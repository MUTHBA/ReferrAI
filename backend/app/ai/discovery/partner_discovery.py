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
        """Encode a single text string into a dense vector.

        Args:
            text: Raw text to encode.

        Returns:
            1-D numpy array of shape (embedding_dim,).
        """
        return self.model.encode([text])[0]  # type: ignore[union-attr]

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors, clamped to [0, 1].

        Args:
            a: First embedding vector.
            b: Second embedding vector.

        Returns:
            float in [0, 1]; 0.0 if either vector has zero norm.
        """
        norm_a = float(np.linalg.norm(a))
        norm_b = float(np.linalg.norm(b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        raw = float(np.dot(a, b) / (norm_a * norm_b))
        # Clamp to [0, 1] — floating-point arithmetic can produce values
        # marginally outside this range for nearly identical vectors.
        return min(1.0, max(0.0, raw))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def score_candidate(self, db: AsyncSession, candidate: dict) -> float:
        """Compute a 0–100 partner-potential score for a candidate business.

        Embeds the candidate against the current active partner pool and returns
        a weighted combination of semantic similarity, category match, and a
        geographic placeholder.

        Args:
            db:        SQLAlchemy async session for partner DB queries.
            candidate: Dict with keys: business_name, category, description,
                       city, country.

        Returns:
            float in [0, 100] rounded to 2 decimal places.
            Returns 0.0 if the embedding model is unavailable or any error occurs.
        """
        if self.model is None:
            return 0.0

        try:
            # --- Load active non-synthetic partners ---
            result = await db.execute(
                select(Partner)
                .where(Partner.status == "active")
                .where(Partner.is_synthetic == False)  # noqa: E712
            )
            partners = result.scalars().all()

            # --- Embed the candidate ---
            candidate_text = (
                f"{candidate['business_name']} "
                f"{candidate['category']} "
                f"{candidate['description']}"
            )
            candidate_vec = self._embed(candidate_text)

            # --- Sub-scores ---
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

            # Placeholder: no geographic data stored on partners yet
            geographic_score = 1.0

            potential_score = (
                similarity_score * 0.5
                + category_score * 0.3
                + geographic_score * 0.2
            ) * 100

            return round(potential_score, 2)

        except Exception:
            logger.exception("PartnerDiscovery.score_candidate failed")
            return 0.0

    def score_factors(
        self,
        similarity: float,
        category: float,
        geographic: float,
    ) -> dict:
        """Assemble the three sub-scores into a named dict for storage.

        Args:
            similarity:  Max cosine similarity vs partner pool (0–1).
            category:    Category match score — 1.0 if matched, 0.5 otherwise.
            geographic:  Geographic proximity score (0–1).

        Returns:
            Dict suitable for storing in ai_scores.contributing_factors.
        """
        return {
            "similarity": similarity,
            "category_match": category,
            "geographic": geographic,
        }
