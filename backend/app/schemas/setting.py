# -----------------------------------------------------------------------------
# backend/app/schemas/setting.py
#
# Pydantic schemas for the settings endpoints. SettingResponse uses
# from_attributes=True so it can be built directly from the ORM model.
# value is typed Any because JSONB settings hold strings, numbers, and
# objects — the schema does not constrain the shape.
# -----------------------------------------------------------------------------

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class SettingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    value: Any
    description: Optional[str]
    updated_at: datetime


class SettingUpdateRequest(BaseModel):
    value: Any


class SettingSchemaResponse(BaseModel):
    key: str
    kind: str
    default: Any
    description: str
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    exclusive_minimum: bool = False
    choices: list[str] = []
    object_keys: list[str] = []
    unit: Optional[str] = None
