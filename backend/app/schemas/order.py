from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.order import OrderStage, OrderStatus


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
    # either an existing customer, or a free name (kept for quick orders)
    customer_id: int | None = None
    customer_name: str | None = Field(default=None, max_length=150)
    customer_email: EmailStr | None = None
    notes: str | None = None
    due_date: date | None = None
    lines: list[OrderLineIn] = Field(default_factory=list)


class OrderUpdate(BaseModel):
    customer_id: int | None = None
    customer_name: str | None = Field(default=None, min_length=1, max_length=150)
    customer_email: EmailStr | None = None
    notes: str | None = None
    due_date: date | None = None
    stage: OrderStage | None = None
    lines: list[OrderLineIn] | None = None


class OrderOut(BaseModel):
    id: int
    customer_name: str
    customer_email: str | None
    status: OrderStatus
    notes: str | None
    customer_id: int | None = None
    due_date: date | None = None
    stage: OrderStage = OrderStage.TODO
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
