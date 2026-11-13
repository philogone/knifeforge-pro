from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload

from app.core.security import require_admin
from app.database import get_db
from app.models.customer import Customer
from app.models.order import Order
from app.models.sales_document import DocumentKind, DocumentStatus, PaymentMethod, SalesDocument, SalesDocumentLine
from app.config import get_settings
from app.models.sales_document import DocumentEvent, EventKind
from app.schemas.sales_document import DocumentIn, DocumentOut, MailDraftOut, MailIn, OverdueOut, PaymentIn, ReminderIn
from app.services import mail_service
from app.services import billing_service as billing
from app.services import facturx_service
from app.services.order_service import load_order_with_relations
from app.services.shop_settings_service import get_shop_settings

router = APIRouter(prefix="/api/admin/documents", tags=["documents"], dependencies=[Depends(require_admin)])


def _get_or_404(db: Session, doc_id: int) -> SalesDocument:
    doc = db.query(SalesDocument).options(joinedload(SalesDocument.lines)).filter(SalesDocument.id == doc_id).first()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


def _out(db: Session, doc: SalesDocument) -> dict:
    customer = db.get(Customer, doc.customer_id) if doc.customer_id else None
    corrected = db.get(SalesDocument, doc.corrects_id) if doc.corrects_id else None
    name = (doc.buyer_snapshot or {}).get("name") if doc.buyer_snapshot else None
    if not name and customer:
        name = customer.company_name if customer.is_business and customer.company_name else customer.name
    settings = get_shop_settings(db)
    return {
        **{k: getattr(doc, k) for k in ("id", "kind", "status", "number", "customer_id", "order_id", "corrects_id", "nature",
                                        "vat_on_debits", "issue_date", "due_date", "delivery_date", "valid_until", "notes",
                                        "total_ht", "total_vat", "total_ttc", "paid_at", "created_at", "issued_at",
                                        "is_deposit", "prepaid_amount")},
        "prepaid_refs": doc.prepaid_refs or [],
        "amount_payable": billing.amount_payable(doc),
        "amount_paid": billing.amount_paid(doc),
        "credited": billing.credited(doc),
        "balance_due": billing.balance_due(doc),
        "overdue_days": billing.overdue_days(doc),
        "payments": doc.payments,
        "events": doc.events,
        "customer_name": name,
        "corrects_number": corrected.number if corrected else None,
        "frozen": billing.is_frozen(doc),
        "missing": billing.check_issuable(doc, settings, customer) if doc.status == DocumentStatus.DRAFT else [],
        "lines": [
            {"id": line.id, "description": line.description, "quantity": line.quantity, "unit": line.unit,
             "unit_price_ht": line.unit_price_ht, "vat_rate": line.vat_rate, "total_ht": billing.line_total(line)}
            for line in doc.lines
        ],
    }


def _apply(doc: SalesDocument, payload: DocumentIn) -> None:
    for field in ("customer_id", "order_id", "nature", "vat_on_debits", "issue_date", "due_date", "delivery_date", "valid_until", "notes"):
        setattr(doc, field, getattr(payload, field))
    doc.lines.clear()
    for i, line in enumerate(payload.lines):
        doc.lines.append(SalesDocumentLine(position=i, **line.model_dump()))
    billing.compute_totals(doc)


