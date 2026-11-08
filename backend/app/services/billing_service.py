"""Quotes, invoices and credit notes: totals, numbering, issuing.

French rules this encodes (CGI art. 242 nonies A, e-invoicing reform):
- an invoice number is unique, continuous and chronological; once issued an invoice never
  changes. A mistake is corrected by a credit note (avoir) that references it;
- seller and buyer details are frozen at issue (snapshots), so later edits to settings or
  to the customer (including a GDPR erasure) never rewrite an issued document;
- VAT is computed per rate on the sum of line amounts (EN 16931 BR-CO rules), rounded to
  the cent; a micro-entreprise invoices with VAT category E and the art. 293 B mention.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.order import Order
from app.models.sales_document import DocumentCounter, DocumentKind, DocumentStatus, SalesDocument, SalesDocumentLine
from app.models.shop_settings import ShopSettings

CENT = Decimal("0.01")
PREFIX = {DocumentKind.QUOTE: "D", DocumentKind.INVOICE: "F", DocumentKind.CREDIT_NOTE: "A"}
FRANCHISE_MENTION = "TVA non applicable, art. 293 B du CGI"
B2B_RECOVERY_FEE = "Indemnité forfaitaire pour frais de recouvrement en cas de retard : 40 €"
DEFAULT_LATE_PENALTY = "Pénalités de retard : trois fois le taux d'intérêt légal"


class BillingError(ValueError):
    pass


def money(value: Decimal | float | int | str) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass
class VatBreakdown:
    rate: Decimal
    base: Decimal
    amount: Decimal


def line_total(line: SalesDocumentLine) -> Decimal:
    return money(Decimal(line.quantity) * Decimal(line.unit_price_ht))


def vat_breakdown(doc: SalesDocument) -> list[VatBreakdown]:
    bases: dict[Decimal, Decimal] = {}
    for line in doc.lines:
        rate = Decimal(line.vat_rate).quantize(CENT)
        bases[rate] = bases.get(rate, Decimal("0")) + line_total(line)
    return [VatBreakdown(rate, money(base), money(base * rate / 100)) for rate, base in sorted(bases.items())]


def compute_totals(doc: SalesDocument) -> None:
    breakdown = vat_breakdown(doc)
    doc.total_ht = money(sum((b.base for b in breakdown), Decimal("0")))
    doc.total_vat = money(sum((b.amount for b in breakdown), Decimal("0")))
    doc.total_ttc = money(doc.total_ht + doc.total_vat)


def is_franchise(settings: ShopSettings) -> bool:
    return (settings.vat_regime or "franchise") == "franchise"


def default_vat_rate(settings: ShopSettings) -> Decimal:
    return Decimal("0") if is_franchise(settings) else Decimal(str(settings.default_vat_rate or 20)).quantize(CENT)


def seller_snapshot(settings: ShopSettings) -> dict:
    return {
        "name": settings.legal_name or settings.workshop_name or "",
        "trade_name": settings.workshop_name,
        "address_line1": settings.address_line1,
        "postal_code": settings.postal_code,
        "city": settings.city,
        "country": settings.country or "FR",
        "siren": settings.siren,
        "siret": settings.siret,
        "vat_regime": settings.vat_regime or "franchise",
        "vat_number": settings.vat_number,
        "trade_register": settings.trade_register,
        "iban": settings.iban,
        "bic": settings.bic,
        "contact": settings.workshop_contact,
        "late_penalty_text": settings.late_penalty_text or DEFAULT_LATE_PENALTY,
    }


def buyer_snapshot(customer: Customer | None, fallback_name: str | None = None) -> dict:
    if customer is None:
        return {"name": fallback_name or "", "is_business": False, "country": "FR"}
    delivery = None
    if customer.delivery_line1:
        delivery = {
            "line1": customer.delivery_line1,
            "postal_code": customer.delivery_postal_code,
            "city": customer.delivery_city,
            "country": customer.delivery_country or customer.country or "FR",
        }
    return {
        "name": customer.company_name or customer.name if customer.is_business else customer.name,
        "contact": customer.name if customer.is_business and customer.company_name else None,
        "is_business": customer.is_business,
        "email": customer.email,
        "address_line1": customer.address_line1,
        "address_line2": customer.address_line2,
        "postal_code": customer.postal_code,
        "city": customer.city,
        "country": customer.country or "FR",
        "siren": customer.siren,
        "vat_number": customer.vat_number,
        "delivery": delivery,
    }


def check_issuable(doc: SalesDocument, settings: ShopSettings, customer: Customer | None) -> list[str]:
    """What is missing for a legally complete document; empty list = can be issued."""
    missing: list[str] = []
    if not doc.lines:
        missing.append("lines")
    if doc.kind == DocumentKind.QUOTE:
        return missing
    if not (settings.legal_name or settings.workshop_name):
        missing.append("seller_name")
    if not (settings.address_line1 and settings.postal_code and settings.city):
        missing.append("seller_address")
    if not settings.siren:
        missing.append("seller_siren")
    if not is_franchise(settings) and not settings.vat_number:
        missing.append("seller_vat_number")
    if customer is None:
        missing.append("customer")
    else:
        if not (customer.address_line1 and customer.postal_code and customer.city):
            missing.append("customer_address")
        if customer.is_business and not customer.siren and (customer.country or "FR") == "FR":
            missing.append("customer_siren")
    if doc.kind == DocumentKind.CREDIT_NOTE and not doc.corrects_id:
        missing.append("corrected_invoice")
    return missing


def _next_number(db: Session, kind: DocumentKind, year: int) -> str:
    counter = (
        db.query(DocumentCounter)
        .filter(DocumentCounter.kind == kind.value, DocumentCounter.year == year)
        .with_for_update()
        .first()
    )
    if counter is None:
        counter = DocumentCounter(kind=kind.value, year=year, last=0)
        db.add(counter)
    counter.last += 1
    return f"{PREFIX[kind]}-{year}-{counter.last:04d}"


def issue(db: Session, doc: SalesDocument, settings: ShopSettings) -> SalesDocument:
    if doc.status != DocumentStatus.DRAFT:
        raise BillingError("Only a draft can be issued")
    customer = db.get(Customer, doc.customer_id) if doc.customer_id else None
    missing = check_issuable(doc, settings, customer)
    if missing:
        raise BillingError("Missing: " + ", ".join(missing))
    today = date.today()
    doc.issue_date = doc.issue_date or today
    if doc.kind == DocumentKind.QUOTE:
        doc.valid_until = doc.valid_until or doc.issue_date + timedelta(days=settings.quote_validity_days or 30)
    else:
        doc.due_date = doc.due_date or doc.issue_date + timedelta(days=settings.payment_terms_days or 30)
        doc.delivery_date = doc.delivery_date or doc.issue_date
    compute_totals(doc)
    doc.seller_snapshot = seller_snapshot(settings)
    doc.buyer_snapshot = buyer_snapshot(customer)
    doc.number = _next_number(db, doc.kind, doc.issue_date.year)
    doc.status = DocumentStatus.ISSUED
    doc.issued_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(doc)
    return doc


def is_frozen(doc: SalesDocument) -> bool:
    """Issued invoices and credit notes never change (quotes stay editable until accepted)."""
    return doc.kind != DocumentKind.QUOTE and doc.status != DocumentStatus.DRAFT


def credit_note_for(db: Session, invoice: SalesDocument) -> SalesDocument:
    if invoice.kind != DocumentKind.INVOICE or invoice.status == DocumentStatus.DRAFT:
        raise BillingError("Only an issued invoice can be credited")
    note = SalesDocument(
        kind=DocumentKind.CREDIT_NOTE,
        customer_id=invoice.customer_id,
        order_id=invoice.order_id,
        corrects_id=invoice.id,
        nature=invoice.nature,
        vat_on_debits=invoice.vat_on_debits,
        notes=f"Avoir sur la facture {invoice.number}",
    )
    for i, line in enumerate(invoice.lines):
        note.lines.append(
            SalesDocumentLine(
                position=i,
                description=line.description,
                quantity=line.quantity,
                unit=line.unit,
                unit_price_ht=line.unit_price_ht,
                vat_rate=line.vat_rate,
            )
        )
    compute_totals(note)
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def invoice_from_quote(db: Session, quote: SalesDocument) -> SalesDocument:
    if quote.kind != DocumentKind.QUOTE:
        raise BillingError("Not a quote")
    invoice = SalesDocument(
        kind=DocumentKind.INVOICE,
        customer_id=quote.customer_id,
        order_id=quote.order_id,
        nature=quote.nature,
        vat_on_debits=quote.vat_on_debits,
        notes=f"Selon devis {quote.number}" if quote.number else None,
    )
    for i, line in enumerate(quote.lines):
        invoice.lines.append(
            SalesDocumentLine(
                position=i, description=line.description, quantity=line.quantity, unit=line.unit,
                unit_price_ht=line.unit_price_ht, vat_rate=line.vat_rate,
            )
        )
    compute_totals(invoice)
    if quote.status == DocumentStatus.ISSUED:
        quote.status = DocumentStatus.ACCEPTED
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def draft_from_order(db: Session, order: Order, kind: DocumentKind, settings: ShopSettings) -> SalesDocument:
    """One line per knife model of the order, at the model's sale price (HT or franchise)."""
    rate = default_vat_rate(settings)
    doc = SalesDocument(kind=kind, customer_id=order.customer_id, order_id=order.id)
    for i, line in enumerate(order.lines):
        price = Decimal(str(line.knife_model.sale_price or 0))
        if rate:
            # model prices are shown TTC to clients: store the HT equivalent
            price = money(price / (1 + rate / 100))
        doc.lines.append(
            SalesDocumentLine(
                position=i,
                description=f"Couteau {line.knife_model.name}",
                quantity=Decimal(line.quantity),
                unit="C62",
                unit_price_ht=money(price),
                vat_rate=rate,
            )
        )
    compute_totals(doc)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc
