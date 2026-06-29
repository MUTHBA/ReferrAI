# -----------------------------------------------------------------------------
# backend/app/services/audit_log_service.py
#
# Minimal audit log writer. Callers (e.g. SettingService) flush their own
# changes before calling log(); the owning service commits the full transaction
# so the setting update and its audit row land atomically.
# -----------------------------------------------------------------------------

import uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.repositories.audit_log_repository import AuditLogRepository


class AuditLogService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def log(
        self,
        user_id: Optional[uuid.UUID],
        action: str,
        entity_type: str,
        entity_id: uuid.UUID,
        old_value: Any,
        new_value: Any,
    ) -> None:
        entry = AuditLog(
            id=uuid.uuid4(),
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_value=old_value,
            new_value=new_value,
        )
        await AuditLogRepository(self.session).create(entry)
