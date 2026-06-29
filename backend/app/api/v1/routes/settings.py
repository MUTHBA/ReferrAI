# -----------------------------------------------------------------------------
# backend/app/api/v1/routes/settings.py
#
# Admin-only settings endpoints. Both routes require the require_admin
# dependency from AUTH-003. Business logic lives in SettingService; this
# module only validates input, calls the service, and maps exceptions to
# HTTP status codes.
# -----------------------------------------------------------------------------

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.models.user import User
from app.schemas.setting import SettingResponse, SettingUpdateRequest
from app.services.setting_service import SettingNotFoundError, SettingService

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=list[SettingResponse])
async def list_settings(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[SettingResponse]:
    service = SettingService(db)
    settings = await service.list_all()
    return [SettingResponse.model_validate(s) for s in settings]


@router.put("/{key}", response_model=SettingResponse)
async def update_setting(
    key: str,
    payload: SettingUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> SettingResponse:
    service = SettingService(db)
    try:
        setting = await service.set(key, payload.value, current_user.id)
    except SettingNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Setting '{key}' not found",
        )
    return SettingResponse.model_validate(setting)
