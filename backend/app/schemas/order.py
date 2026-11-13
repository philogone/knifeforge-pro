from datetime import date, datetime

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
    stage: str | None = Field(default=None, min_length=1, max_length=40)
    lines: list[OrderLineIn] | None = None


class OrderOut(BaseModel):
    id: int
    customer_name: str
    customer_email: str | None
    status: OrderStatus
    notes: str | None
    customer_id: int | None = None
    due_date: date | None = None
    stage: str = "todo"
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


class TimeEntryIn(BaseModel):
    worked_on: date
    minutes: int = Field(gt=0, le=24 * 60)
    stage: str | None = Field(default=None, max_length=40)
    note: str | None = Field(default=None, max_length=300)


class TimeEntryOut(TimeEntryIn):
    id: int

    model_config = {"from_attributes": True}


class TimeSummaryOut(BaseModel):
    entries: list[TimeEntryOut]
    spent_minutes: int
    planned_minutes: int  # from the models' estimated hours × quantities
    hourly_rate: float
    spent_cost: float
    by_stage: dict[str, int]
