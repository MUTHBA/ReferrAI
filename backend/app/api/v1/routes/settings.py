# -----------------------------------------------------------------------------
# backend/app/api/v1/routes/settings.py
#
# Admin-only runtime settings. GET /settings lists stored values,
# GET /settings/schema describes every key (type, range, choices, default)
# so the admin UI can render a typed form, and PUT /settings/{key} validates
# the new value (422 on bad input) and writes an audit row.
# -----------------------------------------------------------------------------

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import client_ip, require_admin
from app.models.user import User
from app.schemas.setting import SettingResponse, SettingSchemaResponse, SettingUpdateRequest
from app.services.setting_service import SettingNotFoundError, SettingService, SettingValueError

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=list[SettingResponse])
async def list_settings(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[SettingResponse]:
    return [SettingResponse.model_validate(s) for s in await SettingService(db).list_all()]


@router.get("/schema", response_model=list[SettingSchemaResponse])
async def settings_schema(_: User = Depends(require_admin)) -> list[SettingSchemaResponse]:
    return [SettingSchemaResponse(**d) for d in SettingService.schema()]


@router.put("/{key}", response_model=SettingResponse)
async def update_setting(
    key: str,
    payload: SettingUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> SettingResponse:
    try:
        setting = await SettingService(db).set(key, payload.value, current_user.id, client_ip(request))
    except SettingNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Setting '{key}' not found")
    except SettingValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return SettingResponse.model_validate(setting)
