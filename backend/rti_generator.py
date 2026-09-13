"""Court/RTI-ready rejection brief generation from deterministic engine data."""
from datetime import datetime, timezone
from typing import Any, Dict


CLAUSE_NAMES = {
    "R001": "Clause 1.1 Financial Capacity",
    "R002": "Clause 1.2 Technical Experience",
    "R003": "Clause 1.3 Statutory PAN Registration",
    "R004": "Clause 1.4 Statutory GST Registration",
    "R006": "Clause 1.5 Bank Guarantee Validity",
}


def generate_rti_legal_brief(bidder_id: str, tender_id: str, evaluation_results: Any, ledger_hash: str) -> Dict[str, Any]:
    """Build a factual brief; only deterministic FAIL outcomes are included."""
    engine = evaluation_results
    violations = []
    for rule_id, rule in engine.rule_nodes.items():
        evaluation = engine.current_rule_evaluations.get(rule_id) or engine.evaluate_rule(rule_id)
        if evaluation.status.value != "FAIL":
            continue
        evidence = engine.evidence_nodes.get(evaluation.evidence_ids[0]) if evaluation.evidence_ids else None
        claimed = evidence.extracted_value if evidence else "Not submitted"
        requirement = rule.ast.value if rule.ast.value is not None else "Required to exist"
        violations.append({
            "clause": CLAUSE_NAMES.get(rule_id, f"Tender Requirement {rule_id}"),
            "rule_id": rule_id,
            "requirement": rule.clause_text,
            "claimed_value": claimed,
            "mandated_threshold": requirement,
            "ast_result": "FAIL (Logical False)",
            "source_document": evidence.source_doc if evidence else "No compliant evidence supplied",
        })
    return {
        "title": "Government e-Marketplace (GeM) - Formal Rejection Brief under RTI Act 2005",
        "reference_number": f"RTI-GEM-{bidder_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "tender_id": tender_id,
        "bidder_id": bidder_id,
        "bidder_name": "",
        "disqualification_timestamp": datetime.now(timezone.utc).isoformat(),
        "violations": violations,
        "cryptographic_audit_footprint": {"ledger_hash": ledger_hash, "genesis_block_reference": engine.ledger[0].event_hash if engine.ledger else None},
    }
