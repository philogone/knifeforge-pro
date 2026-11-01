from datetime import datetime

from pydantic import BaseModel, Field

from app.models.treatment import TreatmentType


class TreatmentStepIn(BaseModel):
    step_order: int = 0
    description: str = Field(min_length=1, max_length=300)
    temperature_c: float | None = None
    duration_minutes: float | None = Field(default=None, ge=0)
    medium: str | None = Field(default=None, max_length=150)


class TreatmentStepOut(TreatmentStepIn):
    id: int

    model_config = {"from_attributes": True}


class TreatmentRecipeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    treatment_type: TreatmentType
    applies_to: str = Field(min_length=1, max_length=150)
    notes: str | None = None
    steps: list[TreatmentStepIn] = Field(default_factory=list)


class TreatmentRecipeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    applies_to: str | None = Field(default=None, min_length=1, max_length=150)
    notes: str | None = None
    steps: list[TreatmentStepIn] | None = None


class TreatmentRecipeOut(BaseModel):
    id: int
    name: str
    treatment_type: TreatmentType
    applies_to: str
    notes: str | None
    is_mock: bool
    created_at: datetime
    steps: list[TreatmentStepOut]

    model_config = {"from_attributes": True}
