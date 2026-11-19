from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class SettingResponse(BaseModel):
    key: str
    value: Any
    version: int
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class SettingUpdateRequest(BaseModel):
    value: Any
