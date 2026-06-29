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
