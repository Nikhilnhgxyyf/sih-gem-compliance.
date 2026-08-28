import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from schemas import EvidenceNode, RuleNode, EvidenceCorrectionRequest
from engine import ProcurementIntelligenceEngine
from extraction import extract_from_documents, build_engine_inputs

app = FastAPI(
    title="GeM AI Auditor V3",
    description=(
        "Evidence-Driven Procurement Evaluation Engine with deterministic "
        "rule compilation, EDPE propagation, blast-radius analysis and "
        "cryptographic audit logging."
    ),
    version="3.0.0",
)

# Set ALLOWED_ORIGINS on Render to your actual Vercel URL(s), comma
# separated, e.g. "https://gem-ai-auditor.vercel.app". Falls back to local
# dev ports so `python -m http.server` / Live Server keep working untouched.
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:5500,http://localhost:5500",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

DEFAULT_TENDER_DEADLINE = datetime(2026, 8, 30, tzinfo=timezone.utc)
MAX_FILE_SIZE_MB = 15

# One engine per bidder, so a tender can be evaluated against several
# bidders at once instead of each upload wiping out the last one.
engines: Dict[str, ProcurementIntelligenceEngine] = {}
bidder_labels: Dict[str, str] = {}
active_bidder_id: Optional[str] = None


def current_engine() -> ProcurementIntelligenceEngine:
    global active_bidder_id
    if active_bidder_id is None or active_bidder_id not in engines:
        if "EMPTY" not in engines:
            engines["EMPTY"] = ProcurementIntelligenceEngine(
                audit_id="GEMA-EMPTY", tender_deadline=DEFAULT_TENDER_DEADLINE
            )
        active_bidder_id = "EMPTY"
    return engines[active_bidder_id]


@app.get("/")
async def root():
    return {
        "system": "GeM AI Auditor V3",
        "status": "ONLINE",
        "architecture": "EDPE",
        "decision_engine": "DETERMINISTIC",
        "ledger": "SHA256 HASH CHAIN",
        "bidders_loaded": len(engines),
    }


@app.get("/api/v3/health")
async def health():
    engine = current_engine()
    return {
        "status": "healthy",
        "audit_id": engine.audit_id,
        "evidence_nodes": len(engine.evidence_nodes),
        "rules": len(engine.rule_nodes),
        "ledger_events": len(engine.ledger),
    }


@app.post("/api/v3/ingest-documents")
async def ingest_documents(
    bidder_files: List[UploadFile] = File(
        ..., description="One or more bidder documents: PAN, GST certificate, Udyam certificate, financials, etc."
    ),
    tender_file: Optional[UploadFile] = File(
        None, description="Optional: the tender/eligibility document to compile requirements from"
    ),
    bidder_label: Optional[str] = Form(
        None, description="How this bidder should show up in the comparison table, e.g. the company name"
    ),
):
    global active_bidder_id

    bidder_payload = []
    for f in bidder_files:
        content = await f.read()
        _check_size(content, f.filename)
        bidder_payload.append({
            "filename": f.filename,
            "mime_type": f.content_type or "application/pdf",
            "data": content,
        })

    tender_payload = None
    if tender_file is not None:
        content = await tender_file.read()
        _check_size(content, tender_file.filename)
        tender_payload = {
            "filename": tender_file.filename,
            "mime_type": tender_file.content_type or "application/pdf",
            "data": content,
        }

    extraction = extract_from_documents(bidder_payload, tender_payload)
    if "error" in extraction:
        raise HTTPException(status_code=502, detail=f"AI extraction failed: {extraction['error']}")

    evidence_nodes, rule_nodes = build_engine_inputs(extraction)

    deadline = DEFAULT_TENDER_DEADLINE
    closing = extraction.get("tender_closing_date")
    if closing:
        try:
            deadline = datetime.strptime(closing, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    bidder_id = f"BIDDER-{sum(1 for k in engines if k != 'EMPTY') + 1}"
    label = bidder_label.strip() if bidder_label and bidder_label.strip() else bidder_id

    new_engine = ProcurementIntelligenceEngine(
        audit_id=f"GEMA-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
        tender_deadline=deadline,
    )

    try:
        for node in evidence_nodes:
            new_engine.register_evidence(node)
        for rule in rule_nodes:
            new_engine.register_rule(rule)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    new_engine.rebuild_dependencies()
    evaluations = new_engine.evaluate_all_rules()

    new_engine._append_to_ledger(
        action="DOCUMENT_INGESTION",
        actor="AI_EXTRACTION",
        payload={
            "bidder_files": [f["filename"] for f in bidder_payload],
            "tender_file": tender_payload["filename"] if tender_payload else None,
            "evidence_count": len(evidence_nodes),
            "rule_count": len(rule_nodes),
        },
    )

    engines[bidder_id] = new_engine
    bidder_labels[bidder_id] = label
    active_bidder_id = bidder_id

    return {
        "message": "Documents extracted and knowledge graph constructed.",
        "bidder_id": bidder_id,
        "bidder_label": label,
        "documents_processed": [d["filename"] for d in extraction.get("documents", [])],
        "evidence_count": len(new_engine.evidence_nodes),
        "rule_count": len(new_engine.rule_nodes),
        "dependency_count": len(new_engine.edges),
        "compliance": new_engine.calculate_overall_compliance(evaluations).model_dump(mode="json"),
    }


def _check_size(content: bytes, filename: str):
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"{filename} is {size_mb:.1f}MB, over the {MAX_FILE_SIZE_MB}MB limit.",
        )


@app.get("/api/v3/bidders")
async def list_bidders():
    """Side-by-side comparison across every bidder loaded this session."""
    rows = []
    for bidder_id, eng in engines.items():
        if bidder_id == "EMPTY":
            continue
        decision = eng.calculate_overall_compliance()
        rows.append({
            "bidder_id": bidder_id,
            "label": bidder_labels.get(bidder_id, bidder_id),
            "compliance_score": decision.compliance_score,
            "decision": decision.decision,
            "mandatory_failures": len(decision.mandatory_failures),
            "review_triggers": len(decision.review_triggers),
            "is_active": bidder_id == active_bidder_id,
        })
    rows.sort(key=lambda r: r["compliance_score"], reverse=True)
    return {"bidders": rows}


@app.post("/api/v3/bidders/{bidder_id}/activate")
async def activate_bidder(bidder_id: str):
    global active_bidder_id
    if bidder_id not in engines:
        raise HTTPException(status_code=404, detail=f"Bidder '{bidder_id}' not found.")
    active_bidder_id = bidder_id
    return {"active_bidder_id": bidder_id, "label": bidder_labels.get(bidder_id, bidder_id)}


@app.post("/api/v3/ingest")
async def ingest(evidence: List[EvidenceNode], rules: List[RuleNode]):
    engine = current_engine()
    try:
        for node in evidence:
            engine.register_evidence(node)
        for rule in rules:
            engine.register_rule(rule)

        engine.rebuild_dependencies()
        evaluations = engine.evaluate_all_rules()

        engine._append_to_ledger(
            action="INGESTION_COMPLETE",
            actor="SYSTEM",
            payload={"evidence_count": len(evidence), "rule_count": len(rules)},
        )

        return {
            "message": "Knowledge graph constructed.",
            "evidence_count": len(engine.evidence_nodes),
            "rule_count": len(engine.rule_nodes),
            "dependency_count": len(engine.edges),
            "compliance": engine.calculate_overall_compliance(evaluations).model_dump(mode="json"),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/v3/evaluate")
async def evaluate():
    engine = current_engine()
    evaluations = engine.evaluate_all_rules()
    decision = engine.calculate_overall_compliance(evaluations)
    return {
        "decisions": {rid: e.model_dump(mode="json") for rid, e in evaluations.items()},
        "overall": decision.model_dump(mode="json"),
    }


@app.get("/api/v3/dashboard")
async def dashboard():
    return current_engine().get_snapshot()


@app.get("/api/v3/graph")
async def graph():
    engine = current_engine()
    return {
        "nodes": {
            "evidence": [n.model_dump(mode="json") for n in engine.evidence_nodes.values()],
            "rules": [r.model_dump(mode="json") for r in engine.rule_nodes.values()],
        },
        "edges": [e.model_dump(mode="json") for e in engine.edges],
    }


@app.get("/api/v3/blast-radius/{node_id}")
async def blast_radius(node_id: str):
    engine = current_engine()
    if node_id not in engine.evidence_nodes:
        raise HTTPException(status_code=404, detail="Evidence node not found.")
    return engine.analyze_blast_radius(node_id)


@app.post("/api/v3/officer-override")
async def officer_override(request: EvidenceCorrectionRequest):
    engine = current_engine()
    try:
        result = engine.incremental_recalculate(
            changed_node_id=request.node_id,
            new_value=request.new_value,
            actor=request.actor,
        )
        return {
            "message": "Evidence correction propagated.",
            "impact_analysis": result,
            "latest_hash": engine.ledger[-1].event_hash,
        }
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# CounterfactualRequest in schemas.py wants a full List[EvidenceNode], which
# is correct for the API but not something anyone's typing into a two-field
# form. This takes the shape the UI actually collects and builds the
# EvidenceNode itself.
class SimpleCounterfactualRequest(BaseModel):
    entity_name: str
    extracted_value: str


@app.post("/api/v3/counterfactual")
async def counterfactual(request: SimpleCounterfactualRequest):
    hypothetical = EvidenceNode(
        node_id=f"HYP-{request.entity_name.upper()}",
        entity_name=request.entity_name.strip().lower(),
        extracted_value=_coerce(request.extracted_value),
        confidence=1.0,
        source_doc="officer_hypothetical",
    )
    return current_engine().optimize_compliance_intervention([hypothetical])


def _coerce(raw: str) -> Any:
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw


@app.get("/api/v3/audit-chain")
async def audit_chain():
    engine = current_engine()
    valid, message = engine.verify_chain_integrity()
    return {
        "chain_valid": valid,
        "message": message,
        "ledger_length": len(engine.ledger),
        "ledger": [e.model_dump(mode="json") for e in engine.ledger],
    }


@app.get("/api/v3/stats")
async def stats():
    engine = current_engine()
    decision = engine.calculate_overall_compliance()
    return {
        "audit_id": engine.audit_id,
        "evidence_nodes": len(engine.evidence_nodes),
        "rule_nodes": len(engine.rule_nodes),
        "dependency_edges": len(engine.edges),
        "ledger_events": len(engine.ledger),
        "decision": decision.decision,
        "compliance_score": decision.compliance_score,
    }


@app.get("/api/v3/state")
async def get_engine_state():
    engine = current_engine()
    rule_statuses = {rid: engine.current_rule_states.get(rid, "REVIEW") for rid in engine.rule_nodes}
    return {
        "audit_id": engine.audit_id,
        "tender_deadline": engine.tender_deadline.isoformat(),
        "evidence": [n.model_dump(mode="json") for n in engine.evidence_nodes.values()],
        "rules": [r.model_dump(mode="json") for r in engine.rule_nodes.values()],
        "edges": [e.model_dump(mode="json") for e in engine.edges],
        "rule_statuses": rule_statuses,
        "ledger": [e.model_dump(mode="json") for e in engine.ledger],
    }
