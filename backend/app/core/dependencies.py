# -----------------------------------------------------------------------------
# backend/app/core/dependencies.py
#
# FastAPI dependency chain for authentication and role-based access control.
# get_current_user decodes the bearer JWT, looks the user up by the "sub"
# claim, and rejects expired/invalid tokens or inactive users with a 401.
# require_admin and require_partner wrap it and add a 403 if the user's role
# doesn't match. Route handlers gate access by declaring
# `Depends(require_admin)` / `Depends(require_partner)` instead of checking
# roles inline.
# -----------------------------------------------------------------------------

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User
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
