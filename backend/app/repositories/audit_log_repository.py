# -----------------------------------------------------------------------------
# backend/app/repositories/audit_log_repository.py
#
# Append-only data access for the audit_logs table: create() plus read-only
# search for the admin audit log page. Rows are never updated or deleted.
# Callers (services) control commit.
# -----------------------------------------------------------------------------

import uuid
from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import Row, String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.partner import Partner
from app.models.user import User


class AuditLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, log: AuditLog) -> AuditLog:
        self.session.add(log)
        await self.session.flush()
        return log

    async def search(
        self,
        *,
        action: Optional[str] = None,
        actor: Optional[str] = None,  # "admin" | "system"
        search: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[Row], int]:
        """(AuditLog, actor email | None) rows, newest first, plus the total count."""
        stmt = select(AuditLog, User.email).outerjoin(User, User.id == AuditLog.user_id)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if actor == "system":
            stmt = stmt.where(AuditLog.user_id.is_(None))
        elif actor == "admin":
            stmt = stmt.where(AuditLog.user_id.is_not(None))
        if since is not None:
            stmt = stmt.where(AuditLog.created_at >= since)
        if until is not None:
            stmt = stmt.where(AuditLog.created_at < until)
        if search:
            like = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    AuditLog.action.ilike(like),
                    AuditLog.ip_address.ilike(like),
                    User.email.ilike(like),
                    cast(AuditLog.old_value, String).ilike(like),
                    cast(AuditLog.new_value, String).ilike(like),
                    AuditLog.entity_id.in_(select(Partner.id).where(Partner.name.ilike(like))),
                )
            )
        total = (await self.session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        rows = (
            await self.session.execute(stmt.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset))
        ).all()
        return rows, int(total)

    async def counts_since(self, since: datetime) -> tuple[int, int]:
        """(admin events, system events) since the given time."""
        rows = await self.session.execute(
            select(AuditLog.user_id.is_(None), func.count())
            .where(AuditLog.created_at >= since)
            .group_by(AuditLog.user_id.is_(None))
        )
        counts = {bool(is_system): int(n) for is_system, n in rows.all()}
        return counts.get(False, 0), counts.get(True, 0)

    async def distinct_actions(self) -> list[str]:
        rows = await self.session.execute(select(AuditLog.action).distinct().order_by(AuditLog.action))
        return list(rows.scalars().all())

    async def partner_names_for(self, rows: Sequence[AuditLog]) -> dict[uuid.UUID, str]:
        """Resolve the partner each audited entity belongs to, for display."""
        from app.models.commission import Commission
        from app.models.fraud_flag import FraudFlag
        from app.models.wallet import Withdrawal

        by_type: dict[str, set[uuid.UUID]] = {}
        for log in rows:
            if log.entity_id is not None and log.entity_type:
                by_type.setdefault(log.entity_type, set()).add(log.entity_id)
        out: dict[uuid.UUID, str] = {}
        sources = {
            "partner": (Partner.id, None),
            "withdrawal": (Withdrawal.id, Withdrawal.partner_id),
            "commission": (Commission.id, Commission.partner_id),
            "fraud_flag": (FraudFlag.id, FraudFlag.partner_id),
        }
        for entity_type, (id_col, partner_col) in sources.items():
            ids = by_type.get(entity_type)
            if not ids:
                continue
            if partner_col is None:
                stmt = select(Partner.id, Partner.name).where(Partner.id.in_(ids))
            else:
                stmt = select(id_col, Partner.name).join(Partner, Partner.id == partner_col).where(id_col.in_(ids))
            out.update({k: v for k, v in (await self.session.execute(stmt)).all()})
        return out
