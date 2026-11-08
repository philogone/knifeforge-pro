from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.sales_document import DocumentKind, DocumentStatus, OperationNature


class LineIn(BaseModel):
    description: str = Field(min_length=1, max_length=300)
    quantity: Decimal = Field(default=Decimal("1"), gt=0, max_digits=12, decimal_places=3)
    unit: str = Field(default="C62", max_length=10)
    unit_price_ht: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    vat_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100, max_digits=5, decimal_places=2)


class LineOut(LineIn):
    id: int
    total_ht: Decimal

    model_config = {"from_attributes": True}


class DocumentIn(BaseModel):
    kind: DocumentKind = DocumentKind.QUOTE
    customer_id: int | None = None
    order_id: int | None = None
    nature: OperationNature = OperationNature.GOODS
    vat_on_debits: bool = False
    issue_date: date | None = None
    due_date: date | None = None
    delivery_date: date | None = None
    valid_until: date | None = None
    notes: str | None = None
    lines: list[LineIn] = Field(default_factory=list)


class DocumentOut(BaseModel):
    id: int
    kind: DocumentKind
    status: DocumentStatus
    number: str | None
    customer_id: int | None
    customer_name: str | None = None
    order_id: int | None
    corrects_id: int | None
    corrects_number: str | None = None
    nature: OperationNature
    vat_on_debits: bool
    issue_date: date | None
    due_date: date | None
    delivery_date: date | None
    valid_until: date | None
    notes: str | None
    total_ht: Decimal
    total_vat: Decimal
    total_ttc: Decimal
    paid_at: date | None
    created_at: datetime
    issued_at: datetime | None
    frozen: bool = False
    missing: list[str] = Field(default_factory=list)
    lines: list[LineOut]
