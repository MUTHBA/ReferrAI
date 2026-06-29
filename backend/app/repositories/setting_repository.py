# -----------------------------------------------------------------------------
# backend/app/repositories/setting_repository.py
#
# Pure data access for the settings table — no business logic here.
# Canonical keys are seeded by DB-003; set() refuses to create new keys so
# that the settings table stays in sync with the seed migration.
# -----------------------------------------------------------------------------

import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.setting import Setting


class SettingKeyNotFoundError(Exception):
    def __init__(self, key: str) -> None:
        super().__init__(f"Setting key '{key}' does not exist and cannot be created here")
        self.key = key


class SettingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, key: str) -> Optional[Setting]:
        result = await self.session.execute(select(Setting).where(Setting.key == key))
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Setting]:
        result = await self.session.execute(select(Setting).order_by(Setting.key))
        return list(result.scalars().all())

    async def set(self, key: str, value: Any, user_id: Optional[uuid.UUID]) -> Setting:
        setting = await self.get(key)
        if setting is None:
            raise SettingKeyNotFoundError(key)
        setting.value = value
        setting.updated_by = user_id
        await self.session.flush()
        return setting
