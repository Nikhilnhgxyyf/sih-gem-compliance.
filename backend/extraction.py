"""
Document extraction layer — turns an uploaded PDF/image into the
EvidenceNode / RuleNode objects engine.py works with.

Uses google-genai with a Pydantic response_schema so Gemini is forced into
valid JSON matching ExtractionResult. Facts are extracted as generic
entity_name/value pairs (turnover, pan, gstin, udyam, iso_certification...)
rather than a fixed set of fields, so the same pipeline works for whatever
a given tender actually asks for.

v2 additions:
  - source_quote per fact: the exact sentence a value came from, so an
    officer can verify a number without reopening the original file.
  - Requirements are now a tree (ExtractedRequirementNode, AND/OR/NOT with
    children), not just flat comparisons — engine.py's AST evaluator
    already supports composite rules, this just uses that.
  - WITHIN_LAST_N_YEARS is a convenience pseudo-op: the LLM gives a plain
    number of years, and the actual cutoff date is computed here in
    Python (against tender_closing_date) rather than trusting the model
    to do date arithmetic, then emitted as a real DATE_AFTER node.
  - Identity-consistency is now a real deterministic check: the entity
    name as written on each of a bidder's own documents is compared
    (token-overlap, not exact string match) and a mismatch is surfaced
    as a Warning evidence node — never an accusation, always "needs
    human review", same pattern as the GSTIN/PAN check below.
"""

import os
import re
import time
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from typing import List, Optional, Literal

from pydantic import BaseModel, Field, field_validator
from google import genai
from google.genai import types

from schemas import EvidenceNode, RuleNode, ASTNode

client: Optional[genai.Client] = None

# Flash-Lite is deliberately used for this prototype: extraction is the only
# generative step and the deterministic engine makes every final decision.
# It has lower latency/cost and is less prone to presentation-breaking spikes.
MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
FALLBACK_MODEL_NAME = os.environ.get("GEMINI_FALLBACK_MODEL", "gemini-2.5-flash")


def _get_client() -> genai.Client:
    """Initialise Gemini only when an extraction is requested.

    This keeps health checks and deterministic API endpoints usable when a
    local developer has not configured a Gemini key yet.
    """
    global client
    if client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured on this server.")
        client = genai.Client(api_key=api_key)
    return client


# --------------------------------------------------------------------------
# Extraction-time schema (Gemini's output). Converted into engine schemas
# (EvidenceNode / RuleNode / ASTNode) by build_engine_inputs() below.
# --------------------------------------------------------------------------

class ExtractedFact(BaseModel):
    entity_name: str = Field(
        description="snake_case field name, reused consistently across documents, e.g. "
                    "'turnover', 'pan', 'gstin', 'udyam_number', 'experience_years', 'iso_certification'"
    )
    value: str = Field(description="extracted value as a string; plain digits for numbers, YYYY-MM-DD for dates")
    confidence: float = Field(ge=0.0, le=1.0)
    page: int
    valid_until: Optional[str] = Field(default=None, description="YYYY-MM-DD if this fact has an expiry date, else null")
    source_quote: Optional[str] = Field(
        default=None,
        description="the exact sentence or line (max ~20 words) this value was read from, verbatim from the document"
    )


class ExtractedDocument(BaseModel):
    filename: str
    document_type: str
    bidder_name_on_document: Optional[str] = Field(
        default=None, description="the company/entity name exactly as written on THIS document, if present"
    )
    facts: List[ExtractedFact]
    notes: str


