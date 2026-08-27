from enum import Enum
from typing import List, Dict, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


# ============================================================
# ENUMS
# ============================================================

class EvidenceStatus(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    CONFLICTING = "CONFLICTING"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"
    OFFICER_CONFIRMED = "OFFICER_CONFIRMED"


class RuleStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"


# ============================================================
# RULE AST
# ============================================================

class ASTNode(BaseModel):
    """
    Executable representation of a procurement rule.

    Supported operators:
        AND
        OR
        NOT
        >=
        >
        <=
        <
        ==
        !=
        EXISTS
        DATE_BEFORE
        DATE_AFTER
        RULE_REF
    """

    op: str

    field: Optional[str] = None
    value: Optional[Any] = None
    children: Optional[List["ASTNode"]] = None


# ============================================================
# EVIDENCE
# ============================================================

class EvidenceNode(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    node_id: str
    entity_name: str
    extracted_value: Any

    confidence: float = Field(
        ge=0.0,
        le=1.0
    )

    status: EvidenceStatus = EvidenceStatus.UNVERIFIED

    source_doc: str

    page_number: Optional[int] = None

    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None


# ============================================================
# PROCUREMENT RULE
# ============================================================

class RuleNode(BaseModel):
    rule_id: str

    clause_text: str

    ast: ASTNode

    weight: float = Field(
        default=10.0,
        ge=0.0
    )

    is_mandatory: bool = True


# ============================================================
# DEPENDENCY GRAPH
# ============================================================

class DependencyEdge(BaseModel):
    edge_id: str

    source_id: str

    target_id: str

    relationship: str

    weight: float = 1.0


# ============================================================
# RULE EVALUATION
# ============================================================

class RuleEvaluation(BaseModel):
    rule_id: str

    status: RuleStatus

    evidence_ids: List[str] = []

    reasoning: str

    confidence_score: float = Field(
        ge=0.0,
        le=1.0
    )


# ============================================================
# OVERALL DECISION
# ============================================================

class DecisionResult(BaseModel):
    compliance_score: float

    decision: str

    mandatory_failures: List[str]

    review_triggers: List[str]

    passed_rules: List[str] = []

    evaluated_rules: int = 0


# ============================================================
# AUDIT LEDGER
# ============================================================

class AuditEvent(BaseModel):
    event_id: str

    timestamp: str

    action: str

    actor: str

    payload: Dict[str, Any]

    impact: Dict[str, Any] = {}

    previous_hash: str

    event_hash: str


# ============================================================
# API REQUEST MODELS
# ============================================================

class EvidenceCorrectionRequest(BaseModel):
    node_id: str
    new_value: Any
    actor: str


class CounterfactualRequest(BaseModel):
    evidence: List[EvidenceNode]


# ============================================================
# COMPLETE AUDIT SNAPSHOT
# ============================================================

class AuditSnapshot(BaseModel):
    audit_id: str

    compliance: DecisionResult

    evidence: List[EvidenceNode]

    rules: List[RuleNode]

    dependencies: List[DependencyEdge]

    ledger_size: int
