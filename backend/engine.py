import copy
import hashlib
import json
from collections import deque
from datetime import datetime, timezone
from typing import Dict, List, Set, Tuple, Any, Optional

from schemas import (
    EvidenceNode,
    RuleNode,
    DependencyEdge,
    DecisionResult,
    AuditEvent,
    RuleEvaluation,
    RuleStatus,
    EvidenceStatus,
    ASTNode,
)


# ============================================================
# AST UTILITIES
# ============================================================

SUPPORTED_OPERATORS = {
    "AND",
    "OR",
    "NOT",
    ">=",
    ">",
    "<=",
    "<",
    "==",
    "!=",
    "EXISTS",
    "DATE_BEFORE",
    "DATE_AFTER",
    "RULE_REF",
}

MARGIN_PCT = 0.15


def check_margin(left: float, right: float, confidence: float) -> Tuple[bool, float]:
    """Return whether a numeric result is too close to auto-decide.

    ``confidence`` is accepted to keep the decision-policy API explicit; a
    narrow factual margin always wins over model confidence.
    """
    del confidence
    if right == 0:
        return False, 1.0
    margin = abs(left - right) / abs(right)
    return margin <= MARGIN_PCT, margin


def format_rule_report(
    rule: RuleNode,
    evidence: EvidenceNode,
    status: str,
    margin: float,
    confidence: float,
) -> str:
    """Produce a concise, provenance-backed officer-facing rule report."""
    tag = "mandatory" if rule.is_mandatory else "optional"
    if status == RuleStatus.REVIEW.value:
        note = (f"Only {margin * 100:.0f}% from the cutoff — too close to auto-decide. "
                "Flagged for officer review regardless of AI confidence.")
    elif status == RuleStatus.PASS.value:
        note = f"Well above threshold ({margin * 100:.0f}% margin) — auto-decided, no review needed."
    else:
        note = f"Well below threshold ({margin * 100:.0f}% margin) — auto-decided, no review needed."
    status_line = f"Status: {status}" if status != RuleStatus.REVIEW.value else "Status: ⚠ REVIEW REQUIRED"
    source = evidence.source_doc or "Unknown source"
    page = f", page {evidence.page_number}" if evidence.page_number is not None else ""
    return "\n".join([
        f"Rule {rule.rule_id} — {rule.clause_text} ({tag})",
        status_line,
        f"Extracted value: {evidence.extracted_value}   |   AI confidence: {int(confidence * 100)}%",
        f"Note: {note}",
        f"Source: {source}{page}",
    ])


def extract_required_entities(ast: ASTNode) -> Set[str]:
    """
    Extract all evidence fields referenced by an AST.

    RULE_REF is intentionally excluded because it references
    another rule rather than an evidence entity.
    """

    entities: Set[str] = set()

    if ast.field and ast.op != "RULE_REF":
        entities.add(ast.field)

    if ast.children:
        for child in ast.children:
            entities.update(
                extract_required_entities(child)
            )

    return entities


def extract_rule_references(ast: ASTNode) -> Set[str]:
    """
    Extract RULE_REF dependencies from an AST.
    """

    refs: Set[str] = set()

    if ast.op == "RULE_REF" and ast.field:
        refs.add(ast.field)

    if ast.children:
        for child in ast.children:
            refs.update(
                extract_rule_references(child)
            )

    return refs


# ============================================================
# PROCUREMENT INTELLIGENCE ENGINE
# ============================================================

