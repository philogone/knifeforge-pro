from datetime import datetime

from pydantic import BaseModel, Field

from app.models.knife_model import KnifeType, MaterialRole


class KnifeModelMaterialIn(BaseModel):
    material_id: int
    role: MaterialRole = MaterialRole.OTHER
    blank_length_mm: float | None = Field(default=None, gt=0)
    blank_width_mm: float | None = Field(default=None, gt=0)
    blank_thickness_mm: float | None = Field(default=None, gt=0)
    quantity: float = Field(default=1.0, gt=0)


class KnifeModelMaterialOut(KnifeModelMaterialIn):
    id: int
    material_name: str

    model_config = {"from_attributes": True}


class KnifeModelTreatmentIn(BaseModel):
    treatment_recipe_id: int
    step_order: int = 0


class KnifeModelTreatmentOut(KnifeModelTreatmentIn):
    id: int
    treatment_recipe_name: str

    model_config = {"from_attributes": True}


class KnifeModelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    knife_type: KnifeType = KnifeType.FIXED
    base_labor_hours: float = Field(default=0.0, ge=0)
    sale_price: float = Field(default=0.0, ge=0)
    margin_percent_override: float | None = Field(default=None, ge=0, lt=100)
    materials: list[KnifeModelMaterialIn] = Field(default_factory=list)
    treatments: list[KnifeModelTreatmentIn] = Field(default_factory=list)


class KnifeModelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    knife_type: KnifeType | None = None
    base_labor_hours: float | None = Field(default=None, ge=0)
    sale_price: float | None = Field(default=None, ge=0)
    margin_percent_override: float | None = Field(default=None, ge=0, lt=100)
    materials: list[KnifeModelMaterialIn] | None = None
    treatments: list[KnifeModelTreatmentIn] | None = None


class KnifeModelOut(BaseModel):
    id: int
    name: str
    knife_type: KnifeType
    base_labor_hours: float
    sale_price: float
    margin_percent_override: float | None
    is_mock: bool
    created_at: datetime
    materials: list[KnifeModelMaterialOut]
    treatments: list[KnifeModelTreatmentOut]

    model_config = {"from_attributes": True}
