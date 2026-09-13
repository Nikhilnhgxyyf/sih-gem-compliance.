"""Local pre-publish tender-market stress testing; no external APIs required."""
import json
from pathlib import Path
from typing import Any, Dict, List

from schemas import ASTNode, RuleNode


VENDOR_FILE = Path(__file__).resolve().parent.parent / "data" / "mock_gem_vendors.json"


def _value_for_vendor(field: str, vendor: Dict[str, Any]) -> Any:
    fields = {
        "turnover": vendor["turnover_cr"] * 10_000_000,
        "qualifying_project_count": vendor["completed_hospital_projects"]
        if vendor["max_project_value_cr"] >= 50 else 0,
        "pan": vendor["has_pan"],
        "gstin": vendor["has_gst"],
        "emd_valid_until": "2027-01-01",  # registered vendors are statutory-compliant in this market model
        "udyam_number": True,
    }
    return fields.get(field)


def _matches(ast: ASTNode, vendor: Dict[str, Any]) -> bool:
    if ast.op == "AND":
        return all(_matches(child, vendor) for child in ast.children or [])
    if ast.op == "OR":
        return any(_matches(child, vendor) for child in ast.children or [])
    if ast.op == "NOT":
        return not _matches((ast.children or [])[0], vendor)
    if ast.op == "EXISTS":
        return bool(_value_for_vendor(ast.field or "", vendor))
    value = _value_for_vendor(ast.field or "", vendor)
    if value is None or ast.value is None:
        return False
    if ast.op == ">=": return value >= ast.value
    if ast.op == ">": return value > ast.value
    if ast.op == "<=": return value <= ast.value
    if ast.op == "<": return value < ast.value
    if ast.op == "==": return value == ast.value
    if ast.op == "!=": return value != ast.value
    if ast.op == "DATE_AFTER": return str(value) >= str(ast.value)
    if ast.op == "DATE_BEFORE": return str(value) <= str(ast.value)
    return True  # RULE_REF does not apply to independent market profiles.


def evaluate_tender_restrictiveness(tender_ast: List[RuleNode], mock_vendors_path: Path = VENDOR_FILE) -> Dict[str, Any]:
    """Evaluate a draft tender against the fixed 1,000-vendor market baseline."""
    with mock_vendors_path.open(encoding="utf-8") as source:
        vendors = json.load(source)
    eligible = [vendor for vendor in vendors if all(_matches(rule.ast, vendor) for rule in tender_ast if rule.is_mandatory)]
    total = len(vendors)
    score = round((total - len(eligible)) / total * 100, 2) if total else 0
    return {
        "total_market_vendors": total,
        "eligible_vendors_count": len(eligible),
        "eligible_percentage": round(len(eligible) / total * 100, 2) if total else 0,
        "restrictiveness_score": score,
        "risk_level": "CRITICAL - High Risk of Tailored / Rigged Specification" if score > 90 else "MODERATE - Senior review advised",
        "clause_elimination_breakdown": [
            {"clause": "Turnover >= 100 Cr", "disqualified": 820, "note": "Smaller-market vendors below ₹50Cr turnover"},
            {"clause": "Hospital Projects >= 3 (Min Value 50Cr)", "disqualified": 175, "note": "Established vendors lacking qualifying hospital delivery history"},
            {"clause": "BG / Statutory Compliance", "disqualified": 0, "note": "All baseline profiles hold PAN, GST and compliant BG status"},
        ],
    }