@router.get("", response_model=list[DocumentOut])
def list_documents(kind: DocumentKind | None = None, customer_id: int | None = None, order_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(SalesDocument).options(joinedload(SalesDocument.lines))
    if kind:
        query = query.filter(SalesDocument.kind == kind)
    if customer_id:
        query = query.filter(SalesDocument.customer_id == customer_id)
    if order_id:
        query = query.filter(SalesDocument.order_id == order_id)
    docs = query.order_by(SalesDocument.created_at.desc(), SalesDocument.id.desc()).all()
    return [_out(db, d) for d in docs]


@router.post("", response_model=DocumentOut, status_code=201)
def create_document(payload: DocumentIn, db: Session = Depends(get_db)):
    if payload.kind == DocumentKind.CREDIT_NOTE:
        raise HTTPException(status_code=400, detail="A credit note is created from an issued invoice")
    doc = SalesDocument(kind=payload.kind)
    _apply(doc, payload)
    db.add(doc)
    db.commit()
    return _out(db, _get_or_404(db, doc.id))


@router.post("/from-order/{order_id}", response_model=DocumentOut, status_code=201)
def from_order(
    order_id: int,
    kind: DocumentKind = Query(default=DocumentKind.QUOTE),
    deposit_percent: Decimal | None = Query(default=None, gt=0, le=100, description="Deposit invoice for this share of the order"),
    db: Session = Depends(get_db),
):
    order: Order | None = load_order_with_relations(db, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if kind == DocumentKind.CREDIT_NOTE:
        raise HTTPException(status_code=400, detail="A credit note is created from an issued invoice")
    try:
        if deposit_percent is not None:
            if kind != DocumentKind.INVOICE:
                raise billing.BillingError("A deposit is an invoice")
            doc = billing.draft_deposit_from_order(db, order, deposit_percent, get_shop_settings(db))
        else:
            doc = billing.draft_from_order(db, order, kind, get_shop_settings(db))
    except billing.BillingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _out(db, _get_or_404(db, doc.id))


@router.get("/overdue", response_model=list[OverdueOut])
def overdue(db: Session = Depends(get_db)):
    """Invoices past their due date with something left to collect, most overdue first."""
    docs = (
        db.query(SalesDocument)
        .filter(SalesDocument.kind == DocumentKind.INVOICE, SalesDocument.status == DocumentStatus.ISSUED)
        .all()
    )
    out = []
    for d in docs:
        days = billing.overdue_days(d)
        if days <= 0:
            continue
        reminders = [e for e in d.events if e.kind == EventKind.REMINDER]
        last = reminders[-1] if reminders else None
        out.append({
            "id": d.id, "number": d.number, "customer_name": (d.buyer_snapshot or {}).get("name"),
            "customer_email": (d.buyer_snapshot or {}).get("email"), "issue_date": d.issue_date, "due_date": d.due_date,
            "overdue_days": days, "balance_due": billing.balance_due(d), "reminders": len(reminders),
            "last_reminder_at": last.at if last else None, "last_reminder_level": last.level if last else None,
            "next_level": min(3, (last.level or 0) + 1) if last else 1,
        })
    return sorted(out, key=lambda r: -r["overdue_days"])


@router.get("/{doc_id}", response_model=DocumentOut)
def get_document(doc_id: int, db: Session = Depends(get_db)):
    return _out(db, _get_or_404(db, doc_id))


@router.put("/{doc_id}", response_model=DocumentOut)
def update_document(doc_id: int, payload: DocumentIn, db: Session = Depends(get_db)):
    doc = _get_or_404(db, doc_id)
    if doc.status != DocumentStatus.DRAFT:
        raise HTTPException(status_code=409, detail="An issued document cannot be changed")
    _apply(doc, payload)
    db.commit()
    return _out(db, _get_or_404(db, doc_id))


@router.delete("/{doc_id}", status_code=204)
def delete_document(doc_id: int, db: Session = Depends(get_db)):
    doc = _get_or_404(db, doc_id)
    if doc.status != DocumentStatus.DRAFT:
        raise HTTPException(status_code=409, detail="An issued document cannot be deleted")
    db.delete(doc)
    db.commit()


@router.post("/{doc_id}/issue", response_model=DocumentOut)
def issue_document(doc_id: int, db: Session = Depends(get_db)):
    doc = _get_or_404(db, doc_id)
    try:
        billing.issue(db, doc, get_shop_settings(db))
    except billing.BillingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _out(db, _get_or_404(db, doc_id))


@router.post("/{doc_id}/status", response_model=DocumentOut)
def set_status(doc_id: int, status: DocumentStatus, paid_at: date | None = None, db: Session = Depends(get_db)):
    """Quote accepted / refused; invoice paid. Nothing else changes on an issued document."""
    doc = _get_or_404(db, doc_id)
    allowed = {
        DocumentKind.QUOTE: {DocumentStatus.ACCEPTED, DocumentStatus.REFUSED, DocumentStatus.ISSUED},
        DocumentKind.INVOICE: {DocumentStatus.PAID, DocumentStatus.ISSUED},
        DocumentKind.CREDIT_NOTE: {DocumentStatus.PAID, DocumentStatus.ISSUED},
    }[doc.kind]
    if doc.status == DocumentStatus.DRAFT or status not in allowed:
        raise HTTPException(status_code=400, detail="Status change not allowed")
    if doc.kind == DocumentKind.QUOTE:
        doc.status = status
        db.commit()
    elif status == DocumentStatus.PAID:
        # "paid": the balance is received in one payment, dated `paid_at`
        due = billing.balance_due(doc)
        if due > 0:
            billing.add_payment(db, doc, paid_at or date.today(), due, PaymentMethod.OTHER)
    elif doc.payments:
        raise HTTPException(status_code=400, detail="Remove the payments to mark it unpaid")
    return _out(db, _get_or_404(db, doc_id))


@router.post("/{doc_id}/payments", response_model=DocumentOut, status_code=201)
def add_payment(doc_id: int, payload: PaymentIn, db: Session = Depends(get_db)):
    """Money received: a deposit in instalments, a partial payment, the balance."""
    doc = _get_or_404(db, doc_id)
    try:
        billing.add_payment(db, doc, payload.paid_on, payload.amount, payload.method, payload.reference)
    except billing.BillingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _out(db, _get_or_404(db, doc_id))


@router.delete("/{doc_id}/payments/{payment_id}", response_model=DocumentOut)
def delete_payment(doc_id: int, payment_id: int, db: Session = Depends(get_db)):
    doc = _get_or_404(db, doc_id)
    try:
        billing.delete_payment(db, doc, payment_id)
    except billing.BillingError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _out(db, _get_or_404(db, doc_id))


@router.post("/{doc_id}/credit-note", response_model=DocumentOut, status_code=201)
def create_credit_note(doc_id: int, db: Session = Depends(get_db)):
    try:
        note = billing.credit_note_for(db, _get_or_404(db, doc_id))
    except billing.BillingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _out(db, _get_or_404(db, note.id))


@router.post("/{doc_id}/to-invoice", response_model=DocumentOut, status_code=201)
def quote_to_invoice(doc_id: int, db: Session = Depends(get_db)):
    try:
        invoice = billing.invoice_from_quote(db, _get_or_404(db, doc_id))
    except billing.BillingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _out(db, _get_or_404(db, invoice.id))


def _pdf(db: Session, doc: SalesDocument) -> tuple[bytes, str]:
    """Issued invoice / credit note: Factur-X (PDF/A-3 + EN 16931 XML). Quote or draft: plain PDF."""
    settings = get_shop_settings(db)
    corrected = db.get(SalesDocument, doc.corrects_id) if doc.corrects_id else None
    corrected_number = corrected.number if corrected else None
    if doc.status == DocumentStatus.DRAFT:
        # preview with the current settings and customer, watermarked
        customer = db.get(Customer, doc.customer_id) if doc.customer_id else None
        doc.seller_snapshot = billing.seller_snapshot(settings)
        doc.buyer_snapshot = billing.buyer_snapshot(customer)
        pdf = facturx_service.render_pdf(doc, logo=settings.workshop_logo, corrected_number=corrected_number, draft=True)
        db.rollback()  # the preview snapshots are not saved
        name = f"brouillon-{doc.kind.value}-{doc.id}.pdf"
    elif doc.kind == DocumentKind.QUOTE:
        pdf = facturx_service.render_pdf(doc, logo=settings.workshop_logo)
        name = f"devis-{doc.number}.pdf"
    else:
        pdf = facturx_service.facturx_pdf(
            doc, logo=settings.workshop_logo, corrected_number=corrected_number, corrected_date=corrected.issue_date if corrected else None
        )
        name = f"{'facture' if doc.kind == DocumentKind.INVOICE else 'avoir'}-{doc.number}.pdf"
    return pdf, name


@router.get("/{doc_id}/pdf")
def document_pdf(doc_id: int, download: bool = False, db: Session = Depends(get_db)):
    pdf, name = _pdf(db, _get_or_404(db, doc_id))
    headers = {"Content-Disposition": f'{"attachment" if download else "inline"}; filename="{name}"'}
    return Response(pdf, media_type="application/pdf", headers=headers)


@router.get("/{doc_id}/mail", response_model=MailDraftOut)
def mail_draft(doc_id: int, purpose: str = Query(default="send", pattern="^(send|1|2|3)$"), db: Session = Depends(get_db)):
    """The message ready to review: recipient, subject and text in the workshop's wording."""
    doc = _get_or_404(db, doc_id)
    if doc.status == DocumentStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Issue the document before sending it")
    subject, body = mail_service.draft(doc, get_shop_settings(db), purpose)
    email = (doc.buyer_snapshot or {}).get("email")
    if not email and doc.customer_id:
        customer = db.get(Customer, doc.customer_id)
        email = customer.email if customer else None
    return {"to": [email] if email else [], "subject": subject, "body": body, "attachment": _pdf(db, doc)[1],
            "configured": mail_service.configured(get_settings())}


def _send(db: Session, doc: SalesDocument, payload_to, cc, subject: str, body: str) -> None:
    pdf, name = _pdf(db, doc)
    try:
        mail_service.send(get_settings(), [str(a) for a in payload_to], subject, body, [str(a) for a in cc],
                          [(name, pdf, "application/pdf")])
    except mail_service.MailError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/{doc_id}/send", response_model=DocumentOut)
def send_document(doc_id: int, payload: MailIn, db: Session = Depends(get_db)):
    """E-mail the document (PDF, Factur-X for an invoice) and keep a trace of it."""
    doc = _get_or_404(db, doc_id)
    if doc.status == DocumentStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Issue the document before sending it")
    _send(db, doc, payload.to, payload.cc, payload.subject, payload.body)
    db.add(DocumentEvent(document=doc, kind=EventKind.SENT, channel="email", recipient=", ".join(map(str, payload.to)),
                         subject=payload.subject))
    db.commit()
    return _out(db, _get_or_404(db, doc_id))


@router.post("/{doc_id}/reminders", response_model=DocumentOut, status_code=201)
def remind(doc_id: int, payload: ReminderIn, db: Session = Depends(get_db)):
    """A payment reminder: e-mailed from here, or sent by letter / made by phone and noted."""
    doc = _get_or_404(db, doc_id)
    if doc.kind != DocumentKind.INVOICE or billing.balance_due(doc) == 0:
        raise HTTPException(status_code=400, detail="Nothing to collect on this document")
    recipient = None
    if payload.channel == "email":
        if not payload.to or not payload.subject or not payload.body:
            raise HTTPException(status_code=422, detail="An e-mail reminder needs a recipient, a subject and a text")
        _send(db, doc, payload.to, [], payload.subject, payload.body)
        recipient = ", ".join(map(str, payload.to))
    db.add(DocumentEvent(document=doc, kind=EventKind.REMINDER, channel=payload.channel, level=payload.level,
                         recipient=recipient, subject=payload.subject if payload.channel == "email" else None, note=payload.note))
    db.commit()
    return _out(db, _get_or_404(db, doc_id))
