import unittest
from datetime import datetime, timezone

from engine import (
    ProcurementIntelligenceEngine,
    check_margin,
    format_rule_report,
)
from schemas import ASTNode, EvidenceNode, RuleNode, RuleStatus


class MarginDecisionTests(unittest.TestCase):
    def setUp(self):
        self.engine = ProcurementIntelligenceEngine(
            audit_id="test-audit",
            tender_deadline=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        self.evidence = EvidenceNode(
            node_id="E001",
            entity_name="turnover",
            extracted_value=110,
            confidence=0.99,
            source_doc="financials.pdf",
            page_number=3,
        )
        self.rule = RuleNode(
            rule_id="R001",
            clause_text="Turnover must be at least 100",
            ast=ASTNode(op=">=", field="turnover", value=100),
        )
        self.engine.register_evidence(self.evidence)
        self.engine.register_rule(self.rule)

    def test_close_numeric_match_requires_review(self):
        evaluation = self.engine.evaluate_rule("R001")
        self.assertEqual(evaluation.status, RuleStatus.REVIEW)
        self.assertIn("officer review required", evaluation.reasoning)

    def test_large_numeric_margin_can_pass(self):
        self.evidence.extracted_value = 120
        evaluation = self.engine.evaluate_rule("R001")
        self.assertEqual(evaluation.status, RuleStatus.PASS)
        self.assertEqual(check_margin(120, 100, 0.1), (False, 0.2))

    def test_formatted_report_includes_provenance(self):
        report = format_rule_report(self.rule, self.evidence, "PASS", 0.2, 0.99)
        self.assertIn("Rule R001", report)
        self.assertIn("financials.pdf, page 3", report)


if __name__ == "__main__":
    unittest.main()
