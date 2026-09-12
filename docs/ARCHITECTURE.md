# Causal Temporal Procurement Intelligence Architecture

GeM AI Auditor is a deterministic procurement-decision support prototype. AI may extract candidate facts; it does not decide compliance.

```text
Frontend → FastAPI API Layer → Audit Orchestrator → Document Intelligence
                                      ↓
Evidence DNA → Temporal Engine → Deterministic Rule Engine → Causal Graph
                                      ↓                         ↓
                              Decision DNA ← Decision Engine → Replay / Simulation
                                      ↓
                            Tamper-evident Audit Event Chain
```

## Data flow
1. Ingestion hashes each source document and creates evidence nodes with source, page, confidence and extraction provenance.
2. Evidence DNA canonicalizes structured provenance into a SHA-256 fingerprint. It is an integrity identifier, not proof of legal correctness.
3. The temporal engine classifies evidence at a supplied timestamp as `VALID_AT_TIME`, `NOT_YET_VALID`, `EXPIRED_AT_TIME`, `UNKNOWN_VALIDITY`, or `CONFLICTING_AT_TIME`; missing dates are never inferred.
4. The rule engine evaluates ASTs deterministically and returns inputs, evidence IDs, reason, status, timestamp, and rule version.
5. The causal graph connects evidence, rules, rule evaluations, and the decision. Dependency traversal powers blast radius and critical-evidence ranking.
6. A simulation deep-copies the audit state, so removing evidence cannot overwrite actual evidence or ledger history.
7. Decision DNA canonicalizes rule/evidence state and hashes it. Replay evaluates a copied state and reports differences.

## Failure modes
- **Gemini/extraction unavailable:** ingestion reports a clear failure; already-ingested deterministic audits remain usable.
- **Date absent:** temporal state is `UNKNOWN_VALIDITY`; temporal-required rules request review.
- **Conflicting evidence:** rules receive `REVIEW`; this is a contradiction signal, not a fraud assertion.
- **Invalid rule/data type:** the deterministic evaluator returns `REVIEW`, not a silent pass.
- **Tampered audit event:** hash-chain verification reports the event/link failure.

## Deployment and limits
The active working session remains in memory for low-latency UI operations, while `SQLiteAuditStore` persists audit sessions, evidence, rules, evaluations, decisions, events, simulations, and Decision Capsules at `AUDIT_DB_PATH`. SQLite is local prototype persistence, not a multi-instance shared database. CORS is configured with `ALLOWED_ORIGINS`; secrets remain server-side environment configuration.
