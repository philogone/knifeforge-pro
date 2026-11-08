from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload

from app.core.security import require_admin
from app.database import get_db
from app.models.customer import Customer
from app.models.order import Order
from app.models.sales_document import DocumentKind, DocumentStatus, SalesDocument, SalesDocumentLine
from app.schemas.sales_document import DocumentIn, DocumentOut
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
                                        "total_ht", "total_vat", "total_ttc", "paid_at", "created_at", "issued_at")},
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
def from_order(order_id: int, kind: DocumentKind = Query(default=DocumentKind.QUOTE), db: Session = Depends(get_db)):
    order: Order | None = load_order_with_relations(db, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if kind == DocumentKind.CREDIT_NOTE:
        raise HTTPException(status_code=400, detail="A credit note is created from an issued invoice")
    doc = billing.draft_from_order(db, order, kind, get_shop_settings(db))
    return _out(db, _get_or_404(db, doc.id))


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
    doc.status = status
    doc.paid_at = (paid_at or date.today()) if status == DocumentStatus.PAID else None
    db.commit()
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


@router.get("/{doc_id}/pdf")
def document_pdf(doc_id: int, download: bool = False, db: Session = Depends(get_db)):
    """Issued invoice / credit note: Factur-X (PDF/A-3 + EN 16931 XML). Quote or draft: plain PDF."""
    doc = _get_or_404(db, doc_id)
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
        pdf = facturx_service.facturx_pdf(doc, logo=settings.workshop_logo, corrected_number=corrected_number)
        name = f"{'facture' if doc.kind == DocumentKind.INVOICE else 'avoir'}-{doc.number}.pdf"
    headers = {"Content-Disposition": f'{"attachment" if download else "inline"}; filename="{name}"'}
    return Response(pdf, media_type="application/pdf", headers=headers)
