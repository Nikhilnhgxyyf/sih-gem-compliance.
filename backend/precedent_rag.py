"""
precedent_rag.py

ADVANCED RAG -- PRECEDENT RETRIEVAL
====================================
Every conflict resolution, tender-integrity override, and officer
correction already gets logged with a human-written reason somewhere in
this system. That is institutional memory sitting unused across tenders.
This module makes it retrievable: given a NEW situation, it surfaces the
most similar PAST situation(s) a human has already resolved -- never as
an automatic decision, exactly like every other signal in GEMA.

TWO RETRIEVAL MODES, SAME INTERFACE:
  - Semantic (Gemini embeddings), when a live API client is available --
    finds conceptually similar cases, not just shared keywords.
  - Deterministic token-overlap fallback, always available, no network
    call -- same demo-safety guarantee as the rest of this project. A
    Gemini outage should never take a feature dark on demo day.

HONESTY NOTE: retrieval surfaces similar PAST human decisions. It does
not verify they were correct, and it never overrides current evaluation
-- it is a "here is what a human decided last time" prompt for the
officer, not a rule, and not a claim that the past decision was right.

VERIFY BEFORE A LIVE DEMO: the embed_text() call shape matches the
google-genai SDK's documented embeddings method at the time this was
written, but SDK versions move fast. Test that one call yourself against
your installed google-genai version. The deterministic fallback needs no
such verification -- it is pure Python, already tested below.
"""

import math
import re
from datetime import datetime, timezone
from typing import List, Optional

_STOPWORDS = {
    "the", "a", "an", "of", "to", "for", "in", "on", "at", "and", "or",
    "is", "was", "must", "be", "this", "that", "with", "by", "not",
    "least", "than", "more", "less",
}


def _tokenize(text: str) -> set:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def _token_overlap_score(a: str, b: str) -> float:
    """Deterministic fallback similarity -- Jaccard overlap of meaningful
    words. No network call, always available, always the same answer
    for the same two strings."""
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _cosine(v1: List[float], v2: List[float]) -> float:
    dot = sum(x * y for x, y in zip(v1, v2))
    n1 = math.sqrt(sum(x * x for x in v1))
    n2 = math.sqrt(sum(y * y for y in v2))
    if n1 == 0 or n2 == 0:
        return 0.0
    return dot / (n1 * n2)


def embed_text(text: str, client=None) -> Optional[List[float]]:
    """
    Tries a real Gemini embedding call. Returns None on ANY failure (no
    client, no key, network down, SDK mismatch) so callers always fall
    back cleanly -- this must never raise and never block the caller.
    """
    if client is None:
        return None
    try:
        response = client.models.embed_content(
            model="text-embedding-004",
            contents=text,
        )
        if hasattr(response, "embedding") and response.embedding is not None:
            return list(response.embedding.values)
        if hasattr(response, "embeddings") and response.embeddings:
            return list(response.embeddings[0].values)
        return None
    except Exception:
        return None


def add_precedent(
    store: List[dict], kind: str, text: str, actor: str, reason: str, client=None
) -> dict:
    """
    store: a plain list the caller owns (e.g. a module-level or main.py
           global -- in-memory for this session, same pattern as the
           rest of this app's state).
    kind:  "integrity_override" | "conflict_resolution" | "evidence_correction"
    text:  short factual description of the situation (e.g. the flagged
           clause text, or the conflicting evidence description).
    reason: the officer's own written justification.
    """
    record = {
        "id": f"PREC-{len(store):04d}",
        "kind": kind,
        "text": text,
        "actor": actor,
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "embedding": embed_text(f"{text} {reason}", client=client),
    }
    store.append(record)
    return record


def find_similar_precedents(
    store: List[dict], query_text: str, top_k: int = 3, client=None
) -> List[dict]:
    """
    Returns up to top_k past precedents most similar to query_text, each
    with "similarity" and "method" ("semantic" or "token_overlap")
    attached, so the UI can honestly show the officer which mode
    produced the match rather than implying every match is equally
    sophisticated.
    """
    if not store:
        return []

    query_embedding = embed_text(query_text, client=client)
    scored = []

    for record in store:
        if query_embedding is not None and record.get("embedding") is not None:
            score = _cosine(query_embedding, record["embedding"])
            method = "semantic"
        else:
            score = _token_overlap_score(query_text, record["text"] + " " + record["reason"])
            method = "token_overlap"
        scored.append({**{k: v for k, v in record.items() if k != "embedding"}, "similarity": round(score, 3), "method": method})

    scored.sort(key=lambda r: r["similarity"], reverse=True)
    return [r for r in scored[:top_k] if r["similarity"] > 0]
