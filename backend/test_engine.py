import unittest
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from engine import ProcurementIntelligenceEngine, check_margin, format_rule_report
from schemas import ASTNode, EvidenceNode, RuleNode, RuleStatus


class EngineTestCase(unittest.TestCase):
    def make_engine(self):
        return ProcurementIntelligenceEngine(
            audit_id="test-audit",
            tender_deadline=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

    @staticmethod
    def evidence(node_id, entity, value, confidence=0.99):
        return EvidenceNode(
            node_id=node_id,
            entity_name=entity,
            extracted_value=value,
            confidence=confidence,
            source_doc="financials.pdf",
            page_number=3,
        )

    def test_close_numeric_match_requires_review(self):
        engine = self.make_engine()
        engine.register_evidence(self.evidence("E001", "turnover", 110))
        engine.register_rule(RuleNode(
            rule_id="R001", clause_text="Turnover must be at least 100",
            ast=ASTNode(op=">=", field="turnover", value=100),
        ))
        evaluation = engine.evaluate_rule("R001")
        self.assertEqual(evaluation.status, RuleStatus.REVIEW)
        self.assertIn("officer review required", evaluation.reasoning)

    def test_large_numeric_margin_can_pass_and_report_provenance(self):
        engine = self.make_engine()
        evidence = self.evidence("E001", "turnover", 120)
        rule = RuleNode(
            rule_id="R001", clause_text="Turnover must be at least 100",
            ast=ASTNode(op=">=", field="turnover", value=100),
        )
        engine.register_evidence(evidence)
        engine.register_rule(rule)
        self.assertEqual(engine.evaluate_rule("R001").status, RuleStatus.PASS)
        self.assertEqual(check_margin(120, 100, 0.1), (False, 0.2))
        report = format_rule_report(rule, evidence, "PASS", 0.2, 0.99)
        self.assertIn("financials.pdf, page 3", report)

    def test_date_operators_handle_iso_dates_and_invalid_input(self):
        engine = self.make_engine()
        engine.register_evidence(self.evidence("E001", "completion_date", "2025-12-31T00:00:00Z"))
        engine.register_rule(RuleNode(
            rule_id="R001", clause_text="Completion is before deadline",
            ast=ASTNode(op="DATE_BEFORE", field="completion_date", value="2026-01-01"),
        ))
        self.assertEqual(engine.evaluate_rule("R001").status, RuleStatus.PASS)
        engine.evidence_nodes["E001"].extracted_value = "not-a-date"
        self.assertEqual(engine.evaluate_rule("R001").status, RuleStatus.REVIEW)

    def test_incremental_recalculation_updates_only_affected_subgraph(self):
        engine = self.make_engine()
        engine.register_evidence(self.evidence("E001", "turnover", 80))
        engine.register_rule(RuleNode(
            rule_id="R001", clause_text="Turnover threshold",
            ast=ASTNode(op=">=", field="turnover", value=100),
        ))
        engine.register_rule(RuleNode(
            rule_id="R002", clause_text="Dependent turnover rule",
            ast=ASTNode(op="RULE_REF", field="R001"),
        ))
        engine.rebuild_dependencies()
        result = engine.incremental_recalculate("E001", 130, "Officer")
        self.assertEqual(result["affected_rules"], ["R001", "R002"])
        self.assertEqual(result["new_decision"], "PASS")
        self.assertEqual(engine.current_rule_states["R001"], RuleStatus.PASS)
        self.assertEqual(engine.current_rule_states["R002"], RuleStatus.PASS)

    def test_ledger_detects_tampering(self):
        engine = self.make_engine()
        self.assertEqual(engine.verify_chain_integrity()[0], True)
        engine.ledger[0].payload["audit_id"] = "altered"
        valid, message = engine.verify_chain_integrity()
        self.assertFalse(valid)
        self.assertIn("Tampering detected", message)

    def test_api_officer_override_and_multi_change_counterfactual(self):
        # Import here so engine-only tests stay independent from FastAPI state.
        import main

        main.engines.clear()
        main.active_bidder_id = None
        client = TestClient(main.app)
        payload = {
            "evidence": [{
                "node_id": "E001", "entity_name": "turnover",
                "extracted_value": 80, "confidence": 0.95,
                "source_doc": "financials.pdf",
            }],
            "rules": [{
                "rule_id": "R001", "clause_text": "Turnover threshold",
                "ast": {"op": ">=", "field": "turnover", "value": 100},
            }],
        }
        self.assertEqual(client.post("/api/v3/ingest", json=payload).status_code, 200)
        corrected = client.post("/api/v3/officer-override", json={
            "node_id": "E001", "new_value": 130, "actor": "Officer",
        })
        self.assertEqual(corrected.status_code, 200)
        self.assertEqual(corrected.json()["impact_analysis"]["new_decision"], "PASS")
        simulation = client.post("/api/v3/counterfactual", json={"changes": [
            {"entity_name": "turnover", "extracted_value": "140"},
            {"entity_name": "experience_years", "extracted_value": "7"},
        ]})
        self.assertEqual(simulation.status_code, 200)
        self.assertEqual(simulation.json()["status"], "ALREADY_COMPLIANT")


if __name__ == "__main__":
    unittest.main()
