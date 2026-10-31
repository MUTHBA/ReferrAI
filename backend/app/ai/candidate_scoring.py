# -----------------------------------------------------------------------------
# backend/app/ai/candidate_scoring.py
#
# Partner discovery (AI-DISC): scores how closely a candidate business
# resembles the platform's best existing partners.
#
#   reference set  = top real active partners by revenue (up to 25), each
#                    weighted by its revenue share
#   similarity     = revenue-weighted mean of the candidate's top-3 text
#                    similarities to the reference partners (0-1)
#   category_fit   = share of reference revenue earned in the candidate's
#                    category (0-1)
#   potential      = 100 x (0.7 x similarity + 0.3 x category_fit)
#
# Text similarity uses sentence-transformers (all-MiniLM-L6-v2) when the
# package and model are available — loaded ONCE per process, in a worker
# thread, from the local cache (HF_HOME) baked into the Docker image. If not,
# it falls back to TF-IDF character n-grams, so discovery always works; the
# method used is recorded in the score factors.
# -----------------------------------------------------------------------------

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

MODEL_NAME = "all-MiniLM-L6-v2"
_model = None
_model_failed = False
_model_lock = threading.Lock()


@dataclass
class ReferencePartner:
    text: str
    category: Optional[str]
    weight: float
    name: str = ""  # display name; falls back to text


def _embedding_model():
    global _model, _model_failed
    if _model is not None or _model_failed:
        return _model
    with _model_lock:
        if _model is None and not _model_failed:
            try:
                from sentence_transformers import SentenceTransformer  # type: ignore[import]

                _model = SentenceTransformer(MODEL_NAME)
                logger.info("Discovery: loaded %s", MODEL_NAME)
            except Exception as exc:  # package missing, no cache + offline, ...
                _model_failed = True
                logger.warning("Discovery: %s unavailable (%s); using TF-IDF similarity", MODEL_NAME, exc)
    return _model


def _similarity_matrix(candidates: list[str], references: list[str]) -> tuple[np.ndarray, str]:
    model = _embedding_model()
    if model is not None:
        emb = model.encode(candidates + references, normalize_embeddings=True, batch_size=64)
        c, r = emb[: len(candidates)], emb[len(candidates):]
        return np.clip(c @ r.T, 0.0, 1.0), "embeddings"

    from sklearn.feature_extraction.text import TfidfVectorizer

    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
    m = vec.fit_transform(candidates + references)
    c, r = m[: len(candidates)], m[len(candidates):]
    return np.clip((c @ r.T).toarray(), 0.0, 1.0), "tfidf"


def candidate_text(c: dict) -> str:
    return " ".join(str(c.get(k) or "") for k in ("business_name", "category", "description")).strip()


def score_candidates(candidates: list[dict], references: list[ReferencePartner]) -> list[tuple[Optional[float], dict]]:
    """Synchronous (CPU). Returns [(potential_score_0_100 | None, factors)] in input order."""
    if not candidates:
        return []
    if not references:
        return [
            (
                None,
                {
                    "method": None,
                    "similarity": None,
                    "category_fit": None,
                    "reference_partners": 0,
                    "note": "No active partners with revenue yet — nothing to compare against.",
                },
            )
            for _ in candidates
        ]

    weights = np.array([r.weight for r in references], dtype=float)
    weights = weights / weights.sum() if weights.sum() > 0 else np.full(len(references), 1 / len(references))
    sims, method = _similarity_matrix([candidate_text(c) for c in candidates], [r.text for r in references])

    out = []
    for i, cand in enumerate(candidates):
        row = sims[i]
        top = np.argsort(row)[::-1][:3]
        similarity = float(np.average(row[top], weights=weights[top] + 1e-9))
        cat = (cand.get("category") or "").strip().lower()
        category_fit = float(sum(w for r, w in zip(references, weights) if cat and (r.category or "").lower() == cat))
        potential = 100.0 * (0.7 * similarity + 0.3 * category_fit)
        out.append(
            (
                round(potential, 2),
                {
                    "method": method,
                    "similarity": round(similarity, 4),
                    "category_fit": round(category_fit, 4),
                    "weights": {"similarity": 0.7, "category_fit": 0.3},
                    "closest_partners": [references[j].name or references[j].text for j in top],
                    "reference_partners": len(references),
                },
            )
        )
    return out
