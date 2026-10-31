# -----------------------------------------------------------------------------
# backend/app/api/v1/routes/dashboard.py
#
# Dashboard and reporting endpoints. Admin-only: GET /dashboard/admin (KPIs
# + 30-day volume chart) and the three CSV exports under /reports/. Partner-
# only: GET /dashboard/partner (own KPIs + AI score placeholders). CSV
# responses use StreamingResponse with Content-Disposition: attachment so
# the browser triggers a file download rather than rendering inline.
# Mounted in main.py with prefix="/api/v1".
# -----------------------------------------------------------------------------

import csv
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin, require_partner
from app.models.user import User
from app.schemas.dashboard import AdminDashboardResponse, PartnerDashboardResponse
from app.services.dashboard_service import DashboardService

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/admin", response_model=AdminDashboardResponse)
async def admin_dashboard(
    days: int = Query(default=30, ge=1, le=90),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminDashboardResponse:
    return await DashboardService(db).get_admin_dashboard(days=days)


@router.get("/dashboard/partner", response_model=PartnerDashboardResponse)
async def partner_dashboard(
    days: int = Query(default=30, ge=1, le=90),
    current_user: User = Depends(require_partner),
    db: AsyncSession = Depends(get_db),
) -> PartnerDashboardResponse:
    return await DashboardService(db).get_partner_dashboard(current_user.id, days=days)


def _csv_response(rows: list[dict], filename: str) -> StreamingResponse:
    if not rows:
        content = ""
    else:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        content = output.getvalue()

    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/reports/referrals.csv")
async def export_referrals(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    rows = await DashboardService(db).get_referrals_csv_data()
    return _csv_response(rows, "referrals.csv")


@router.get("/reports/commissions.csv")
async def export_commissions(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    rows = await DashboardService(db).get_commissions_csv_data()
    return _csv_response(rows, "commissions.csv")


@router.get("/reports/partners.csv")
async def export_partners(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    rows = await DashboardService(db).get_partners_csv_data()
    return _csv_response(rows, "partners.csv")
