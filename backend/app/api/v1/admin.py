# -----------------------------------------------------------------------------
# backend/app/api/v1/admin.py
#
# Admin-only API endpoints that don't belong to a specific domain router.
# Currently exposes one endpoint:
#   POST /api/v1/admin/synthetic-data — triggers synthetic ML training data
#   generation via SyntheticDataGenerator (AI-DATA-001/002). Requires admin
#   role. The endpoint is intentionally slow for large requests (bcrypt at
#   module load, sequential DB commits per generator step) — callers should
#   treat it as a long-running operation and not set aggressive timeouts.
# -----------------------------------------------------------------------------

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.models.user import User
from app.schemas.synthetic_data import SyntheticDataRequest, SyntheticDataResponse
from app.services.synthetic_data_service import generate_and_insert

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post(
    "/synthetic-data",
    response_model=SyntheticDataResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate synthetic ML training data",
)
async def generate_synthetic_data(
    payload: SyntheticDataRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> SyntheticDataResponse:
    return await generate_and_insert(db, payload)
