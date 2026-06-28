# -----------------------------------------------------------------------------
# backend/app/repositories/user_repository.py
#
# Data access for the users table. get_by_email backs login/registration
# uniqueness checks; get_by_id backs get_current_user's JWT-subject lookup.
# create() adds and flushes (not commits) so callers can compose it into a
# larger transaction, e.g. AuthService.register() creating User + Partner +
# Wallet rows together.
# -----------------------------------------------------------------------------

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def create(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user
