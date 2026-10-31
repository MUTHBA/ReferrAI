# -----------------------------------------------------------------------------
# backend/app/services/discovery_service.py
#
# Business logic for partner discovery (AI-DISC-002, AI-DISC-003).
# score_and_insert_candidates() compares each candidate with the best current
# partners (app/ai/discovery.py, run in a worker thread), stores the rows and
# returns them sorted by potential score. list_candidates() lists stored
# candidates; update_status() (invited / dismissed / reviewed) is audited.
# Scoring always works: sentence-transformers when available, TF-IDF otherwise.
# -----------------------------------------------------------------------------

import uuid
from decimal import Decimal
from typing import Optional

import anyio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.candidate_scoring import ReferencePartner, score_candidates
from app.models.partner import Partner
from app.models.discovered_partner import DiscoveredPartner
from app.services.audit_log_service import AuditLogService


class CandidateNotFoundError(Exception):
    def __init__(self, candidate_id: uuid.UUID) -> None:
        super().__init__(f"Discovered partner {candidate_id} not found")


class DiscoveryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _reference_partners(self, limit: int = 25) -> list[ReferencePartner]:
        rows = await self.session.execute(
            select(Partner)
            .where(Partner.status == "active")
            .where(Partner.is_synthetic == False)  # noqa: E712
            .where(Partner.total_revenue_contribution > 0)
            .order_by(Partner.total_revenue_contribution.desc())
            .limit(limit)
        )
        return [
            ReferencePartner(
                text=" ".join(x for x in (p.business_name or p.name, p.category or "") if x),
                category=p.category,
                weight=float(p.total_revenue_contribution),
                name=p.business_name or p.name,
            )
            for p in rows.scalars()
        ]

    async def score_and_insert_candidates(self, candidates: list[dict]) -> list[DiscoveredPartner]:
        """Score candidates against the best current partners and persist them,
        returning rows sorted by potential score (highest first)."""
        references = await self._reference_partners()
        results = await anyio.to_thread.run_sync(score_candidates, candidates, references)

        inserted: list[DiscoveredPartner] = []
        for c, (score, factors) in zip(candidates, results):
            dp = DiscoveredPartner(
                id=uuid.uuid4(),
                candidate_name=c["business_name"],
                business_category=c.get("category") or None,
                geographic_data={"city": c.get("city", ""), "country": c.get("country", "")},
                raw_data=c,
                potential_score=Decimal(str(score)) if score is not None else None,
                score_factors=factors,
                status="new",
            )
            self.session.add(dp)
            inserted.append(dp)

        await self.session.commit()
        inserted.sort(key=lambda x: float(x.potential_score or 0), reverse=True)
        return inserted

    async def list_candidates(self, status: Optional[str] = None) -> list[DiscoveredPartner]:
        stmt = select(DiscoveredPartner)
        if status:
            stmt = stmt.where(DiscoveredPartner.status == status)
        stmt = stmt.order_by(
            DiscoveredPartner.potential_score.desc().nullslast(), DiscoveredPartner.created_at.desc()
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def update_status(
        self,
        candidate_id: uuid.UUID,
        new_status: str,
        admin_id: Optional[uuid.UUID] = None,
        ip_address: Optional[str] = None,
    ) -> DiscoveredPartner:
        """Transition a DiscoveredPartner's status (invited / dismissed / reviewed); audited."""
        result = await self.session.execute(
            select(DiscoveredPartner).where(DiscoveredPartner.id == candidate_id)
        )
        dp = result.scalar_one_or_none()
        if dp is None:
            raise CandidateNotFoundError(candidate_id)
        old_status = dp.status
        dp.status = new_status
        await AuditLogService(self.session).log(
            user_id=admin_id,
            action="discovery.status_changed",
            entity_type="discovered_partner",
            entity_id=dp.id,
            old_value={"status": old_status},
            new_value={"status": new_status, "candidate_name": dp.candidate_name},
            ip_address=ip_address,
        )
        await self.session.commit()
        return dp
