from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.order import OrderStatus


class OrderLineIn(BaseModel):
    knife_model_id: int
    quantity: int = Field(default=1, ge=1)


class OrderLineOut(BaseModel):
    id: int
    knife_model_id: int
    knife_model_name: str
    quantity: int

    model_config = {"from_attributes": True}


class OrderCreate(BaseModel):
    customer_name: str = Field(min_length=1, max_length=150)
    customer_email: EmailStr | None = None
    notes: str | None = None
    lines: list[OrderLineIn] = Field(default_factory=list)


class OrderUpdate(BaseModel):
    customer_name: str | None = Field(default=None, min_length=1, max_length=150)
    customer_email: EmailStr | None = None
    notes: str | None = None
    lines: list[OrderLineIn] | None = None


class OrderOut(BaseModel):
    id: int
    customer_name: str
    customer_email: str | None
    status: OrderStatus
    notes: str | None
    is_mock: bool
    created_at: datetime
    lines: list[OrderLineOut]

    model_config = {"from_attributes": True}


class MaterialFeasibility(BaseModel):
    material_id: int
    material_name: str
    unit: str
    required: float
    available: float
    sufficient: bool
    shortfall: float


class FeasibilityResult(BaseModel):
    feasible: bool
    materials: list[MaterialFeasibility]
