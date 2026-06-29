# -----------------------------------------------------------------------------
# backend/app/services/setting_service.py
#
# Business logic for runtime settings. get() never raises on a missing key —
# per the resilience design in CLAUDE.md, a missing settings row must not
# crash the application. set() audits every change atomically: the value
# update and the audit_log row commit together or not at all.
# -----------------------------------------------------------------------------

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.setting import Setting
from app.repositories.setting_repository import SettingKeyNotFoundError, SettingRepository
from app.services.audit_log_service import AuditLogService


class SettingNotFoundError(Exception):
    def __init__(self, key: str) -> None:
        super().__init__(f"Setting '{key}' not found")
        self.key = key


class SettingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = SettingRepository(session)

    async def get(self, key: str, default: Any = None) -> Any:
        setting = await self.repo.get(key)
        if setting is None:
            return default
        return setting.value

    async def list_all(self) -> list[Setting]:
        return await self.repo.list_all()

    async def set(self, key: str, value: Any, user_id: uuid.UUID) -> Setting:
        old_setting = await self.repo.get(key)
        if old_setting is None:
            raise SettingNotFoundError(key)

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
            old_value=old_value,
            new_value=value,
        )

        await self.session.commit()
        return updated
