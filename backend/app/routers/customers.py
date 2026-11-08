from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.database import get_db
from app.models.customer import Customer
from app.models.order import Order
from app.models.sales_document import SalesDocument
from app.schemas.customer import CustomerIn, CustomerOut

router = APIRouter(prefix="/api/admin/customers", tags=["customers"], dependencies=[Depends(require_admin)])


def _out(db: Session, customer: Customer) -> dict:
    data = CustomerOut.model_validate(customer, from_attributes=True).model_dump()
    data["order_count"] = db.query(func.count(Order.id)).filter(Order.customer_id == customer.id).scalar() or 0
    data["document_count"] = db.query(func.count(SalesDocument.id)).filter(SalesDocument.customer_id == customer.id).scalar() or 0
    return data


def _get_or_404(db: Session, customer_id: int) -> Customer:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


def _clean(payload: CustomerIn) -> dict:
    data = payload.model_dump()
    for key, value in data.items():
        if value == "":
            data[key] = None
    data["country"] = (data.get("country") or "FR").upper()
    return data


@router.get("", response_model=list[CustomerOut])
def list_customers(db: Session = Depends(get_db)):
    return [_out(db, c) for c in db.query(Customer).order_by(Customer.name).all()]


@router.post("", response_model=CustomerOut, status_code=201)
def create_customer(payload: CustomerIn, db: Session = Depends(get_db)):
    customer = Customer(**_clean(payload))
    db.add(customer)
    db.commit()
    return _out(db, customer)


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    return _out(db, _get_or_404(db, customer_id))


@router.put("/{customer_id}", response_model=CustomerOut)
def update_customer(customer_id: int, payload: CustomerIn, db: Session = Depends(get_db)):
    customer = _get_or_404(db, customer_id)
    if customer.anonymized_at:
        raise HTTPException(status_code=409, detail="Customer data was erased")
    for field, value in _clean(payload).items():
        setattr(customer, field, value)
    db.commit()
    return _out(db, customer)


@router.delete("/{customer_id}", status_code=204)
def delete_customer(customer_id: int, db: Session = Depends(get_db)):
    """Only a customer with no order and no document can be deleted; otherwise erase (GDPR)."""
    customer = _get_or_404(db, customer_id)
    data = _out(db, customer)
    if data["order_count"] or data["document_count"]:
        raise HTTPException(status_code=409, detail="Customer has orders or documents: erase personal data instead")
    db.delete(customer)
    db.commit()


@router.get("/{customer_id}/export")
def export_customer(customer_id: int, db: Session = Depends(get_db)):
    """GDPR right of access: everything held about this person, in one JSON file."""
    customer = _get_or_404(db, customer_id)
    orders = db.query(Order).filter(Order.customer_id == customer_id).order_by(Order.created_at).all()
    docs = db.query(SalesDocument).filter(SalesDocument.customer_id == customer_id).order_by(SalesDocument.id).all()
    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "customer": CustomerOut.model_validate(_out(db, customer)).model_dump(mode="json"),
        "orders": [
            {"id": o.id, "created_at": o.created_at.isoformat() if o.created_at else None, "status": o.status.value,
             "notes": o.notes, "lines": [{"model": line.knife_model.name, "quantity": line.quantity} for line in o.lines]}
            for o in orders
        ],
        "documents": [
            {"kind": d.kind.value, "number": d.number, "issue_date": d.issue_date.isoformat() if d.issue_date else None,
             "total_ttc": str(d.total_ttc), "buyer": d.buyer_snapshot}
            for d in docs
        ],
    }


@router.post("/{customer_id}/erase", response_model=CustomerOut)
def erase_customer(customer_id: int, db: Session = Depends(get_db)):
    """GDPR right to erasure. Personal data on the customer record and on its orders is
    removed. Issued invoices are NOT altered: French law requires keeping them 10 years
    (code de commerce L123-22, LPF L102 B); that legal obligation overrides erasure."""
    customer = _get_or_404(db, customer_id)
    label = f"Client effacé #{customer.id}"
    for field in ("company_name", "email", "phone", "address_line1", "address_line2", "postal_code", "city",
                  "delivery_line1", "delivery_postal_code", "delivery_city", "delivery_country", "siren", "vat_number", "notes"):
        setattr(customer, field, None)
    customer.name = label
    customer.anonymized_at = datetime.now(timezone.utc)
    for order in db.query(Order).filter(Order.customer_id == customer_id).all():
        order.customer_name = label
        order.customer_email = None
        order.notes = None
    db.commit()
    return _out(db, customer)
