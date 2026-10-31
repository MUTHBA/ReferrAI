# -----------------------------------------------------------------------------
# backend/app/core/dependencies.py
#
# FastAPI dependency chain for authentication and role-based access control.
# get_current_user decodes the bearer JWT (access tokens only — reset tokens
# are rejected), looks the user up by the "sub" claim, and rejects invalid
# tokens or inactive users with a 401. require_admin / require_partner add a
# 403 on role mismatch. get_current_partner resolves the caller's Partner
# row, and require_active_partner additionally blocks suspended/pending
# partners from actions that create value (links, codes, withdrawals).
# Change: client_ip() now uses the LAST X-Forwarded-For entry (client-spoofable earlier entries ignored) - week-11 hardening merged.
# -----------------------------------------------------------------------------

import uuid

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.partner import Partner
from app.models.user import User
from app.repositories.partner_repository import PartnerRepository
from app.repositories.user_repository import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        claims = decode_access_token(token)
        user_id = uuid.UUID(claims["sub"])
    except (ValueError, KeyError):
        raise credentials_error

    user = await UserRepository(db).get_by_id(user_id)
    if user is None or not user.is_active:
        raise credentials_error

    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def require_partner(user: User = Depends(get_current_user)) -> User:
    if user.role != "partner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Partner access required")
    return user


async def get_current_partner(
    user: User = Depends(require_partner), db: AsyncSession = Depends(get_db)
) -> Partner:
    partner = await PartnerRepository(db).get_by_user_id(user.id)
    if partner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner profile not found")
    return partner


async def require_active_partner(partner: Partner = Depends(get_current_partner)) -> Partner:
    if partner.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Partner account is {partner.status}; this action is not allowed",
        )
    return partner


def client_ip(request: Request) -> str | None:
    """Caller IP behind nginx.

    nginx is the only reverse proxy in front of this service and appends the real
    client IP via $proxy_add_x_forwarded_for, so only the LAST X-Forwarded-For
    entry is trustworthy; earlier entries can be client-spoofed (week-11 hardening).
    """
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[-1].strip()
    return request.client.host if request.client else None
