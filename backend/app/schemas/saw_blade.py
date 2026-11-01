from datetime import datetime

from pydantic import BaseModel, Field

from app.models.saw_blade import SawType


class SawBladeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    saw_type: SawType
    diameter_mm: float | None = Field(default=None, gt=0)
    kerf_mm: float = Field(gt=0)
    notes: str | None = None


class SawBladeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    saw_type: SawType | None = None
    diameter_mm: float | None = Field(default=None, gt=0)
    kerf_mm: float | None = Field(default=None, gt=0)
    notes: str | None = None


class SawBladeOut(BaseModel):
    id: int
    name: str
    saw_type: SawType
    diameter_mm: float | None
    kerf_mm: float
    notes: str | None
    is_mock: bool
    created_at: datetime

    model_config = {"from_attributes": True}
