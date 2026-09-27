# GEMA — Procurement Intelligence Engine

**AI-Powered Integrated Bid Compliance Verification Platform for GeM Procurement**
Smart India Hackathon 2026 · Problem Statement SIH26100 · Team Flamingo Group

[Live app](https://auditor-kappa.vercel.app) · [API base](https://sih-gem-compliance.onrender.com) · [Health check](https://sih-gem-compliance.onrender.com/api/v3/health)

> The backend runs on Render's free tier. If it's been idle, the first request can take 20–30 seconds to wake up. That's a cold start, not a bug — worth knowing before you click through it live.

---

## The problem

GeM procurement officers manually cross-check every bidder's PAN, GSTIN, turnover certificates and technical-eligibility documents against a tender's own clauses — for every tender, every bidder, every renewal cycle. It's slow, and a missed cross-check goes one of two ways: a wrongful rejection an MSME has to fight, or a wrongful pass that turns into a CAG audit finding two years later.

There's a second, less obvious failure mode: the tender's *own rules* can be the problem. A turnover band written as "₹137–140 Cr" instead of a round "₹100 Cr minimum" isn't a typo — it's a clause sized to fit exactly one bidder. Most compliance tools only ever check whether a bidder passes. GEMA also checks whether the rules themselves look rigged, before a single bidder is evaluated against them.

## The one design decision everything else follows from

**AI touches facts. Deterministic logic decides.**

Gemini reads the uploaded documents and pulls out structured facts — a number, a date, a registration ID — each one tied to the exact source file, page and line it came from, with a confidence score attached. It never sees the tender's rules and never makes a pass/fail call. A separate, hand-written AST rule engine evaluates every clause against those facts, deterministically. Same evidence in, same verdict out, every time — tonight, or during a re-run six months from now.

This split is what makes the audit trail defensible. If someone asks "why did this bidder fail R002," the answer traces backward through the rule tree to a specific extracted fact, to a specific PDF page, to a specific SHA-256 hash. Nowhere in that chain is the answer "the AI decided."

## How a bid moves through the system

1. **Documents in.** Tender PDF + bidder PDFs, uploaded as-is — scans, portal exports, whatever the department actually hands over.
2. **AI extraction.** Gemini returns schema-constrained JSON per document: entity, value, source page, confidence. No free text, no summarizing.
3. **Evidence.** Every extracted fact becomes an Evidence Node — source document, page, line, document hash, confidence — traceable back to the original file.
4. **Rule / AST engine.** Tender clauses compile into an AST (`>=`, `AND`, `OR`, `DATE_AFTER`, `EXISTS`, …) and get evaluated against the evidence. No LLM in this step.
5. **Conflict & risk.** Two documents disagreeing on the same fact gets flagged `CONFLICTING`, never averaged or guessed. A value within 15% of a legal cutoff auto-routes to a human, regardless of how confident the extraction was.
6. **Decision.** PASS / FAIL / REVIEW, with a compliance score and the specific reasoning behind every mandatory requirement.
7. **Audit ledger.** Every ingestion, correction and override is appended as a SHA-256 hash-chained event. `GET /api/v3/audit-chain` re-verifies the whole chain on request — you don't have to take the UI's word for it.

## What's actually built

**Evidence graph.** Evidence nodes and rule nodes as a live graph, rendered with vis.js. If the CDN can't load — no internet at the venue, say — it degrades to a plain list view instead of a blank screen.

**Officer correction, with propagation.** An officer can override any extracted value but has to give a verification reason. The correction is logged to the ledger, and only the rules that actually depend on that value get recomputed — not the whole audit.

**Blast radius analyzer.** `GET /api/v3/blast-radius/{node_id}` — before committing a correction, see exactly which rules sit downstream of that piece of evidence, how many are mandatory, and how many compliance points are at risk if the value turns out to be wrong.

**Counterfactual simulation.** "If this bidder's turnover were ₹2 Cr higher, would R001 flip?" Runs the projection without touching real audit state.

**Bidder comparison.** Every bidder ingested against the same compiled tender ruleset, side by side, ranked by score. The comparison is only valid because they share one compiled ruleset — GEMA won't let you line up bidders from two different tenders.

**Tamper-evident ledger.** SHA-256 canonical hashing (`json.dumps(..., sort_keys=True, default=str)`), each event chained to the previous event's hash, Merkle root exposed via the state endpoint. Built with RTI disclosure in mind, not just as an internal log.

**Tender Integrity Gate.** When a tender is uploaded, GEMA silently runs two checks against the compiled ruleset before any bidder is evaluated:
- *Restrictiveness Index* — runs the tender's own rules against a synthetic population of firms sized for the project, to see if the combined ruleset is unusually hard to clear.
- *Outlier rule detection* — checks whether any single clause behaves nothing like its siblings in the same document.

  A flagged rule hard-blocks ingestion with `HTTP 409` before any bidder gets evaluated. An officer has to log a specific written reason to proceed. That override is appended to its own hash-chained tender-level ledger — separate from the per-bidder evidence ledger — and generates **Annexure B**, an RTI-style PDF documenting what was flagged, who overrode it, and why.

**Precedent retrieval.** The moment a tender gets blocked, GEMA searches past override decisions for similar cases and surfaces the closest matches, so the officer isn't deciding blind. Two retrieval modes live in `precedent_rag.py`:
  - Semantic — Gemini `text-embedding-004`, cosine similarity, when a client is available.
  - Deterministic fallback — Jaccard token-overlap, no network dependency. This is what actually runs in the current deployment; `main.py` doesn't pass a client into the retrieval calls yet.

  Every result is tagged with which method produced it, so the UI never dresses up a keyword match as a semantic one.

**Two audit-ready PDFs**, both generated with ReportLab:
  - *Annexure A* — per-bidder rejection justification, every mandatory failure traced to its evidence, GFR 2017 Rule 149-aligned.
  - *Annexure B* — the tender-integrity override justification described above.

Frontend is one HTML file, vanilla JS, no build step, eight working pages: Ingest, Overview, Bidder Comparison, Evidence Graph, Rule Engine, Risk & Impact, Counterfactual, Audit Ledger.

## Architecture

```
Browser (vis.js graph, vanilla JS)
        │  fetch()
        ▼
FastAPI backend  ─────────►  Gemini (gemini-3.6-flash)
   │        │                    extraction only — schema-constrained JSON
   │        └─► Pydantic v2 models, reject bad data before rules ever see it
   │
   ├─ Rule / AST engine        deterministic evaluation of compiled clauses
   ├─ Restrictiveness + outlier-rule checks   synthetic-population testing
   ├─ Precedent RAG            embeddings or token-overlap over past overrides
   └─ SHA-256 ledger           per-bidder chain + a separate tender-integrity chain
```

| Layer | Tech |
|---|---|
| Frontend | HTML5, vanilla JS, vis.js network graph, JetBrains Mono for data/hashes — no framework |
| Backend | Python 3.11, FastAPI, Uvicorn |
| Validation | Pydantic v2 |
| AI extraction | Google Gemini (`google-genai`), `gemini-3.6-flash` by default |
| PDF generation | ReportLab |
| Deployment | Frontend on Vercel, backend on Render |

## Repository layout

| File | What's in it |
|---|---|
| `main.py` | FastAPI app, every route, in-memory session state |
| `engine.py` | `ProcurementIntelligenceEngine` — evidence graph, rule evaluation, ledger, Merkle root |
| `schemas.py` | Pydantic models shared across the backend |
| `extraction.py` | Gemini document extraction (schema-constrained JSON) |
| `restrictiveness.py` | Restrictiveness index, outlier-rule detection, tender-integrity ledger |
| `precedent_rag.py` | Precedent retrieval — embeddings + deterministic fallback |
| `legal_defense.py` | Annexure A / Annexure B PDF generation |
| `demo_fixtures.py` | Offline demo data — three real bidder filings against one real GeM tender, plus a deliberately-rigged tender for the integrity-gate demo |
| `index.html`, `style.css`, `app.js` | Frontend |

## API reference

Base URL: `https://sih-gem-compliance.onrender.com`

**Ingest a tender + bidder**
```
POST /api/v3/ingest-documents
Content-Type: multipart/form-data

tender_file: <pdf>          optional — reused from the active tender if omitted
bidder_files: <pdf>[]        required, one or more
bidder_label: "ABC Infrastructure"
tender_department: "Nashik Municipal Corporation"
```
Returns the compliance decision, or `409` with `"blocked": true` if the tender's ruleset trips the integrity gate.

**Override a flagged tender**
```
POST /api/v3/tender/integrity-override
{ "reason": "...", "actor": "..." }
```

**Correct an evidence value**
```
POST /api/v3/officer-override
{ "node_id": "E14", "new_value": 11.2, "actor": "...", "reason": "..." }
```

**Downstream impact of a value, before you change it**
```
GET /api/v3/blast-radius/{node_id}
```

**Counterfactual**
```
POST /api/v3/counterfactual
{ "changes": [{ "entity_name": "turnover", "extracted_value": "12.5" }] }
```

**Verify the ledger independently**
```
GET /api/v3/audit-chain
→ { "chain_valid": true, "merkle_root": "...", "ledger": [...] }
```

Bidder comparison matrix, per-bidder reports, both annexure PDFs, the restrictiveness/outlier checks and session state all live under `/api/v3/` as well — see `main.py` for the full route list.

## Running it locally

```bash
git clone https://github.com/Nikhilnhgxyyf/sih-gem-compliance.git
cd sih-gem-compliance
pip install -r requirements.txt

export GEMINI_API_KEY=your_key_here   # optional, see below
uvicorn main:app --reload --port 8000
```

Serve `index.html` with any static server (VS Code Live Server, `python -m http.server`) and point `API_BASE` in `app.js` at `http://localhost:8000`.

`GEMINI_API_KEY` is optional. Without it, extraction falls back to `demo_fixtures.py` — the same real bidder filings used in the live demo, plus the rigged tender that trips the integrity gate. A judge should be able to clone this and run the whole flow without an API key.

| Env var | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | — | Enables live document extraction |
| `GEMINI_MODEL` | `gemini-3.6-flash` | Extraction model |
| `ALLOWED_ORIGINS` | local dev ports | CORS allowlist for the deployed frontend |
| `MAX_FILE_SIZE_MB` | `15` | Per-file upload cap |


## Team

Flamingo Group · SIH26100 · *AI-Powered Integrated Bid Compliance Verification Platform for GeM Procurement*
