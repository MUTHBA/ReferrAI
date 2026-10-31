# -----------------------------------------------------------------------------
# backend/app/services/auth_service.py
#
# Business logic for the auth vertical: register, login, admin creation and
# the forgot/reset-password pair. register() creates a partner User plus the
# linked Partner (on the lowest-rank tier, so the base tier's commission rate
# applies from the first sale) and Wallet, in one transaction. Admin accounts
# can only be created through create_admin(), which is called from the CLI
# script backend/scripts/create_admin.py — never from a public endpoint.
# forgot_password() always returns silently so registered emails can't be
# enumerated; email sending is out of scope, so the token is logged instead.
# Reset tokens embed a fingerprint of the current password hash, which makes
# them single-use.
# -----------------------------------------------------------------------------

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_password_reset_token,
    decode_password_reset_token,
    hash_password,
    password_fingerprint,
    verify_password,
)
from app.models.partner import Partner, PartnerTier
from app.models.user import User
from app.models.wallet import Wallet
from app.repositories.partner_repository import PartnerRepository
from app.repositories.user_repository import UserRepository
from app.repositories.wallet_repository import WalletRepository
from app.schemas.auth import LoginRequest, RegisterRequest

logger = logging.getLogger(__name__)


class EmailAlreadyRegisteredError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class InvalidResetTokenError(Exception):
    pass


class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.partner_repo = PartnerRepository(session)
        self.wallet_repo = WalletRepository(session)

    async def register(self, data: RegisterRequest) -> User:
        if await self.user_repo.get_by_email(data.email):
            raise EmailAlreadyRegisteredError(data.email)

        user = User(
            id=uuid.uuid4(),
            email=data.email,
            password_hash=hash_password(data.password),
            role="partner",
        )
        await self.user_repo.create(user)

        base_tier = (
            await self.session.execute(
                select(PartnerTier).order_by(PartnerTier.rank_order.asc()).limit(1)
            )
        ).scalar_one_or_none()

        partner = Partner(
            id=uuid.uuid4(),
            user_id=user.id,
            name=data.name,
            email=data.email,
            tier_id=base_tier.id if base_tier else None,
        )
        await self.partner_repo.create(partner)
        await self.wallet_repo.create(Wallet(id=uuid.uuid4(), partner_id=partner.id))

        await self.session.commit()
        return user

    async def create_admin(self, email: str, password: str) -> User:
        email = email.lower()
        if await self.user_repo.get_by_email(email):
            raise EmailAlreadyRegisteredError(email)
        user = User(
            id=uuid.uuid4(),
            email=email,
            password_hash=hash_password(password),
            role="admin",
        )
        await self.user_repo.create(user)
        await self.session.commit()
        return user

    async def login(self, data: LoginRequest) -> str:
        user = await self.user_repo.get_by_email(data.email.lower())
        if not user or not user.is_active or not verify_password(data.password, user.password_hash):
            raise InvalidCredentialsError()

        return create_access_token(subject=str(user.id), role=user.role, email=user.email)

    async def forgot_password(self, email: str) -> None:
        user = await self.user_repo.get_by_email(email.lower())
        if not user:
            return

        token = create_password_reset_token(str(user.id), password_fingerprint(user.password_hash))
        # Email sending is out of scope — log the token so the reset flow can be demoed.
        logger.warning("[password reset] link for %s: /reset-password?token=%s", email, token)

    async def reset_password(self, token: str, new_password: str) -> None:
        try:
            user_id, fingerprint = decode_password_reset_token(token)
            user = await self.user_repo.get_by_id(uuid.UUID(user_id))
        except ValueError as exc:
            raise InvalidResetTokenError() from exc

        if not user or fingerprint != password_fingerprint(user.password_hash):
            # Unknown user, or the password already changed since the token was issued.
            raise InvalidResetTokenError()

        user.password_hash = hash_password(new_password)
        await self.session.commit()

    async def change_password(self, user: User, current_password: str, new_password: str) -> None:
        """Signed-in password change. Also invalidates outstanding reset links,
        because reset tokens carry a fingerprint of the old password hash."""
        if not verify_password(current_password, user.password_hash):
            raise InvalidCredentialsError()
        db_user = await self.user_repo.get_by_id(user.id)
        db_user.password_hash = hash_password(new_password)
        await self.session.commit()
