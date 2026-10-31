# -----------------------------------------------------------------------------
# backend/app/core/security.py
#
# Password hashing (bcrypt via passlib) and JWT helpers used across the auth
# module. create_access_token/decode_access_token handle login sessions;
# create_password_reset_token/decode_password_reset_token are a separate,
# shorter-lived token family tagged with a "purpose" claim. Access tokens
# carry typ="access" and decode_access_token rejects anything else, so a
# reset token can never be replayed as a login session. bcrypt is pinned to
# 4.0.1 in requirements.txt — passlib 1.7.4's backend self-test breaks under
# bcrypt>=4.1, which raises instead of truncating on inputs over 72 bytes.
# -----------------------------------------------------------------------------

import hashlib
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def create_access_token(*, subject: str, role: str, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    claims = {"sub": subject, "role": role, "email": email, "typ": "access", "exp": expire}
    return jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc
    if claims.get("typ") != "access" or "purpose" in claims:
        raise ValueError("Token is not an access token")
    return claims


def password_fingerprint(password_hash: str) -> str:
    """Short digest of the current password hash.

    Embedded in reset tokens so a token stops working as soon as the password
    changes — i.e. reset tokens are single-use.
    """
    return hashlib.sha256(password_hash.encode()).hexdigest()[:16]


def create_password_reset_token(subject: str, fingerprint: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
    )
    claims = {"sub": subject, "purpose": "password_reset", "pwf": fingerprint, "exp": expire}
    return jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_password_reset_token(token: str) -> tuple[str, str | None]:
    try:
        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc

    if claims.get("purpose") != "password_reset":
        raise ValueError("Token is not a password reset token")

    return claims["sub"], claims.get("pwf")
