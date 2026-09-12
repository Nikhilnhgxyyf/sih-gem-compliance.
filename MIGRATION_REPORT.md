# Migration and Stabilization Report

## Scope
This report records the post-change verification of the causal-temporal upgrade and Decision Story / Procurement X-Ray UI. It does not claim live government verification or a production certification.

## Files changed
- `backend/schemas.py` — Evidence DNA provenance, temporal states, tender-version and evaluation metadata.
- `backend/engine.py` — deterministic temporal evaluation, DNA, causal graph/path, Decision Story, isolated simulation, criticality and replay.
- `backend/main.py` — compatible v3 audit APIs, synthetic demo seed, simulation endpoint, and Decision Capsule routes.
- `backend/audit_store.py` — SQLite persistence adapter for sessions, snapshots, normalized audit records, simulations, and capsules.
- `backend/test_engine.py` — deterministic engine and API coverage.
- `frontend/index.html`, `frontend/app.js`, `frontend/style.css` — synthetic demo action, Decision Story Mode, and Decision Skeleton/X-Ray interaction.
- `README.md`, `docs/ARCHITECTURE.md`, `docs/INVENTION_DISCLOSURE.md` — product and technical documentation.

## APIs added
| Endpoint | Purpose |
|---|---|
| `GET /api/v3/evidence/{evidence_id}/dna` | Evidence provenance, temporal state and fingerprint. |
| `GET /api/v3/audits/{audit_id}/timeline` | Evidence validity intervals at evaluation time. |
| `GET /api/v3/audits/{audit_id}/decision-dna` | Canonical decision-state fingerprint. |
| `GET /api/v3/audits/{audit_id}/causal-graph` | Causal nodes and edges. |
| `GET /api/v3/decision/{audit_id}/causal-path` | Evidence-to-decision dependency paths. |
| `GET /api/v3/audits/{audit_id}/decision-story` | Deterministic, identifier-citing officer explanation and X-Ray skeleton graph. |
| `GET /api/v3/audits/{audit_id}/critical-evidence` | Single-removal criticality approximation. |
| `GET /api/v3/audits/{audit_id}/replay` | Reconstructed decision and mismatch information. |
| `GET /api/v3/audits/{audit_id}/integrity` | Audit-event hash-chain verification. |
| `POST /api/v3/simulations` | Isolated `REMOVE_EVIDENCE` scenario. |
| `POST /api/v3/demo/seed` | Clearly marked synthetic demo audit. |
| `POST /api/v3/audits/{audit_id}/capsule/save` | Persist a portable Decision Capsule. |
| `GET /api/v3/audits/{audit_id}/capsule` / `export` | Retrieve or export a stored capsule. |
| `POST /api/v3/audits/capsule/import` | Integrity-check and restore a capsule. |
| `POST /api/v3/audits/{audit_id}/capsule/replay` / `verify` | Replay and integrity-verify stored state. |

## Models added or extended
- Added `TemporalState`.
- Extended `EvidenceNode` with Evidence DNA, extraction provenance, confidence, relationships, and fingerprint fields.
- Extended `RuleNode` with version/effective-period/source metadata and `requires_temporal_validity`.
- Extended `RuleEvaluation` with evaluated timestamp, rule version and deterministic input context.

## Compatibility and breaking changes
- **No intentional breaking API changes.** Existing `/api/v3/ingest-documents`, `/api/v3/officer-override`, `/api/v3/blast-radius/{node_id}`, `/api/v3/counterfactual`, `/api/v3/state`, and graph/evaluation response fields remain available.
- Blast-radius retains its former response fields and adds a `simulation` object.
- The frontend is a static HTML/CSS/JavaScript application and has no package manager build step; JavaScript syntax and static-server delivery were validated instead.

## Deployment changes
- No external database dependency is required; SQLite is part of Python’s standard library.
- The active in-memory session remains for UI responsiveness, with persistent SQLite snapshots and Decision Capsules for restart recovery.
- SQLite local storage is appropriate for this prototype, not shared multi-instance production persistence.
- Configure `ALLOWED_ORIGINS` for the deployed frontend origin(s).

## Required environment variables
| Variable | Required | Use |
|---|---|---|
| `GEMINI_API_KEY` | Required only for live Gemini document extraction | Server-side Gemini client initialization. |
| `GEMINI_MODEL` | Optional | Overrides the primary Gemini extraction model. |
| `GEMINI_FALLBACK_MODEL` | Optional | Overrides the fallback Gemini extraction model. |
| `ALLOWED_ORIGINS` | Recommended for deployment | Comma-separated CORS origins. |
| `AUDIT_DB_PATH` | Optional | Persistent SQLite database path; defaults to `backend/data/gem_audit.db`. |
| `DEMO_FIXTURE_ONLY` | Optional | Limits demo extraction to recognised fixtures. |

## Verification completed
- Backend unit tests and FastAPI TestClient API smoke tests passed.
- Restart recovery was verified in two separate Python processes against the same temporary `AUDIT_DB_PATH`.
- Python syntax compilation passed.
- Static frontend JavaScript syntax and HTTP serving passed.
- Existing JSON ingestion, evaluation, evidence graph, officer override, counterfactual, and blast-radius contracts are exercised by the automated suite/smoke test.
- Live multipart document extraction cannot be executed in this environment without a configured `GEMINI_API_KEY` and real upload artefacts. The failure path remains explicit and deterministic audit endpoints remain usable without the key.

## Static audit findings
- Removed a duplicate `SimpleCounterfactualRequest` declaration found during review.
- No circular imports were identified in the backend import graph.
- No frontend package/build configuration exists; this is an intentional repository architecture limitation, not a build failure.
- No API keys are present in frontend source; Gemini configuration is read from server-side environment variables.
