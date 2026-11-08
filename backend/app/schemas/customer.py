from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class CustomerIn(BaseModel):
    is_business: bool = False
    name: str = Field(min_length=1, max_length=150)
    company_name: str | None = Field(default=None, max_length=150)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    address_line1: str | None = Field(default=None, max_length=200)
    address_line2: str | None = Field(default=None, max_length=200)
    postal_code: str | None = Field(default=None, max_length=20)
    city: str | None = Field(default=None, max_length=100)
    country: str = Field(default="FR", min_length=2, max_length=2)
    delivery_line1: str | None = Field(default=None, max_length=200)
    delivery_postal_code: str | None = Field(default=None, max_length=20)
    delivery_city: str | None = Field(default=None, max_length=100)
    delivery_country: str | None = Field(default=None, min_length=2, max_length=2)
    siren: str | None = Field(default=None, pattern=r"^(\d{9})?$")
    vat_number: str | None = Field(default=None, max_length=20)
    notes: str | None = None


class CustomerOut(CustomerIn):
    id: int
    email: str | None = None  # an anonymized record no longer holds a valid address
    anonymized_at: datetime | None
    is_mock: bool
    created_at: datetime
    order_count: int = 0
    document_count: int = 0

    model_config = {"from_attributes": True}
