# -----------------------------------------------------------------------------
# backend/app/services/setting_service.py
#
# Runtime business settings (commission rates, thresholds, attribution, ...).
# get() returns the stored value, validated against the definition in
# app/core/setting_definitions.py; if the row is missing or the stored value
# is invalid it logs a warning and returns the registry default, so a bad row
# can never crash commission or withdrawal processing. set() validates the new
# value (raising SettingValueError -> HTTP 422), writes an audit_logs row and
# commits.
# -----------------------------------------------------------------------------

import logging
import uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.setting_definitions import (
    SETTING_DEFINITIONS,
    SettingDefinition,
    SettingValidationError,
)
from app.models.setting import Setting
from app.repositories.setting_repository import SettingKeyNotFoundError, SettingRepository
from app.services.audit_log_service import AuditLogService

logger = logging.getLogger(__name__)

_MISSING = object()


class SettingNotFoundError(Exception):
    def __init__(self, key: str) -> None:
        super().__init__(f"Setting '{key}' not found")
        self.key = key


class SettingValueError(Exception):
    def __init__(self, key: str, message: str) -> None:
        super().__init__(message)
        self.key = key


class SettingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = SettingRepository(session)

    async def get(self, key: str, default: Any = _MISSING) -> Any:
        definition: Optional[SettingDefinition] = SETTING_DEFINITIONS.get(key)
        fallback = default if default is not _MISSING else (definition.default if definition else None)

        setting = await self.repo.get(key)
        if setting is None:
            return fallback
        if definition is None:
            return setting.value
        try:
            return definition.validate(setting.value)
        except SettingValidationError as exc:
            logger.warning("Stored setting %s is invalid (%s); using default %r", key, exc, fallback)
            return fallback

    async def list_all(self) -> list[Setting]:
        return await self.repo.list_all()

    @staticmethod
    def schema() -> list[dict]:
        return [d.to_schema() for d in SETTING_DEFINITIONS.values()]

    async def set(
        self, key: str, value: Any, user_id: uuid.UUID, ip_address: Optional[str] = None
    ) -> Setting:
        old_setting = await self.repo.get(key)
        if old_setting is None:
            raise SettingNotFoundError(key)

        definition = SETTING_DEFINITIONS.get(key)
        if definition is not None:
            try:
                value = definition.validate(value)
            except SettingValidationError as exc:
                raise SettingValueError(key, str(exc)) from exc

        old_value = old_setting.value
        try:
            updated = await self.repo.set(key, value, user_id)
        except SettingKeyNotFoundError:
            raise SettingNotFoundError(key)

        await AuditLogService(self.session).log(
            user_id=user_id,
            action="settings.updated",
            entity_type="setting",
            entity_id=updated.id,
            old_value={"key": key, "value": old_value},
            new_value={"key": key, "value": value},
            ip_address=ip_address,
        )
        await self.session.commit()
        await self.session.refresh(updated)
        return updated
