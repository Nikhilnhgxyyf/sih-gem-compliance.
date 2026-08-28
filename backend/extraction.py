"""
Document extraction layer — turns an uploaded PDF/image into the
EvidenceNode / RuleNode objects engine.py works with.

Uses google-genai with a Pydantic response_schema so Gemini is forced into
valid JSON matching ExtractionResult. Facts are extracted as generic
entity_name/value pairs (turnover, pan, gstin, udyam, iso_certification...)
rather than a fixed set of fields, so the same pipeline works for whatever
a given tender actually asks for.
"""

import os
import re
from datetime import datetime, timezone
from typing import List, Optional, Literal

from pydantic import BaseModel, Field
from google import genai
from google.genai import types

from schemas import EvidenceNode, RuleNode, ASTNode

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

MODEL_NAME = "gemini-3.6-flash"


# --------------------------------------------------------------------------
# Extraction-time schema (Gemini's output). Converted into engine schemas
# (EvidenceNode / RuleNode / ASTNode) by build_engine_inputs() below —
# kept separate because the engine's own types (datetime, Any) aren't
# things Gemini should be asked to emit directly.
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


class ExtractedDocument(BaseModel):
    filename: str
    document_type: str
    facts: List[ExtractedFact]
    notes: str


class ExtractedRequirement(BaseModel):
    description: str = Field(description="plain-language statement of the requirement, for the officer to read")
    entity_name: str = Field(description="which fact this checks — MUST match an entity_name used in facts above")
    operator: Literal[">=", ">", "<=", "<", "==", "!=", "EXISTS"]
    value: Optional[str] = Field(default=None, description="comparison value; omit for EXISTS")
    mandatory: bool = Field(description="True for hard eligibility criteria, False for preferred/conditional ones")
    weight: float = Field(default=10.0, description="relative importance, roughly 1-100")


class ExtractionResult(BaseModel):
    documents: List[ExtractedDocument]
    requirements: List[ExtractedRequirement] = Field(
        description="Eligibility requirements from the TENDER document. Empty list if no tender was provided."
    )
    tender_closing_date: Optional[str] = Field(default=None, description="YYYY-MM-DD if a tender doc was provided")


SYSTEM_PROMPT = """You are an expert Indian Government Procurement Auditor extracting structured \
data from GeM (Government e-Marketplace) bid documents.

You will receive one or more documents, labelled TENDER (buyer's requirement document) or BIDDER \
(seller's submission). Documents may be scanned, photographed, low-quality, or handwritten.

For EACH document, extract every relevant fact as an entity_name/value pair — PAN, GSTIN, Udyam \
number, turnover, years of experience, certifications, entity/company name, and anything else \
that looks like it would matter for eligibility. Use consistent snake_case entity_names across \
documents (e.g. always "turnover", never "annual_turnover" in one place and "revenue" in another) \
so facts about the same thing can be compared. Note the page each fact came from. If a document \
states a validity/expiry date for itself or a specific fact, extract it as valid_until in \
YYYY-MM-DD format. Never guess or invent a value that is not actually visible.

If a TENDER document was provided, extract its eligibility requirements as simple comparisons \
(entity_name, operator, value) — e.g. "turnover >= 1000000" or "udyam_number EXISTS". Use the \
SAME entity_name convention as the facts you extracted. If a requirement doesn't reduce to a \
simple comparison, describe it in plain language in the description field and pick the closest \
operator (EXISTS is always a safe fallback). If no tender document was provided, return an empty \
requirements list. If the tender states a bid closing/submission date, extract it as \
tender_closing_date.

Be conservative: only report what is actually visible in the documents, and say so in a \
document's notes field when it's unreadable or irrelevant, rather than guessing.
"""


def extract_from_documents(bidder_files: List[dict], tender_file: Optional[dict] = None) -> dict:
    """
    bidder_files: list of {"filename": str, "mime_type": str, "data": bytes}
    tender_file:  same shape, optional

    Returns {"error": ...} on failure, else the raw ExtractionResult as a dict
    (see build_engine_inputs() to convert that into EvidenceNode/RuleNode lists).
    """
    contents: list = []

    if tender_file is not None:
        contents.append(f"=== TENDER / ELIGIBILITY DOCUMENT: {tender_file['filename']} ===")
        contents.append(types.Part.from_bytes(data=tender_file["data"], mime_type=tender_file["mime_type"]))

    for f in bidder_files:
        contents.append(f"=== BIDDER DOCUMENT: {f['filename']} ===")
        contents.append(types.Part.from_bytes(data=f["data"], mime_type=f["mime_type"]))

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=ExtractionResult,
            ),
        )
        result: Optional[ExtractionResult] = response.parsed
        if result is None:
            result = ExtractionResult.model_validate_json(response.text)
        return result.model_dump()
    except Exception as e:
        return {"error": str(e), "status": "AI_EXTRACTION_FAILED"}


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


def _parse_valid_until(value: Optional[str]):
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")


def build_engine_inputs(extraction: dict) -> tuple:
    """
    Converts a raw ExtractionResult dict into (evidence_nodes, rule_nodes)
    for engine.register_evidence() / engine.register_rule().

    Also cross-checks GSTIN against PAN: a GSTIN encodes the filer's PAN at
    characters 3-12, so a mismatch between a submitted GSTIN and a
    standalone PAN document is pure string comparison, no LLM needed. Added
    as its own "identity_consistency" evidence node so it just shows up in
    the graph like everything else.
    """
    evidence_nodes: List[EvidenceNode] = []
    counter = 0
    pans, gstins = [], []

    for doc in extraction.get("documents", []):
        for fact in doc.get("facts", []):
            counter += 1
            entity = fact["entity_name"].strip().lower()
            value = _coerce_value(fact["value"])

            evidence_nodes.append(EvidenceNode(
                node_id=f"E{counter:03d}",
                entity_name=entity,
                extracted_value=value,
                confidence=fact.get("confidence", 0.8),
                source_doc=doc["filename"],
                page_number=fact.get("page"),
                valid_until=_parse_valid_until(fact.get("valid_until")),
            ))

            if entity == "pan" and isinstance(value, str) and PAN_RE.match(value.upper()):
                pans.append((value.upper(), doc["filename"]))
            if entity == "gstin" and isinstance(value, str) and GSTIN_RE.match(value.upper()):
                gstins.append((value.upper(), doc["filename"]))

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

    rule_nodes: List[RuleNode] = []
    for i, req in enumerate(extraction.get("requirements", []), start=1):
        rule_id = f"R{i:03d}"
        ast = ASTNode(
            op=req["operator"],
            field=req["entity_name"].strip().lower(),
            value=_coerce_value(req.get("value")),
        )
        rule_nodes.append(RuleNode(
            rule_id=rule_id,
            clause_text=req["description"],
            ast=ast,
            weight=req.get("weight", 10.0),
            is_mandatory=req.get("mandatory", True),
        ))

    return evidence_nodes, rule_nodes