class ExtractedRequirementNode(BaseModel):
    description: str = Field(description="plain-language statement of this requirement or sub-requirement")
    op: Literal["AND", "OR", "NOT", ">=", ">", "<=", "<", "==", "!=", "EXISTS", "WITHIN_LAST_N_YEARS"]
    entity_name: Optional[str] = Field(default=None, description="required for leaf comparisons; omit for AND/OR/NOT")
    value: Optional[str] = Field(
        default=None,
        description="comparison value; for WITHIN_LAST_N_YEARS this is the number of years as a string, e.g. '7'"
    )
    mandatory: bool = Field(default=True, description="True for hard eligibility criteria, False if preferred/conditional")
    weight: float = Field(default=10.0, description="relative importance, roughly 1-100 — only meaningful at top level")
    children: Optional[List["ExtractedRequirementNode"]] = Field(
        default=None, description="sub-requirements — only for AND / OR / NOT"
    )

    @field_validator("weight", mode="before")
    @classmethod
    def default_missing_weight(cls, value):
        """Accept null/missing LLM weights without rejecting useful output."""
        return 10.0 if value is None else value


ExtractedRequirementNode.model_rebuild()


class ExtractionResult(BaseModel):
    documents: List[ExtractedDocument]
    requirements: List[ExtractedRequirementNode] = Field(
        description="Top-level eligibility requirements from the TENDER document. Empty list if no tender was provided."
    )
    tender_closing_date: Optional[str] = Field(default=None, description="YYYY-MM-DD if a tender doc was provided")


SYSTEM_PROMPT = """You are an expert Indian Government Procurement Auditor extracting structured \
data from GeM (Government e-Marketplace) bid documents.

You will receive one or more documents, labelled TENDER (buyer's requirement document) or BIDDER \
(seller's submission). Documents may be scanned, photographed, low-quality, or handwritten. A \
single uploaded file is often a whole bidder packet scanned together — a PAN card followed by a \
GST certificate followed by a financial statement, etc. Treat each distinct certificate or \
section as its OWN entry in documents (own document_type, own bidder_name_on_document), even \
though they share the same filename — do not merge separate certificates into one entry just \
because they arrived in the same file.

For EACH document:
- Extract every relevant fact as an entity_name/value pair — PAN, GSTIN, Udyam number, turnover, \
years of experience, project completion dates, certifications, and anything else that looks like \
it would matter for eligibility. Use consistent snake_case entity_names across documents (always \
"turnover", never "annual_turnover" in one place and "revenue" elsewhere) so facts about the same \
thing can be compared across documents.
- Note the page each fact came from, and copy the exact sentence or line it appears in as \
source_quote (verbatim, under ~20 words) — this lets an officer verify the number without \
reopening the file.
- Extract bidder_name_on_document — the company name exactly as printed on that specific document.
- If the document states a validity/expiry date, extract it as valid_until (YYYY-MM-DD).
- If a value is not visible, do not invent one. Say so in the notes field instead.

If a TENDER document was provided, extract its eligibility requirements as a tree using \
requirements. Simple requirements are a single leaf: {op: ">=", entity_name: "turnover", value: \
"10000000"}. Compound requirements ("at least 3 similar projects of ₹50 Cr each in the last 5 \
years") become an AND node whose children are the individual leaf conditions (project_count >= 3, \
project_value >= 50000000, WITHIN_LAST_N_YEARS with value "5") — so each sub-condition can be \
checked and shown separately, not collapsed into one pass/fail. For a "completed within the last \
N years" style condition, use op WITHIN_LAST_N_YEARS with entity_name set to the relevant \
completion-date fact and value set to N as a plain number string — do not compute a cutoff date \
yourself. If no tender document was provided, return an empty requirements list. If the tender \
states a bid closing/submission date, extract it as tender_closing_date.

Be conservative: only report what is actually visible in the documents, and say so in a \
document's notes field when it's unreadable or irrelevant, rather than guessing.
"""


def extract_from_documents(bidder_files: List[dict], tender_file: Optional[dict] = None) -> dict:
    """
    bidder_files: list of {"filename": str, "mime_type": str, "data": bytes}
    tender_file:  same shape, optional

    Returns {"error": ...} on failure, else the raw ExtractionResult as a dict.
    """
    contents: list = []

    if tender_file is not None:
        contents.append(f"=== TENDER / ELIGIBILITY DOCUMENT: {tender_file['filename']} ===")
        contents.append(types.Part.from_bytes(data=tender_file["data"], mime_type=tender_file["mime_type"]))

    for f in bidder_files:
        contents.append(f"=== BIDDER DOCUMENT: {f['filename']} ===")
        contents.append(types.Part.from_bytes(data=f["data"], mime_type=f["mime_type"]))

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=ExtractionResult,
    )
    # A short retry covers transient 503 demand spikes. If Flash-Lite remains
    # unavailable, use the configurable Flash fallback rather than making the
    # officer re-upload documents.
    attempts = [MODEL_NAME, MODEL_NAME, FALLBACK_MODEL_NAME]
    last_error: Optional[Exception] = None
    for attempt, model_name in enumerate(attempts):
        try:
            response = _get_client().models.generate_content(
                model=model_name,
                contents=contents,
                config=config,
            )
            result: Optional[ExtractionResult] = response.parsed
            if result is None:
                result = ExtractionResult.model_validate_json(response.text)
            payload = result.model_dump()
            payload["extraction_model"] = model_name
            return payload
        except Exception as error:
            last_error = error
            if attempt < len(attempts) - 1:
                time.sleep(0.5 * (attempt + 1))
    return {"error": str(last_error), "status": "AI_EXTRACTION_FAILED"}


def extract_bidder_only(bidder_files: List[dict]) -> dict:
    """Same as extract_from_documents but never asks for requirements — used
    when a tender's rules were already compiled earlier this session and
    are being reused (see main.py). Keeps the same output shape with
    requirements always empty, so build_engine_inputs() doesn't need a
    separate code path."""
    return extract_from_documents(bidder_files, tender_file=None)


def _coerce_value(raw: Optional[str]):
    if raw is None:
        return None
    try:
        return int(raw)
    except (ValueError, TypeError):
        pass
    try:
        return float(raw)
    except (ValueError, TypeError):
        return raw


# Canonicalise common variants before nodes and rules reach the graph. This
# prevents an extraction such as "annual_turnover" from silently disconnecting
# from a tender rule written as "turnover".
ENTITY_ALIASES = {
    "annual_turnover": "turnover",
    "annual_revenue": "turnover",
    "revenue": "turnover",
    "turn_over": "turnover",
    "years_of_experience": "experience_years",
    "experience": "experience_years",
    "project_experience": "experience_years",
    "udyam": "udyam_number",
    "udyam_registration_number": "udyam_number",
    "gst_number": "gstin",
    "pan_number": "pan",
}


def canonical_entity_name(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    normalized = re.sub(r"[^a-z0-9]+", "_", raw.strip().lower()).strip("_")
    return ENTITY_ALIASES.get(normalized, normalized)


def _parse_iso_date(value: Optional[str]):
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")

NAME_STOPWORDS = {"pvt", "ltd", "limited", "private", "the", "and", "co", "company", "corp", "corporation", "llp", "inc"}


def _name_tokens(name: str) -> set:
    cleaned = re.sub(r"[^a-z0-9\s]", " ", name.lower())
    return {t for t in cleaned.split() if t and t not in NAME_STOPWORDS}


def _name_similarity(a: str, b: str) -> float:
    ta, tb = _name_tokens(a), _name_tokens(b)
    if not ta or not tb:
        return 1.0  # nothing usable to compare — don't flag on missing data
    return len(ta & tb) / max(len(ta), len(tb))


def _convert_requirement_node(node: dict, tender_closing: Optional[datetime], counter: list) -> ASTNode:
    """Recursively turns one ExtractedRequirementNode dict into a real ASTNode.
    WITHIN_LAST_N_YEARS is translated into a concrete DATE_AFTER cutoff here —
    the date arithmetic happens in Python, never trusted to the model."""
    op = node["op"]

    if op == "WITHIN_LAST_N_YEARS":
        try:
            years = int(float(node.get("value") or "0"))
        except (TypeError, ValueError):
            years = 0
        anchor = tender_closing or datetime.now(timezone.utc)
        cutoff = anchor - relativedelta(years=years)
        return ASTNode(op="DATE_AFTER", field=canonical_entity_name(node.get("entity_name")), value=cutoff.strftime("%Y-%m-%d"))

    if op in ("AND", "OR", "NOT"):
        children = [_convert_requirement_node(c, tender_closing, counter) for c in (node.get("children") or [])]
        return ASTNode(op=op, children=children)

    return ASTNode(op=op, field=canonical_entity_name(node.get("entity_name")), value=_coerce_value(node.get("value")))


def build_engine_inputs(extraction: dict) -> tuple:
    """
    Converts a raw ExtractionResult dict into (evidence_nodes, rule_nodes)
    for engine.register_evidence() / engine.register_rule().

    Also runs two deterministic, non-LLM checks:
      - GSTIN encodes the filer's PAN at characters 3-12 — a mismatch
        against a standalone PAN document is pure string comparison.
      - Entity name consistency across a bidder's own documents, by token
        overlap (not exact string match, so "ABC Infra Ltd" vs "ABC
        Infrastructure Pvt Ltd" is still comparable). Both are surfaced as
        their own evidence nodes with status Warning, never Fail — a
        mismatch needs a human to look, it is never treated as proof of
        anything on its own.
    """
    evidence_nodes: List[EvidenceNode] = []
    counter = 0
    pans, gstins, doc_names = [], [], []

    tender_closing = _parse_iso_date(extraction.get("tender_closing_date"))

    for doc in extraction.get("documents", []):
        for fact in doc.get("facts", []):
            counter += 1
            entity = canonical_entity_name(fact["entity_name"])
            value = _coerce_value(fact["value"])

            evidence_nodes.append(EvidenceNode(
                node_id=f"E{counter:03d}",
                entity_name=entity,
                extracted_value=value,
                confidence=fact.get("confidence", 0.8),
                source_doc=doc["filename"],
                page_number=fact.get("page"),
                source_quote=fact.get("source_quote"),
                valid_until=_parse_iso_date(fact.get("valid_until")),
            ))

            if entity == "pan" and isinstance(value, str) and PAN_RE.match(value.upper()):
                pans.append((value.upper(), doc["filename"]))
            if entity == "gstin" and isinstance(value, str) and GSTIN_RE.match(value.upper()):
                gstins.append((value.upper(), doc["filename"]))

        if doc.get("bidder_name_on_document"):
            doc_names.append((doc["bidder_name_on_document"], doc["filename"]))

    for gstin_val, gstin_doc in gstins:
        embedded_pan = gstin_val[2:12]
        for pan_val, pan_doc in pans:
            counter += 1
            match = embedded_pan == pan_val
            evidence_nodes.append(EvidenceNode(
                node_id=f"E{counter:03d}",
                entity_name="identity_consistency",
                extracted_value="CONSISTENT" if match else "MISMATCH_NEEDS_REVIEW",
                confidence=1.0,
                source_doc=f"system check: {gstin_doc} vs {pan_doc}",
                page_number=None,
            ))

    for i in range(len(doc_names)):
        for j in range(i + 1, len(doc_names)):
            name_a, file_a = doc_names[i]
            name_b, file_b = doc_names[j]
            similarity = _name_similarity(name_a, name_b)
            if similarity < 0.6:
                counter += 1
                evidence_nodes.append(EvidenceNode(
                    node_id=f"E{counter:03d}",
                    entity_name="identity_consistency",
                    extracted_value="NAME_MISMATCH_NEEDS_REVIEW",
                    confidence=round(1 - similarity, 2),
                    source_doc=f"system check: '{name_a}' ({file_a}) vs '{name_b}' ({file_b})",
                    page_number=None,
                ))

    rule_nodes: List[RuleNode] = []
    for i, req in enumerate(extraction.get("requirements", []), start=1):
        rule_id = f"R{i:03d}"
        ast = _convert_requirement_node(req, tender_closing, [0])
        rule_nodes.append(RuleNode(
            rule_id=rule_id,
            clause_text=req["description"],
            ast=ast,
            weight=req.get("weight", 10.0),
            is_mandatory=req.get("mandatory", True),
        ))

    return evidence_nodes, rule_nodes
