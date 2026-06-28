import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_password_reset_token,
    decode_password_reset_token,
    hash_password,
    verify_password,
)
from app.models.partner import Partner
from app.models.user import User
from app.models.wallet import Wallet
from app.repositories.partner_repository import PartnerRepository
from app.repositories.user_repository import UserRepository
from app.repositories.wallet_repository import WalletRepository
from app.schemas.auth import LoginRequest, RegisterRequest


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
            role=data.role,
        )
        await self.user_repo.create(user)

        if data.role == "partner":
            partner = Partner(
                id=uuid.uuid4(),
                user_id=user.id,
                name=data.name,
                email=data.email,
            )
            await self.partner_repo.create(partner)

            wallet = Wallet(id=uuid.uuid4(), partner_id=partner.id)
            await self.wallet_repo.create(wallet)

        await self.session.commit()
        return user

    async def login(self, data: LoginRequest) -> str:
        user = await self.user_repo.get_by_email(data.email)
        if not user or not user.is_active or not verify_password(data.password, user.password_hash):
            raise InvalidCredentialsError()

        return create_access_token(subject=str(user.id), role=user.role, email=user.email)

    async def forgot_password(self, email: str) -> None:
        user = await self.user_repo.get_by_email(email)
        if not user:
            return

        token = create_password_reset_token(str(user.id))
        # Email sending is out of scope for this project — log the token so it
        # can be used to demo the reset flow.
        print(f"[password reset] token for {email}: {token}")

    async def reset_password(self, token: str, new_password: str) -> None:
        try:
            user_id = decode_password_reset_token(token)
        except ValueError as exc:
            raise InvalidResetTokenError() from exc

        user = await self.user_repo.get_by_id(uuid.UUID(user_id))
        if not user:
            raise InvalidResetTokenError()

        user.password_hash = hash_password(new_password)
        await self.session.commit()
