import enum
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DocumentKind(str, enum.Enum):
    QUOTE = "quote"  # devis
    INVOICE = "invoice"  # facture (UNTDID 1001: 380)
    CREDIT_NOTE = "credit_note"  # avoir (381), the only way to correct an issued invoice


class DocumentStatus(str, enum.Enum):
    DRAFT = "draft"  # editable, no number yet
    ISSUED = "issued"  # numbered and frozen (invoice / credit note) or sent (quote)
    ACCEPTED = "accepted"  # quote accepted
    REFUSED = "refused"  # quote refused
    PAID = "paid"  # invoice paid


class OperationNature(str, enum.Enum):
    """Mandatory mention since the reform; also the French billing framework code (BT-23)."""

    GOODS = "goods"  # B1: livraison de biens (a knife)
    SERVICES = "services"  # S1: prestation de services (a sharpening, a repair)
    MIXED = "mixed"  # M1


class SalesDocument(Base):
    __tablename__ = "sales_documents"
    __table_args__ = (UniqueConstraint("kind", "number", name="uq_sales_document_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[DocumentKind] = mapped_column(
        Enum(DocumentKind, name="document_kind", values_callable=lambda e: [x.value for x in e]), nullable=False
    )
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status", values_callable=lambda e: [x.value for x in e]),
        default=DocumentStatus.DRAFT,
    )
    # continuous, gap-free per kind and year (F-2026-0001); null while draft
    number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    # a credit note cancels (part of) this invoice
    # NO ACTION (not RESTRICT): still blocks deleting a corrected invoice, but lets a full
    # restore wipe the table in one statement on PostgreSQL
    corrects_id: Mapped[int | None] = mapped_column(ForeignKey("sales_documents.id"), nullable=True)

    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)  # quotes
    nature: Mapped[OperationNature] = mapped_column(
        Enum(OperationNature, name="operation_nature", values_callable=lambda e: [x.value for x in e]),
        default=OperationNature.GOODS,
    )
    vat_on_debits: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # frozen at issue: the invoice says what it said, whatever happens to settings or customer
    seller_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    buyer_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    total_ht: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    total_vat: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    total_ttc: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    paid_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    lines: Mapped[list["SalesDocumentLine"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="SalesDocumentLine.position"
    )


class SalesDocumentLine(Base):
    __tablename__ = "sales_document_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("sales_documents.id", ondelete="CASCADE"), nullable=False)
    document: Mapped[SalesDocument] = relationship(back_populates="lines")
    position: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal("1"))
    unit: Mapped[str] = mapped_column(String(10), default="C62")  # UN/ECE rec 20: C62 = unit
    unit_price_ht: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))


class DocumentCounter(Base):
    """Last number used per kind and year: numbering never reuses or skips a value."""

    __tablename__ = "document_counters"

    kind: Mapped[str] = mapped_column(String(20), primary_key=True)
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    last: Mapped[int] = mapped_column(Integer, default=0)
