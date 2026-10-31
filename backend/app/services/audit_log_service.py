# -----------------------------------------------------------------------------
# backend/app/services/audit_log_service.py
#
# Writes rows to audit_logs. Every admin action (settings change, payout
# review, fraud review, partner/tier edits, discovery changes, AI batch runs)
# and every money-moving system event (auto-approved withdrawal, tier
# upgrade) calls log(). user_id is None for system events. Values are stored
# as JSONB, so non-JSON types (Decimal, UUID, datetime) are converted here.
# log() only flushes — the caller's transaction decides when to commit.
# -----------------------------------------------------------------------------

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.repositories.audit_log_repository import AuditLogRepository


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (uuid.UUID,)):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    return str(value)


class AuditLogService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def log(
        self,
        user_id: Optional[uuid.UUID],
        action: str,
        entity_type: Optional[str],
        entity_id: Optional[uuid.UUID],
        old_value: Any = None,
        new_value: Any = None,
        ip_address: Optional[str] = None,
    ) -> None:
        entry = AuditLog(
            id=uuid.uuid4(),
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_value=_jsonable(old_value),
            new_value=_jsonable(new_value),
            ip_address=ip_address,
        )
        await AuditLogRepository(self.session).create(entry)

    async def search(self, **filters):
        """Audit log page: rows with actor email and the related partner's name."""
        repo = AuditLogRepository(self.session)
        rows, total = await repo.search(**filters)
        names = await repo.partner_names_for([log for log, _ in rows])
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        admin_24h, system_24h = await repo.counts_since(since)
        return rows, total, names, {"events_24h": admin_24h + system_24h, "admin_24h": admin_24h, "system_24h": system_24h}

    async def actions(self) -> list[str]:
        return await AuditLogRepository(self.session).distinct_actions()
