from enum import Enum
from typing import List, Dict, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


# ============================================================
# ENUMS
# ============================================================

class EvidenceStatus(str, Enum):
    AI_EXTRACTED = "AI_EXTRACTED"
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    CONFLICTING = "CONFLICTING"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"
    OFFICER_CONFIRMED = "OFFICER_CONFIRMED"
    SIMULATED = "SIMULATED"


class RuleStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"


class TemporalState(str, Enum):
    VALID_AT_TIME = "VALID_AT_TIME"
    NOT_YET_VALID = "NOT_YET_VALID"
    EXPIRED_AT_TIME = "EXPIRED_AT_TIME"
    UNKNOWN_VALIDITY = "UNKNOWN_VALIDITY"
    CONFLICTING_AT_TIME = "CONFLICTING_AT_TIME"


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
    document_hash: Optional[str] = None

    page_number: Optional[int] = None

    source_quote: Optional[str] = None

    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    extraction_timestamp: Optional[datetime] = None
    originating_event: Optional[str] = None
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    # Evidence DNA / provenance fields. Optional values preserve existing ingest
    # contracts while allowing richer extractors to populate them.
    bidder_id: Optional[str] = None
    normalized_value: Optional[Any] = None
    evidence_type: Optional[str] = None
    source_document_id: Optional[str] = None
    bounding_box: Optional[Dict[str, float]] = None
    ocr_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    semantic_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    source_timestamp: Optional[datetime] = None
    issue_date: Optional[datetime] = None
    issuer: Optional[str] = None
    provenance: str = "EXTRACTED_EVIDENCE"
    extraction_model: Optional[str] = None
    extraction_version: Optional[str] = None
    verification_method: Optional[str] = None
    parent_evidence_ids: List[str] = Field(default_factory=list)
    derived_evidence_ids: List[str] = Field(default_factory=list)
    conflicting_evidence_ids: List[str] = Field(default_factory=list)
    dependent_rule_ids: List[str] = Field(default_factory=list)
    evidence_fingerprint: Optional[str] = None


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
    version: str = "1.0"
    effective_from: Optional[datetime] = None
    effective_until: Optional[datetime] = None
    tender_id: Optional[str] = None
    tender_version: str = "1.0"
    source_page: Optional[int] = None
    source_document: Optional[str] = None
    created_at: Optional[datetime] = None
    requires_temporal_validity: bool = False


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
    evaluated_at: Optional[datetime] = None
    rule_version: Optional[str] = None
    inputs: Dict[str, Any] = Field(default_factory=dict)


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

    nonce: str

    event_hash: str


# ============================================================
# API REQUEST MODELS
# ============================================================

class EvidenceCorrectionRequest(BaseModel):
    node_id: str
    new_value: Any
    actor: str
    reason: str = Field(min_length=3, max_length=1000)


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
