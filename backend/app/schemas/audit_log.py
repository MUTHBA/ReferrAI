# -----------------------------------------------------------------------------
# backend/app/schemas/audit_log.py
#
# Response schemas for the admin audit log page (GET /audit-logs).
# actor_email is None for system events; partner_name is the partner the
# audited entity belongs to (partner, withdrawal, commission, fraud flag).
# -----------------------------------------------------------------------------

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class AuditLogEntry(BaseModel):
    id: uuid.UUID
    created_at: datetime
    actor_email: Optional[str] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[uuid.UUID] = None
    partner_name: Optional[str] = None
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None
    ip_address: Optional[str] = None


class AuditLogStats(BaseModel):
    events_24h: int
    admin_24h: int
    system_24h: int


class AuditLogPage(BaseModel):
    items: list[AuditLogEntry]
    total: int
    limit: int
    offset: int
    stats: AuditLogStats
