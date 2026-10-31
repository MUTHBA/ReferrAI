# -----------------------------------------------------------------------------
# backend/app/schemas/auth.py
#
# Pydantic request/response shapes for the auth routes: register, login,
# /me, and the forgot/reset-password pair. Public registration only creates
# partner accounts — admins are created with `python -m scripts.create_admin`
# — so `role` is fixed to "partner" and `name` is required. Email format is
# validated with a plain regex rather than pydantic's EmailStr, since
# EmailStr needs the optional email-validator package, which isn't in
# requirements.txt.
# -----------------------------------------------------------------------------

import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    role: Literal["partner"] = "partner"
    name: str = Field(min_length=1, max_length=255)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if not EMAIL_PATTERN.match(value):
            raise ValueError("Invalid email address")
        return value.lower()


class RegisterResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    created_at: datetime


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ForgotPasswordRequest(BaseModel):
    email: str


class MessageResponse(BaseModel):
    message: str


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)
