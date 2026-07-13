# -----------------------------------------------------------------------------
# backend/app/services/discovery_service.py
#
# Business logic for partner discovery (AI-DISC-002, AI-DISC-003).
# score_and_insert_candidates() runs PartnerDiscovery.score_candidate_full()
# for each submitted candidate, inserts DiscoveredPartner rows, commits, then
# returns the inserted rows sorted by potential_score descending so callers
# get a ranked list in one call.
# update_status() handles the PATCH action (invited / dismissed / reviewed).
# PartnerDiscovery degrades gracefully when sentence_transformers is unavailable
# — scores will be 0.0, but records are still inserted.
# -----------------------------------------------------------------------------

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.discovery.partner_discovery import PartnerDiscovery
from app.models.discovered_partner import DiscoveredPartner


class CandidateNotFoundError(Exception):
    def __init__(self, candidate_id: uuid.UUID) -> None:
        super().__init__(f"Discovered partner {candidate_id} not found")


class DiscoveryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def score_and_insert_candidates(
        self, candidates: list[dict]
    ) -> list[DiscoveredPartner]:
        """Score and persist each candidate; return rows sorted by score desc."""
        discovery = PartnerDiscovery()
        inserted: list[DiscoveredPartner] = []

        for c in candidates:
            score, factors = await discovery.score_candidate_full(self.session, c)
            dp = DiscoveredPartner(
                id=uuid.uuid4(),
                candidate_name=c["business_name"],
                business_category=c.get("category") or None,
                geographic_data={
                    "city": c.get("city", ""),
                    "country": c.get("country", ""),
                },
                raw_data=c,
                potential_score=Decimal(str(score)),
                score_factors=factors,
                status="new",
            )
            self.session.add(dp)
            inserted.append(dp)

        await self.session.commit()
        inserted.sort(
            key=lambda x: float(x.potential_score or 0), reverse=True
        )
        return inserted

    async def update_status(
        self, candidate_id: uuid.UUID, new_status: str
    ) -> DiscoveredPartner:
        """Transition a DiscoveredPartner's status (invited / dismissed / reviewed)."""
        result = await self.session.execute(
            select(DiscoveredPartner).where(DiscoveredPartner.id == candidate_id)
        )
        dp = result.scalar_one_or_none()
        if dp is None:
            raise CandidateNotFoundError(candidate_id)
        dp.status = new_status
        await self.session.commit()
        return dp
