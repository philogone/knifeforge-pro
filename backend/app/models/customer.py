from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Customer(Base):
    """A buyer: a private person or a business (SIREN required on B2B invoices since the
    e-invoicing reform). Orders and sales documents point here; issued invoices also keep a
    frozen copy of these details, so editing or erasing a customer never alters an invoice."""

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    is_business: Mapped[bool] = mapped_column(Boolean, default=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    address_line1: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(200), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str] = mapped_column(String(2), default="FR")
    # delivery address, only when it differs from the billing one (mandatory mention then)
    delivery_line1: Mapped[str | None] = mapped_column(String(200), nullable=True)
    delivery_postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    delivery_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    delivery_country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    siren: Mapped[str | None] = mapped_column(String(9), nullable=True)
    vat_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # GDPR: personal data erased on request; the record stays so documents keep their link
    anonymized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
