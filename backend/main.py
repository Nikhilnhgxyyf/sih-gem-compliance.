from datetime import datetime, timezone
from typing import List, Any

from fastapi import (
    FastAPI,
    HTTPException,
)

from fastapi.middleware.cors import CORSMiddleware

from schemas import (
    EvidenceNode,
    RuleNode,
    EvidenceCorrectionRequest,
    CounterfactualRequest,
)

from engine import (
    ProcurementIntelligenceEngine,
)


# ============================================================
# APPLICATION
# ============================================================

app = FastAPI(
    title="GeM AI Auditor V3",
    description=(
        "Evidence-Driven Procurement Evaluation Engine "
        "with deterministic rule compilation, EDPE propagation, "
        "blast-radius analysis and cryptographic audit logging."
    ),
    version="3.0.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# ENGINE
# ============================================================

TENDER_DEADLINE = datetime(
    2026,
    8,
    30,
    tzinfo=timezone.utc,
)

engine = ProcurementIntelligenceEngine(
    audit_id="GEMA-HACKATHON-001",
    tender_deadline=TENDER_DEADLINE,
)


# ============================================================
# HEALTH
# ============================================================

@app.get("/")
async def root():

    return {
        "system": "GeM AI Auditor V3",
        "status": "ONLINE",
        "architecture": "EDPE",
        "decision_engine": "DETERMINISTIC",
        "ledger": "SHA256 HASH CHAIN",
    }


@app.get("/api/v3/health")
async def health():

    return {
        "status": "healthy",
        "audit_id": engine.audit_id,
        "evidence_nodes": len(
            engine.evidence_nodes
        ),
        "rules": len(
            engine.rule_nodes
        ),
        "ledger_events": len(
            engine.ledger
        ),
    }


# ============================================================
# INGESTION
# ============================================================

@app.post("/api/v3/ingest")
async def ingest(
    evidence: List[EvidenceNode],
    rules: List[RuleNode],
):

    try:

        for node in evidence:
            engine.register_evidence(
                node
            )

        for rule in rules:
            engine.register_rule(
                rule
            )

        # Rebuild everything after both evidence
        # and rules exist.
        engine.rebuild_dependencies()

        evaluations = (
            engine.evaluate_all_rules()
        )

        engine._append_to_ledger(
            action="INGESTION_COMPLETE",
            actor="SYSTEM",
            payload={
                "evidence_count": len(
                    evidence
                ),
                "rule_count": len(
                    rules
                ),
            },
        )

        return {
            "message": "Knowledge graph constructed.",
            "evidence_count": len(
                engine.evidence_nodes
            ),
            "rule_count": len(
                engine.rule_nodes
            ),
            "dependency_count": len(
                engine.edges
            ),
            "compliance": (
                engine.calculate_overall_compliance(
                    evaluations
                ).model_dump(
                    mode="json"
                )
            ),
        }

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


# ============================================================
# EVALUATION
# ============================================================

@app.get("/api/v3/evaluate")
async def evaluate():

    evaluations = (
        engine.evaluate_all_rules()
    )

    decision = (
        engine.calculate_overall_compliance(
            evaluations
        )
    )

    return {
        "decisions": {
            rid: evaluation.model_dump(
                mode="json"
            )
            for rid, evaluation
            in evaluations.items()
        },
        "overall": decision.model_dump(
            mode="json"
        ),
    }


# ============================================================
# COMPLETE DASHBOARD STATE
# ============================================================

@app.get("/api/v3/dashboard")
async def dashboard():

    return engine.get_snapshot()


# ============================================================
# GRAPH
# ============================================================

@app.get("/api/v3/graph")
async def graph():

    return {
        "nodes": {
            "evidence": [
                node.model_dump(
                    mode="json"
                )
                for node in engine.evidence_nodes.values()
            ],
            "rules": [
                rule.model_dump(
                    mode="json"
                )
                for rule in engine.rule_nodes.values()
            ],
        },
        "edges": [
            edge.model_dump(
                mode="json"
            )
            for edge in engine.edges
        ],
    }


# ============================================================
# BLAST RADIUS
# ============================================================

@app.get("/api/v3/blast-radius/{node_id}")
async def blast_radius(
    node_id: str,
):

    if node_id not in engine.evidence_nodes:

        raise HTTPException(
            status_code=404,
            detail="Evidence node not found.",
        )

    return engine.analyze_blast_radius(
        node_id
    )


# ============================================================
# OFFICER CORRECTION
# ============================================================

@app.post("/api/v3/officer-override")
async def officer_override(
    request: EvidenceCorrectionRequest,
):

    try:

        result = (
            engine.incremental_recalculate(
                changed_node_id=request.node_id,
                new_value=request.new_value,
                actor=request.actor,
            )
        )

        return {
            "message": "Evidence correction propagated.",
            "impact_analysis": result,
            "latest_hash": engine.ledger[
                -1
            ].event_hash,
        }

    except KeyError as exc:

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )


# ============================================================
# COUNTERFACTUAL
# ============================================================

@app.post("/api/v3/counterfactual")
async def counterfactual(
    request: CounterfactualRequest,
):

    return engine.optimize_compliance_intervention(
        request.evidence
    )


# ============================================================
# AUDIT LEDGER
# ============================================================

@app.get("/api/v3/audit-chain")
async def audit_chain():

    valid, message = (
        engine.verify_chain_integrity()
    )

    return {
        "chain_valid": valid,
        "message": message,
        "ledger_length": len(
            engine.ledger
        ),
        "ledger": [
            event.model_dump(
                mode="json"
            )
            for event in engine.ledger
        ],
    }


# ============================================================
# GRAPH/LEDGER SUMMARY
# ============================================================

@app.get("/api/v3/stats")
async def stats():

    decision = (
        engine.calculate_overall_compliance()
    )

    return {
        "audit_id": engine.audit_id,
        "evidence_nodes": len(
            engine.evidence_nodes
        ),
        "rule_nodes": len(
            engine.rule_nodes
        ),
        "dependency_edges": len(
            engine.edges
        ),
        "ledger_events": len(
            engine.ledger
        ),
        "decision": decision.decision,
        "compliance_score": decision.compliance_score,
                }


@app.get("/api/v3/state")
async def get_engine_state():
    rule_statuses = {
        rid: engine.current_rule_states.get(rid, "REVIEW")
        for rid in engine.rule_nodes
    }

    return {
        "audit_id": engine.audit_id,
        "tender_deadline": engine.tender_deadline.isoformat(),
        "evidence": [
            node.model_dump(mode="json")
            for node in engine.evidence_nodes.values()
        ],
        "rules": [
            rule.model_dump(mode="json")
            for rule in engine.rule_nodes.values()
        ],
        "edges": [
            edge.model_dump(mode="json")
            for edge in engine.edges
        ],
        "rule_statuses": rule_statuses,
        "ledger": [
            event.model_dump(mode="json")
            for event in engine.ledger
        ]
    }


@app.get("/api/v3/blast-radius/{node_id}")
async def blast_radius(node_id: str):
    if node_id not in engine.evidence_nodes:
        raise HTTPException(
            status_code=404,
            detail="Evidence node not found"
        )

    return engine.analyze_blast_radius(node_id)