class ProcurementIntelligenceEngine:

    def __init__(
        self,
        audit_id: str,
        tender_deadline: datetime,
    ):

        self.audit_id = audit_id

        if tender_deadline.tzinfo is None:
            tender_deadline = tender_deadline.replace(
                tzinfo=timezone.utc
            )

        self.tender_deadline = tender_deadline

        # ----------------------------------------------------
        # Knowledge Graph
        # ----------------------------------------------------

        self.evidence_nodes: Dict[str, EvidenceNode] = {}

        self.rule_nodes: Dict[str, RuleNode] = {}

        self.edges: List[DependencyEdge] = []

        # source -> targets
        self.forward_adj: Dict[str, Set[str]] = {}

        # entity -> evidence IDs
        self.entity_to_evidence: Dict[str, List[str]] = {}

        # ----------------------------------------------------
        # Cached deterministic rule state
        # ----------------------------------------------------

        self.current_rule_states: Dict[
            str,
            RuleStatus
        ] = {}

        self.current_rule_evaluations: Dict[
            str,
            RuleEvaluation
        ] = {}

        # ----------------------------------------------------
        # Cryptographic ledger
        # ----------------------------------------------------

        self.ledger: List[AuditEvent] = []

        self._append_to_ledger(
            action="GENESIS",
            actor="SYSTEM",
            payload={
                "audit_id": audit_id,
                "tender_deadline": tender_deadline.isoformat(),
            },
        )

    # ========================================================
    # CRYPTOGRAPHIC AUDIT LEDGER
    # ========================================================

    @staticmethod
    def _canonical_hash(data: dict) -> str:

        canonical = json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )

        return hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest()

    def _append_to_ledger(
        self,
        action: str,
        actor: str,
        payload: dict,
        impact: Optional[dict] = None,
    ) -> str:

        previous_hash = (
            self.ledger[-1].event_hash
            if self.ledger
            else "0000000000000000"
        )

        event_id = f"EVT-{len(self.ledger):04d}"

        timestamp = datetime.now(
            timezone.utc
        ).isoformat()

        event_data = {
            "event_id": event_id,
            "timestamp": timestamp,
            "action": action,
            "actor": actor,
            "payload": payload,
            "impact": impact or {},
            "previous_hash": previous_hash,
        }

        event_hash = self._canonical_hash(
            event_data
        )

        event = AuditEvent(
            **event_data,
            event_hash=event_hash,
        )

        self.ledger.append(event)

        return event_id

    def verify_chain_integrity(
        self,
    ) -> Tuple[bool, str]:

        previous_hash = "0000000000000000"

        for event in self.ledger:

            if event.previous_hash != previous_hash:
                return (
                    False,
                    f"Broken chain link at {event.event_id}",
                )

            reconstructed = {
                "event_id": event.event_id,
                "timestamp": event.timestamp,
                "action": event.action,
                "actor": event.actor,
                "payload": event.payload,
                "impact": event.impact,
                "previous_hash": event.previous_hash,
            }

            calculated_hash = self._canonical_hash(
                reconstructed
            )

            if calculated_hash != event.event_hash:
                return (
                    False,
                    f"Tampering detected at {event.event_id}",
                )

            previous_hash = event.event_hash

        return True, "Chain Verified"

    # ========================================================
    # REGISTRATION
    # ========================================================

    def register_evidence(
        self,
        node: EvidenceNode,
    ):

        # Prevent accidental duplicate node IDs.
        if node.node_id in self.evidence_nodes:
            raise ValueError(
                f"Evidence node '{node.node_id}' already exists."
            )

        self.evidence_nodes[node.node_id] = node

        self.entity_to_evidence.setdefault(
            node.entity_name,
            [],
        ).append(node.node_id)

    def register_rule(
        self,
        rule: RuleNode,
    ):

        if rule.rule_id in self.rule_nodes:
            raise ValueError(
                f"Rule '{rule.rule_id}' already exists."
            )

        self.rule_nodes[rule.rule_id] = rule

        self.current_rule_states[
            rule.rule_id
        ] = RuleStatus.FAIL

        # Automatically construct dependencies
        # from AST evidence fields.
        for entity in extract_required_entities(
            rule.ast
        ):

            for evidence_id in self.entity_to_evidence.get(
                entity,
                [],
            ):

                self.link_dependency(
                    evidence_id,
                    rule.rule_id,
                    "SUPPORTS",
                )

        # Rule -> Rule dependencies
        for referenced_rule in extract_rule_references(
            rule.ast
        ):

            if referenced_rule in self.rule_nodes:

                self.link_dependency(
                    referenced_rule,
                    rule.rule_id,
                    "RULE_DEPENDENCY",
                )

    def rebuild_dependencies(self):

        self.edges.clear()
        self.forward_adj.clear()

        for rid, rule in self.rule_nodes.items():

            entities = extract_required_entities(
                rule.ast
            )

            for entity in entities:

                for evidence_id in self.entity_to_evidence.get(
                    entity,
                    [],
                ):

                    self.link_dependency(
                        evidence_id,
                        rid,
                        "SUPPORTS",
                    )

            refs = extract_rule_references(
                rule.ast
            )

            for ref in refs:

                if ref in self.rule_nodes:

                    self.link_dependency(
                        ref,
                        rid,
                        "RULE_DEPENDENCY",
                    )

    def link_dependency(
        self,
        source_id: str,
        target_id: str,
        relationship: str = "SUPPORTS",
    ):

        edge_id = (
            f"EDGE-{len(self.edges):04d}"
        )

        edge = DependencyEdge(
            edge_id=edge_id,
            source_id=source_id,
            target_id=target_id,
            relationship=relationship,
        )

        self.edges.append(edge)

        self.forward_adj.setdefault(
            source_id,
            set(),
        ).add(target_id)

    # ========================================================
    # EVIDENCE RESOLUTION
    # ========================================================

    def _resolve_entity(
        self,
        entity_name: str,
    ) -> Tuple[
        Any,
        EvidenceStatus,
        List[str],
        float,
    ]:

        node_ids = self.entity_to_evidence.get(
            entity_name,
            [],
        )

        if not node_ids:

            return (
                None,
                EvidenceStatus.UNVERIFIED,
                [],
                0.0,
            )

        active_nodes: List[
            EvidenceNode
        ] = []

        for node_id in node_ids:

            node = self.evidence_nodes[node_id]

            # Explicit rejection
            if node.status == EvidenceStatus.REJECTED:
                continue

            # Temporal validity
            if (
                node.valid_until
                and node.valid_until < self.tender_deadline
            ):

                node.status = EvidenceStatus.EXPIRED

                continue

            active_nodes.append(node)

        if not active_nodes:

            return (
                None,
                EvidenceStatus.EXPIRED,
                node_ids,
                0.0,
            )

        # ----------------------------------------------------
        # Contradiction detection
        # ----------------------------------------------------

        normalized_values = {
            self._normalize_value(
                node.extracted_value
            )
            for node in active_nodes
        }

        confidence = sum(
            node.confidence
            for node in active_nodes
        ) / len(active_nodes)

        if len(normalized_values) > 1:

            for node in active_nodes:
                node.status = EvidenceStatus.CONFLICTING

            return (
                None,
                EvidenceStatus.CONFLICTING,
                [
                    node.node_id
                    for node in active_nodes
                ],
                confidence,
            )

        # ----------------------------------------------------
        # Select strongest evidence
        # ----------------------------------------------------

        primary = max(
            active_nodes,
            key=lambda n: (
                n.status == EvidenceStatus.OFFICER_CONFIRMED,
                n.confidence,
            ),
        )

        if primary.status != EvidenceStatus.OFFICER_CONFIRMED:
            primary.status = EvidenceStatus.VERIFIED

        return (
            primary.extracted_value,
            primary.status,
            [primary.node_id],
            primary.confidence,
        )

    @staticmethod
    def _normalize_value(
        value: Any,
    ) -> str:

        if isinstance(value, float):
            return f"{value:.10f}"

        if isinstance(value, str):
            return value.strip().lower()

        return str(value)

    # ========================================================
    # AST EVALUATION
    # ========================================================

    def evaluate_ast(
        self,
        ast: ASTNode,
        visited_rules: Optional[Set[str]] = None,
    ) -> Tuple[
        RuleStatus,
        List[str],
        str,
        float,
    ]:

        if visited_rules is None:
            visited_rules = set()

        # ----------------------------------------------------
        # AND
        # ----------------------------------------------------

        if ast.op == "AND":

            results = [
                self.evaluate_ast(
                    child,
                    visited_rules,
                )
                for child in (
                    ast.children or []
                )
            ]

            statuses = [
                result[0]
                for result in results
            ]

            evidence_ids = [
                evidence_id
                for result in results
                for evidence_id in result[1]
            ]

            confidence = (
                sum(
                    result[3]
                    for result in results
                ) / len(results)
                if results
                else 1.0
            )

            if RuleStatus.FAIL in statuses:
                return (
                    RuleStatus.FAIL,
                    evidence_ids,
                    "AND condition failed.",
                    confidence,
                )

            if RuleStatus.REVIEW in statuses:
                return (
                    RuleStatus.REVIEW,
                    evidence_ids,
                    "AND condition contains unresolved evidence.",
                    confidence,
                )

            return (
                RuleStatus.PASS,
                evidence_ids,
                "All AND conditions passed.",
                confidence,
            )

        # ----------------------------------------------------
        # OR
        # ----------------------------------------------------

        if ast.op == "OR":

            results = [
                self.evaluate_ast(
                    child,
                    visited_rules,
                )
                for child in (
                    ast.children or []
                )
            ]

            evidence_ids = [
                evidence_id
                for result in results
                for evidence_id in result[1]
            ]

            confidence = (
                sum(
                    result[3]
                    for result in results
                ) / len(results)
                if results
                else 1.0
            )

            if any(
                result[0] == RuleStatus.PASS
                for result in results
            ):

                return (
                    RuleStatus.PASS,
                    evidence_ids,
                    "At least one OR condition passed.",
                    confidence,
                )

            if any(
                result[0] == RuleStatus.REVIEW
                for result in results
            ):

                return (
                    RuleStatus.REVIEW,
                    evidence_ids,
                    "OR condition contains unresolved evidence.",
                    confidence,
                )

            return (
                RuleStatus.FAIL,
                evidence_ids,
                "All OR conditions failed.",
                confidence,
            )

        # ----------------------------------------------------
        # NOT
        # ----------------------------------------------------

        if ast.op == "NOT":

            if not ast.children:
                return (
                    RuleStatus.FAIL,
                    [],
                    "NOT requires a child condition.",
                    0.0,
                )

            status, evidence, reason, confidence = (
                self.evaluate_ast(
                    ast.children[0],
                    visited_rules,
                )
            )

            if status == RuleStatus.REVIEW:

                return (
                    RuleStatus.REVIEW,
                    evidence,
                    "NOT condition depends on unresolved evidence.",
                    confidence,
                )

            if status == RuleStatus.PASS:

                return (
                    RuleStatus.FAIL,
                    evidence,
                    "NOT condition failed because child passed.",
                    confidence,
                )

            return (
                RuleStatus.PASS,
                evidence,
                "NOT condition passed because child failed.",
                confidence,
            )

        # ----------------------------------------------------
        # RULE REFERENCE
        # ----------------------------------------------------

        if ast.op == "RULE_REF":

            if not ast.field:
                return (
                    RuleStatus.FAIL,
                    [],
                    "RULE_REF missing rule ID.",
                    0.0,
                )

            if ast.field in visited_rules:

                return (
                    RuleStatus.REVIEW,
                    [],
                    "Circular rule dependency detected.",
                    0.0,
                )

            referenced = self.rule_nodes.get(
                ast.field
            )

            if referenced is None:

                return (
                    RuleStatus.FAIL,
                    [],
                    f"Referenced rule '{ast.field}' does not exist.",
                    0.0,
                )

            new_visited = set(visited_rules)
            new_visited.add(ast.field)

            return self.evaluate_ast(
                referenced.ast,
                new_visited,
            )

        # ----------------------------------------------------
        # LEAF ENTITY
        # ----------------------------------------------------

        value, status, evidence_ids, confidence = (
            self._resolve_entity(
                ast.field
            )
        )

        if status == EvidenceStatus.CONFLICTING:

            return (
                RuleStatus.REVIEW,
                evidence_ids,
                f"Conflicting evidence for '{ast.field}'.",
                confidence,
            )

        if status in (
            EvidenceStatus.UNVERIFIED,
            EvidenceStatus.EXPIRED,
        ):

            return (
                RuleStatus.REVIEW,
                evidence_ids,
                f"Evidence unavailable or expired for '{ast.field}'.",
                confidence,
            )

        if value is None:

            if ast.op == "EXISTS":
                return (
                    RuleStatus.FAIL,
                    evidence_ids,
                    f"Required evidence '{ast.field}' does not exist.",
                    0.0,
                )

            return (
                RuleStatus.FAIL,
                evidence_ids,
                f"Missing evidence for '{ast.field}'.",
                0.0,
            )

        # ----------------------------------------------------
        # EXISTS
        # ----------------------------------------------------

        if ast.op == "EXISTS":

            return (
                RuleStatus.PASS,
                evidence_ids,
                f"Evidence '{ast.field}' exists.",
                confidence,
            )

        # ----------------------------------------------------
        # NUMERIC OPERATORS
        # ----------------------------------------------------

        if ast.op in {
            ">=",
            ">",
            "<=",
            "<",
        }:

            try:

                left = float(value)
                right = float(ast.value)

            except (
                TypeError,
                ValueError,
            ):

                return (
                    RuleStatus.REVIEW,
                    evidence_ids,
                    f"Non-numeric comparison for '{ast.field}'.",
                    confidence,
                )

            if ast.op == ">=":
                passed = left >= right

            elif ast.op == ">":
                passed = left > right

            elif ast.op == "<=":
                passed = left <= right

            else:
                passed = left < right

            borderline, margin = check_margin(left, right, confidence)
            if borderline:
                return (
                    RuleStatus.REVIEW,
                    evidence_ids,
                    f"{left} {ast.op} {right} is within {margin * 100:.1f}% of the cutoff; officer review required.",
                    confidence,
                )

            return (
                RuleStatus.PASS if passed else RuleStatus.FAIL,
                evidence_ids,
                f"{left} {ast.op} {right} evaluated deterministically.",
                confidence,
            )

        # ----------------------------------------------------
        # EQUALITY
        # ----------------------------------------------------

        if ast.op in {
            "==",
            "!=",
        }:

            left = self._normalize_value(value)
            right = self._normalize_value(ast.value)

            equal = left == right

            passed = (
                equal
                if ast.op == "=="
                else not equal
            )

            return (
                RuleStatus.PASS if passed else RuleStatus.FAIL,
                evidence_ids,
                f"Equality comparison evaluated deterministically.",
                confidence,
            )

        # ----------------------------------------------------
        # DATE COMPARISON
        # ----------------------------------------------------

        if ast.op in {
            "DATE_BEFORE",
            "DATE_AFTER",
        }:

            try:

                actual = self._parse_datetime(
                    value
                )

                target = self._parse_datetime(
                    ast.value
                )

            except (
                TypeError,
                ValueError,
            ):

                return (
                    RuleStatus.REVIEW,
                    evidence_ids,
                    "Invalid date format.",
                    confidence,
                )

            if ast.op == "DATE_BEFORE":
                passed = actual < target
            else:
                passed = actual > target

            return (
                RuleStatus.PASS if passed else RuleStatus.FAIL,
                evidence_ids,
                f"Date comparison evaluated deterministically.",
                confidence,
            )

        # ----------------------------------------------------
        # UNKNOWN OPERATOR
        # ----------------------------------------------------

        return (
            RuleStatus.REVIEW,
            evidence_ids,
            f"Unsupported operator '{ast.op}'.",
            confidence,
        )

    @staticmethod
    def _parse_datetime(
        value: Any,
    ) -> datetime:

        if isinstance(value, datetime):
            return value

        parsed = datetime.fromisoformat(
            str(value).replace(
                "Z",
                "+00:00",
            )
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed

    # ========================================================
    # SINGLE RULE EVALUATION
    # ========================================================

    def evaluate_rule(
        self,
        rule_id: str,
    ) -> RuleEvaluation:

        if rule_id not in self.rule_nodes:
            raise KeyError(
                f"Rule '{rule_id}' not found."
            )

        rule = self.rule_nodes[rule_id]

        status, evidence_ids, reasoning, confidence = (
            self.evaluate_ast(
                rule.ast,
                {rule_id},
            )
        )

        return RuleEvaluation(
            rule_id=rule_id,
            status=status,
            evidence_ids=list(
                dict.fromkeys(evidence_ids)
            ),
            reasoning=reasoning,
            confidence_score=round(
                confidence,
                4,
            ),
        )

    # ========================================================
    # FULL COMPILATION
    # ========================================================

    def evaluate_all_rules(self) -> Dict[
        str,
        RuleEvaluation,
    ]:

        evaluations = {}

        # Deterministic ordering.
        for rule_id in sorted(
            self.rule_nodes.keys()
        ):

            evaluation = self.evaluate_rule(
                rule_id
            )

            evaluations[
                rule_id
            ] = evaluation

            self.current_rule_states[
                rule_id
            ] = evaluation.status

            self.current_rule_evaluations[
                rule_id
            ] = evaluation

        return evaluations

    # ========================================================
    # OVERALL COMPLIANCE
    # ========================================================

    def calculate_overall_compliance(
        self,
        evaluations: Optional[
            Dict[str, RuleEvaluation]
        ] = None,
    ) -> DecisionResult:

        if evaluations is None:

            # Make sure state exists.
            if (
                len(
                    self.current_rule_evaluations
                )
                != len(self.rule_nodes)
            ):
                evaluations = (
                    self.evaluate_all_rules()
                )

            else:
                evaluations = (
                    self.current_rule_evaluations
                )

        achieved = 0.0
        total_weight = 0.0

        mandatory_failures = []
        review_triggers = []
        passed_rules = []

        for rule_id, rule in self.rule_nodes.items():

            total_weight += rule.weight

            evaluation = evaluations.get(
                rule_id
            )

            status = (
                evaluation.status
                if evaluation
                else RuleStatus.FAIL
            )

            if status == RuleStatus.PASS:

                achieved += rule.weight

                passed_rules.append(
                    rule_id
                )

            elif (
                status == RuleStatus.FAIL
                and rule.is_mandatory
            ):

                mandatory_failures.append(
                    rule_id
                )

            elif status == RuleStatus.REVIEW:

                review_triggers.append(
                    rule_id
                )

        score = (
            achieved / total_weight * 100
            if total_weight > 0
            else 0.0
        )

        if mandatory_failures:
            decision = "FAIL"

        elif review_triggers:
            decision = "REVIEW"

        else:
            decision = "PASS"

        return DecisionResult(
            compliance_score=round(
                score,
                2,
            ),
            decision=decision,
            mandatory_failures=mandatory_failures,
            review_triggers=review_triggers,
            passed_rules=passed_rules,
            evaluated_rules=len(
                self.rule_nodes
            ),
        )

    # ========================================================
    # BLAST RADIUS
    # ========================================================

    def analyze_blast_radius(
        self,
        target_node_id: str,
    ) -> dict:

        affected_rules: Set[str] = set()

        queue = deque(
            [target_node_id]
        )

        visited: Set[str] = set()

        while queue:

            current = queue.popleft()

            if current in visited:
                continue

            visited.add(current)

            for dependent in self.forward_adj.get(
                current,
                set(),
            ):

                if dependent in self.rule_nodes:

                    affected_rules.add(
                        dependent
                    )

                queue.append(
                    dependent
                )

        mandatory_count = sum(
            1
            for rule_id in affected_rules
            if self.rule_nodes[
                rule_id
            ].is_mandatory
        )

        if mandatory_count > 0:

            sensitivity = (
                "HIGH - impacts mandatory compliance"
            )

        elif len(affected_rules) > 2:

            sensitivity = (
                "MODERATE - impacts multiple rules"
            )

        else:

            sensitivity = (
                "LOW - limited decision impact"
            )

        return {
            "target_node": target_node_id,
            "blast_radius_size": len(
                affected_rules
            ),
            "mandatory_rules_affected": mandatory_count,
            "affected_rules": sorted(
                affected_rules
            ),
            "decision_sensitivity": sensitivity,
        }

    # ========================================================
    # TRUE INCREMENTAL PROPAGATION
    # ========================================================

    def incremental_recalculate(
        self,
        changed_node_id: str,
        new_value: Any,
        actor: str,
    ) -> dict:

        if changed_node_id not in self.evidence_nodes:

            raise KeyError(
                f"Evidence node '{changed_node_id}' not found."
            )

        # Ensure baseline state exists.
        self.evaluate_all_rules()

        old_decision = (
            self.calculate_overall_compliance()
        )

        node = self.evidence_nodes[
            changed_node_id
        ]

        old_value = node.extracted_value

        # ----------------------------------------------------
        # Mutate evidence
        # ----------------------------------------------------

        node.extracted_value = new_value

        node.status = (
            EvidenceStatus.OFFICER_CONFIRMED
        )

        # ----------------------------------------------------
        # Find affected subgraph
        # ----------------------------------------------------

        radius = self.analyze_blast_radius(
            changed_node_id
        )

        affected_rules = set(
            radius["affected_rules"]
        )

        # ----------------------------------------------------
        # Recalculate ONLY affected rules
        # ----------------------------------------------------

        updated_evaluations = {}

        # Topological-ish ordering:
        # evaluate referenced rules before dependents.
        ordered = self._order_affected_rules(
            affected_rules
        )

        for rule_id in ordered:

            evaluation = self.evaluate_rule(
                rule_id
            )

            self.current_rule_states[
                rule_id
            ] = evaluation.status

            self.current_rule_evaluations[
                rule_id
            ] = evaluation

            updated_evaluations[
                rule_id
            ] = evaluation

        new_decision = (
            self.calculate_overall_compliance()
        )

        impact = {
            "changed_node": changed_node_id,
            "affected_subgraph": len(
                affected_rules
            ),
            "affected_rules": sorted(
                affected_rules
            ),
            "old_decision": old_decision.decision,
            "new_decision": new_decision.decision,
            "old_score": old_decision.compliance_score,
            "new_score": new_decision.compliance_score,
            "score_delta": round(
                new_decision.compliance_score
                - old_decision.compliance_score,
                2,
            ),
        }

        self._append_to_ledger(
            action="EVIDENCE_CORRECTION",
            actor=actor,
            payload={
                "node": changed_node_id,
                "old_value": old_value,
                "new_value": new_value,
            },
            impact=impact,
        )

        return {
            **impact,
            "updated_evaluations": {
                rule_id: evaluation.model_dump(
                    mode="json"
                )
                for rule_id, evaluation
                in updated_evaluations.items()
            },
        }

    def _order_affected_rules(
        self,
        affected_rules: Set[str],
    ) -> List[str]:

        ordered: List[str] = []
        remaining = set(
            affected_rules
        )

        # Repeatedly select rules whose RULE_REF
        # dependencies have already been processed.
        while remaining:

            progress = False

            for rule_id in list(
                remaining
            ):

                dependencies = (
                    extract_rule_references(
                        self.rule_nodes[
                            rule_id
                        ].ast
                    )
                )

                relevant_dependencies = (
                    dependencies
                    & affected_rules
                )

                if relevant_dependencies.issubset(
                    set(ordered)
                ):

                    ordered.append(
                        rule_id
                    )

                    remaining.remove(
                        rule_id
                    )

                    progress = True

            if not progress:

                # Circular dependency.
                ordered.extend(
                    sorted(
                        remaining
                    )
                )

                break

        return ordered

    # ========================================================
    # COUNTERFACTUAL SIMULATION
    # ========================================================

    def optimize_compliance_intervention(
        self,
        candidate_evidence: List[EvidenceNode],
    ) -> dict:

        self.evaluate_all_rules()

        baseline = (
            self.calculate_overall_compliance()
        )

        if baseline.decision == "PASS":

            return {
                "status": "ALREADY_COMPLIANT",
                "current_decision": "PASS",
                "projected_decision": "PASS",
                "score_improvement": 0.0,
                "required_interventions": [],
            }

        # ----------------------------------------------------
        # Side-effect-free copy
        # ----------------------------------------------------

        simulation = copy.deepcopy(
            self
        )

        # Candidate evidence represents a hypothetical
        # replacement for the corresponding entity.
        #
        # This avoids creating artificial contradictions
        # between existing evidence and the proposed fix.

        for candidate in candidate_evidence:

            existing_ids = (
                simulation.entity_to_evidence.get(
                    candidate.entity_name,
                    [],
                )
            )

            for existing_id in existing_ids:

                simulation.evidence_nodes[
                    existing_id
                ].status = EvidenceStatus.REJECTED

            # Avoid duplicate node ID.
            if (
                candidate.node_id
                in simulation.evidence_nodes
            ):

                candidate = copy.deepcopy(
                    candidate
                )

                candidate.node_id = (
                    f"HYP-{candidate.node_id}"
                )

            simulation.register_evidence(
                candidate
            )

        simulation.rebuild_dependencies()

        simulated_evaluations = (
            simulation.evaluate_all_rules()
        )

        simulated_decision = (
            simulation.calculate_overall_compliance(
                simulated_evaluations
            )
        )

        flipped_rules = []

        for rule_id in self.rule_nodes:

            old_status = (
                self.current_rule_states.get(
                    rule_id,
                    RuleStatus.FAIL,
                )
            )

            new_status = (
                simulated_evaluations[
                    rule_id
                ].status
            )

            if old_status != new_status:

                flipped_rules.append(
                    {
                        "rule_id": rule_id,
                        "from": old_status.value,
                        "to": new_status.value,
                    }
                )

        return {
            "status": "SIMULATED",
            "current_decision": baseline.decision,
            "projected_decision": simulated_decision.decision,
            "current_score": baseline.compliance_score,
            "projected_score": simulated_decision.compliance_score,
            "score_improvement": round(
                simulated_decision.compliance_score
                - baseline.compliance_score,
                2,
            ),
            "required_interventions": [
                candidate.entity_name
                for candidate in candidate_evidence
            ],
            "flipped_rules": flipped_rules,
            "side_effect_free": True,
        }

    # ========================================================
    # SNAPSHOT
    # ========================================================

    def get_snapshot(self) -> dict:

        evaluations = (
            self.evaluate_all_rules()
        )

        compliance = (
            self.calculate_overall_compliance(
                evaluations
            )
        )

        return {
            "audit_id": self.audit_id,
            "compliance": compliance.model_dump(
                mode="json"
            ),
            "evidence": [
                node.model_dump(
                    mode="json"
                )
                for node in self.evidence_nodes.values()
            ],
            "rules": [
                rule.model_dump(
                    mode="json"
                )
                for rule in self.rule_nodes.values()
            ],
            "dependencies": [
                edge.model_dump(
                    mode="json"
                )
                for edge in self.edges
            ],
            "ledger_size": len(
                self.ledger
            ),
            }
