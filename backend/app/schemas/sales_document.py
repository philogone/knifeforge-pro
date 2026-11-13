from datetime import date, datetime
from decimal import Decimal

from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.models.sales_document import DocumentKind, DocumentStatus, EventKind, OperationNature, PaymentMethod


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


class PaymentIn(BaseModel):
    paid_on: date
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    method: PaymentMethod = PaymentMethod.TRANSFER
    reference: str | None = Field(default=None, max_length=100)


class PaymentOut(PaymentIn):
    id: int

    model_config = {"from_attributes": True}


class EventOut(BaseModel):
    id: int
    kind: EventKind
    at: datetime
    channel: str
    level: int | None
    recipient: str | None
    subject: str | None
    note: str | None

    model_config = {"from_attributes": True}


class MailDraftOut(BaseModel):
    to: list[str]
    subject: str
    body: str
    attachment: str
    configured: bool


class MailIn(BaseModel):
    to: list[EmailStr] = Field(min_length=1, max_length=10)
    cc: list[EmailStr] = Field(default_factory=list, max_length=10)
    subject: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1, max_length=20000)


class ReminderIn(BaseModel):
    level: int = Field(ge=1, le=3)
    channel: Literal["email", "letter", "phone"] = "email"
    # e-mail only
    to: list[EmailStr] = Field(default_factory=list, max_length=10)
    subject: str | None = Field(default=None, max_length=255)
    body: str | None = Field(default=None, max_length=20000)
    note: str | None = Field(default=None, max_length=2000)


class OverdueOut(BaseModel):
    id: int
    number: str
    customer_name: str | None
    customer_email: str | None
    issue_date: date
    due_date: date
    overdue_days: int
    balance_due: Decimal
    reminders: int
    last_reminder_at: datetime | None
    last_reminder_level: int | None
    next_level: int


class PrepaidRef(BaseModel):
    number: str
    date: date
    amount: Decimal


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
    is_deposit: bool = False
    prepaid_amount: Decimal = Decimal("0")
    prepaid_refs: list[PrepaidRef] = Field(default_factory=list)
    amount_payable: Decimal = Decimal("0")
    amount_paid: Decimal = Decimal("0")
    credited: Decimal = Decimal("0")
    balance_due: Decimal = Decimal("0")
    overdue_days: int = 0
    payments: list[PaymentOut] = Field(default_factory=list)
    events: list[EventOut] = Field(default_factory=list)
    created_at: datetime
    issued_at: datetime | None
    frozen: bool = False
    missing: list[str] = Field(default_factory=list)
    lines: list[LineOut]
