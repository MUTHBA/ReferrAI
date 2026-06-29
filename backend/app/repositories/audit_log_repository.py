# -----------------------------------------------------------------------------
# backend/app/repositories/audit_log_repository.py
#
# Append-only data access for the audit_logs table. Only create() is exposed —
# audit log rows are immutable once written. Callers (services) control commit.
# -----------------------------------------------------------------------------

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


class AuditLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, log: AuditLog) -> AuditLog:
        self.session.add(log)
        await self.session.flush()
        return log
