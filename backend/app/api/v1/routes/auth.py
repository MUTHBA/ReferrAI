# -----------------------------------------------------------------------------
# backend/app/api/v1/routes/auth.py
#
# Auth endpoints: register, login, me, forgot-password, reset-password.
# Mounted at /api/v1/auth via app.include_router() in main.py. Each handler
# translates a service-layer exception into the appropriate HTTP status
# (409 duplicate email, 401 bad credentials, 400 bad reset token) — business
# logic itself lives in AuthService, not here.
# -----------------------------------------------------------------------------

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    TokenResponse,
)
from app.services.auth_service import (
    AuthService,
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidResetTokenError,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> RegisterResponse:
    service = AuthService(db)
    try:
        user = await service.register(payload)
    except EmailAlreadyRegisteredError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    return RegisterResponse(id=user.id, email=user.email, role=user.role, created_at=user.created_at)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    service = AuthService(db)
    try:
        token = await service.login(payload)
    except InvalidCredentialsError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    return TokenResponse(access_token=token)


@router.get("/me", response_model=RegisterResponse)
async def me(current_user: User = Depends(get_current_user)) -> RegisterResponse:
    return RegisterResponse(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role,
        created_at=current_user.created_at,
    )


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(payload: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)) -> MessageResponse:
    service = AuthService(db)
    await service.forgot_password(payload.email)
    return MessageResponse(message="If that email is registered, a password reset token has been issued.")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)) -> MessageResponse:
    service = AuthService(db)
    try:
        await service.reset_password(payload.token, payload.new_password)
    except InvalidResetTokenError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

    return MessageResponse(message="Password reset successful")
