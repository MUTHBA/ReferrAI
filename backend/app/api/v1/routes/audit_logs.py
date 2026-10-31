# -----------------------------------------------------------------------------
# backend/app/api/v1/routes/audit_logs.py
#
# Admin-only, read-only audit log (GET /audit-logs, GET /audit-logs/actions).
# Filters: action, actor (admin|system), free-text search (partner name,
# admin email, IP, values), and a date range. Rows are never edited here.
# -----------------------------------------------------------------------------

from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.models.user import User
from app.schemas.audit_log import AuditLogEntry, AuditLogPage, AuditLogStats
from app.services.audit_log_service import AuditLogService

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


@router.get("", response_model=AuditLogPage)
async def list_audit_logs(
    action: Optional[str] = Query(None, max_length=100),
    actor: Optional[Literal["admin", "system"]] = Query(None),
    search: Optional[str] = Query(None, max_length=100),
    since: Optional[datetime] = Query(None),
    until: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AuditLogPage:
    rows, total, names, stats = await AuditLogService(db).search(
        action=action, actor=actor, search=search, since=since, until=until, limit=limit, offset=offset
    )
    items = [
        AuditLogEntry(
            id=log.id,
            created_at=log.created_at,
            actor_email=email,
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            partner_name=names.get(log.entity_id) if log.entity_id else None,
            old_value=log.old_value,
            new_value=log.new_value,
            ip_address=log.ip_address,
        )
        for log, email in rows
    ]
    return AuditLogPage(items=items, total=total, limit=limit, offset=offset, stats=AuditLogStats(**stats))


@router.get("/actions", response_model=list[str])
async def list_audit_actions(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    return await AuditLogService(db).actions()
