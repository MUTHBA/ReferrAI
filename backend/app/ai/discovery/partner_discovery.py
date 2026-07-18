# -----------------------------------------------------------------------------
# backend/app/ai/discovery/partner_discovery.py
#
# Partner discovery scoring via sentence-transformer embeddings (AI-DISC-001).
# Scores a candidate business (not yet in the DB) against the existing active
# partner pool to quantify how well it fits the current referral network.
#
# Potential score (0–100) is a weighted sum of three sub-scores:
#   similarity_score  (weight 0.5) — max cosine similarity vs partner embeddings
#   category_score    (weight 0.3) — 1.0 if candidate category matches any partner
#   geographic_score  (weight 0.2) — placeholder 1.0 (no partner geo data yet)
#
# Model loading: SentenceTransformer is loaded once in __init__. If loading
# fails (missing package, no internet, CUDA error) self.model is set to None
# and all scoring methods return 0.0 — discovery silently degrades rather than
# crashing the API.
# AI-DISC-002: added score_candidate_full() — same computation as score_candidate()
# but also returns the contributing factors dict needed for DiscoveredPartner
# storage. Shared logic extracted into _compute_scores() to avoid duplication.
# -----------------------------------------------------------------------------

import logging
from typing import Optional

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.partner import Partner

logger = logging.getLogger(__name__)

_MODEL_NAME = "all-MiniLM-L6-v2"


class PartnerDiscovery:
    """Scores a candidate business for partner-network fit using semantic embeddings.

    Usage::

        discovery = PartnerDiscovery()
        score = await discovery.score_candidate(db, {
            "business_name": "Acme Fitness",
            "category": "health",
            "description": "Online fitness coaching and nutrition plans",
            "city": "Austin",
            "country": "US",
        })
    """

    def __init__(self) -> None:
        self.model: Optional[object] = None
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import]

            self.model = SentenceTransformer(_MODEL_NAME)
            logger.info("PartnerDiscovery: loaded %s", _MODEL_NAME)
        except Exception:
            logger.exception(
                "PartnerDiscovery: failed to load %s — scoring disabled", _MODEL_NAME
            )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _embed(self, text: str) -> np.ndarray:
        """Encode a single text string into a dense vector."""
        return self.model.encode([text])[0]  # type: ignore[union-attr]

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors, clamped to [0, 1]."""
        norm_a = float(np.linalg.norm(a))
        norm_b = float(np.linalg.norm(b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        raw = float(np.dot(a, b) / (norm_a * norm_b))
        return min(1.0, max(0.0, raw))

    async def _compute_scores(
        self, db: AsyncSession, candidate: dict
    ) -> tuple[float, float, float]:
        """Return (similarity_score, category_score, geographic_score) for a candidate.

        Caller must verify self.model is not None before calling. Exceptions
        propagate to the caller, which wraps them in a try/except.
        """
        result = await db.execute(
            select(Partner)
            .where(Partner.status == "active")
            .where(Partner.is_synthetic == False)  # noqa: E712
        )
        partners = result.scalars().all()

        candidate_text = (
            f"{candidate['business_name']} "
            f"{candidate['category']} "
            f"{candidate['description']}"
        )
        candidate_vec = self._embed(candidate_text)

        similarity_score = 0.0
        category_score = 0.5  # default: no category match found yet

        for partner in partners:
            partner_text = (
                f"{partner.business_name or ''} {partner.category or ''}"
            ).strip()
            partner_vec = self._embed(partner_text)
            sim = self._cosine_similarity(candidate_vec, partner_vec)
            if sim > similarity_score:
                similarity_score = sim

            if (
                partner.category
                and partner.category == candidate.get("category")
            ):
                category_score = 1.0

        geographic_score = 1.0  # placeholder — no geo data on Partner rows yet
        return similarity_score, category_score, geographic_score

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def score_candidate(self, db: AsyncSession, candidate: dict) -> float:
        """Compute a 0–100 partner-potential score for a candidate business.

        Returns 0.0 if the embedding model is unavailable or any error occurs.
        """
        if self.model is None:
            return 0.0
        try:
            sim, cat, geo = await self._compute_scores(db, candidate)
            return round((sim * 0.5 + cat * 0.3 + geo * 0.2) * 100, 2)
        except Exception:
            logger.exception("PartnerDiscovery.score_candidate failed")
            return 0.0

    async def score_candidate_full(
        self, db: AsyncSession, candidate: dict
    ) -> tuple[float, dict]:
        """Like score_candidate() but also returns the contributing score factors.

        Returns:
            (total_score: float, factors: dict with keys similarity, category_match,
            geographic) — factors suitable for storing in DiscoveredPartner.score_factors.
            Falls back to (0.0, default_factors) when the model is unavailable.
        """
        if self.model is None:
            return 0.0, self.score_factors(0.0, 0.5, 1.0)
        try:
            sim, cat, geo = await self._compute_scores(db, candidate)
            total = round((sim * 0.5 + cat * 0.3 + geo * 0.2) * 100, 2)
            return total, self.score_factors(sim, cat, geo)
        except Exception:
            logger.exception("PartnerDiscovery.score_candidate_full failed")
            return 0.0, self.score_factors(0.0, 0.5, 1.0)

    def score_factors(
        self,
        similarity: float,
        category: float,
        geographic: float,
    ) -> dict:
        """Assemble the three sub-scores into a named dict for storage."""
        return {
            "similarity": similarity,
            "category_match": category,
            "geographic": geographic,
        }
