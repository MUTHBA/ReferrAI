import re
import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    role: Literal["admin", "partner"]
    name: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if not EMAIL_PATTERN.match(value):
            raise ValueError("Invalid email address")
        return value.lower()

    @model_validator(mode="after")
    def validate_partner_name(self) -> "RegisterRequest":
        if self.role == "partner" and not self.name:
            raise ValueError("name is required when role is 'partner'")
        return self


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
