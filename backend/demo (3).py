from datetime import datetime, timezone

from schemas import (
    EvidenceNode,
    RuleNode,
    ASTNode,
)

from engine import (
    ProcurementIntelligenceEngine,
)


def run_demo():

    print()
    print("=" * 70)
    print("       GeM AI AUDITOR V3 — EDPE VERIFICATION")
    print("=" * 70)

    deadline = datetime(
        2026,
        8,
        30,
        tzinfo=timezone.utc,
    )

    engine = ProcurementIntelligenceEngine(
        audit_id="GEMA-DEMO-001",
        tender_deadline=deadline,
    )

    # ========================================================
    # 1. EVIDENCE
    # ========================================================

    print("\n[1] INGESTING EVIDENCE")

    turnover_financial = EvidenceNode(
        node_id="E14",
        entity_name="turnover",
        extracted_value=7.2,
        confidence=0.98,
        source_doc="financial_statement.pdf",
        page_number=3,
    )

    turnover_certificate = EvidenceNode(
        node_id="E22",
        entity_name="turnover",
        extracted_value=11.2,
        confidence=0.95,
        source_doc="turnover_certificate.pdf",
        page_number=1,
    )

    projects = EvidenceNode(
        node_id="E09",
        entity_name="project_count",
        extracted_value=4,
        confidence=0.99,
        source_doc="experience.pdf",
        page_number=5,
    )

    engine.register_evidence(
        turnover_financial
    )

    engine.register_evidence(
        turnover_certificate
    )

    engine.register_evidence(
        projects
    )

    print("✓ 3 evidence nodes registered")

    # ========================================================
    # 2. RULES
    # ========================================================

    print("\n[2] COMPILING PROCUREMENT RULES")

    turnover_rule = RuleNode(
        rule_id="R42",
        clause_text=(
            "Bidder must have turnover >= ₹10 Cr"
        ),
        ast=ASTNode(
            op=">=",
            field="turnover",
            value=10.0,
        ),
        weight=50,
        is_mandatory=True,
    )

    experience_rule = RuleNode(
        rule_id="R43",
        clause_text=(
            "Bidder must have at least 3 projects"
        ),
        ast=ASTNode(
            op=">=",
            field="project_count",
            value=3,
        ),
        weight=30,
        is_mandatory=True,
    )

    composite_rule = RuleNode(
        rule_id="R90",
        clause_text=(
            "Turnover and experience eligibility"
        ),
        ast=ASTNode(
            op="AND",
            children=[
                ASTNode(
                    op="RULE_REF",
                    field="R42",
                ),
                ASTNode(
                    op="RULE_REF",
                    field="R43",
                ),
            ],
        ),
        weight=20,
        is_mandatory=True,
    )

    engine.register_rule(
        turnover_rule
    )

    engine.register_rule(
        experience_rule
    )

    engine.register_rule(
        composite_rule
    )

    engine.rebuild_dependencies()

    print("✓ 3 executable rules compiled")

    # ========================================================
    # 3. INITIAL EVALUATION
    # ========================================================

    print("\n[3] INITIAL EVALUATION")

    evaluations = (
        engine.evaluate_all_rules()
    )

    overall = (
        engine.calculate_overall_compliance(
            evaluations
        )
    )

    print(
        f"Decision : {overall.decision}"
    )

    print(
        f"Score    : {overall.compliance_score}"
    )

    for rid, result in evaluations.items():

        print(
            f"  {rid}: "
            f"{result.status.value} | "
            f"{result.reasoning}"
        )

    # ========================================================
    # 4. BLAST RADIUS
    # ========================================================

    print("\n[4] BLAST-RADIUS ANALYSIS")

    radius = engine.analyze_blast_radius(
        "E14"
    )

    print(
        f"Changed evidence : {radius['target_node']}"
    )

    print(
        f"Affected rules   : {radius['affected_rules']}"
    )

    print(
        f"Blast radius     : {radius['blast_radius_size']}"
    )

    print(
        f"Sensitivity      : {radius['decision_sensitivity']}"
    )

    # ========================================================
    # 5. COUNTERFACTUAL
    # ========================================================

    print("\n[5] COUNTERFACTUAL SIMULATION")

    hypothetical = EvidenceNode(
        node_id="HYP-E14",
        entity_name="turnover",
        extracted_value=12.5,
        confidence=1.0,
        source_doc="officer_verified.pdf",
        page_number=1,
    )

    simulation = (
        engine.optimize_compliance_intervention(
            [hypothetical]
        )
    )

    print(
        f"Current decision   : "
        f"{simulation['current_decision']}"
    )

    print(
        f"Projected decision : "
        f"{simulation['projected_decision']}"
    )

    print(
        f"Score improvement  : "
        f"{simulation['score_improvement']}"
    )

    print(
        f"Flipped rules      : "
        f"{simulation['flipped_rules']}"
    )

    # ========================================================
    # 6. OFFICER CORRECTION
    # ========================================================

    print("\n[6] OFFICER CORRECTION")

    impact = (
        engine.incremental_recalculate(
            changed_node_id="E14",
            new_value=11.2,
            actor="OFFICER-402",
        )
    )

    print(
        f"Decision : "
        f"{impact['old_decision']} "
        f"→ "
        f"{impact['new_decision']}"
    )

    print(
        f"Score    : "
        f"{impact['old_score']} "
        f"→ "
        f"{impact['new_score']}"
    )

    print(
        f"Recalculated rules: "
        f"{impact['affected_rules']}"
    )

    # ========================================================
    # 7. HASH VERIFICATION
    # ========================================================

    print("\n[7] CRYPTOGRAPHIC LEDGER")

    valid, message = (
        engine.verify_chain_integrity()
    )

    print(
        f"Before tampering: "
        f"{valid} — {message}"
    )

    # --------------------------------------------------------
    # Deliberate tampering
    # --------------------------------------------------------

    engine.ledger[1].payload[
        "audit_id"
    ] = "TAMPERED"

    valid, message = (
        engine.verify_chain_integrity()
    )

    print(
        f"After tampering : "
        f"{valid} — {message}"
    )

    # ========================================================
    # COMPLETE
    # ========================================================

    print()
    print("=" * 70)
    print("                 DEMO COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
