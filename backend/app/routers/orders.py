from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.database import get_db
from app.models.customer import Customer
from app.models.order import Order, OrderLine, OrderStatus
from app.schemas.order import FeasibilityResult, OrderCreate, OrderOut, OrderUpdate
from app.services.order_service import (
    OrderConfirmError,
    cancel_order,
    check_feasibility,
    complete_order,
    confirm_order,
    load_order_with_relations,
)

router = APIRouter(prefix="/api/admin/orders", tags=["orders"], dependencies=[Depends(require_admin)])


def _to_out(order: Order) -> dict:
    return {
        "id": order.id,
        "customer_name": order.customer_name,
        "customer_email": order.customer_email,
        "status": order.status,
        "notes": order.notes,
        "customer_id": order.customer_id,
        "due_date": order.due_date,
        "stage": order.stage,
        "is_mock": order.is_mock,
        "created_at": order.created_at,
        "lines": [
            {
                "id": line.id,
                "knife_model_id": line.knife_model_id,
                "knife_model_name": line.knife_model.name,
                "quantity": line.quantity,
            }
            for line in order.lines
        ],
    }


@router.get("", response_model=list[OrderOut])
def list_orders(db: Session = Depends(get_db)):
    orders = db.query(Order).order_by(Order.created_at.desc()).all()
    return [_to_out(load_order_with_relations(db, o.id)) for o in orders]


@router.post("", response_model=OrderOut, status_code=201)
def create_order(payload: OrderCreate, db: Session = Depends(get_db)):
    name, email = payload.customer_name, payload.customer_email
    if payload.customer_id is not None:
        customer = db.get(Customer, payload.customer_id)
        if customer is None:
            raise HTTPException(status_code=404, detail="Customer not found")
        name, email = customer.company_name if customer.is_business and customer.company_name else customer.name, customer.email
    if not name:
        raise HTTPException(status_code=422, detail="customer_id or customer_name is required")
    order = Order(
        customer_id=payload.customer_id, customer_name=name, customer_email=email, notes=payload.notes, due_date=payload.due_date
    )
    order.lines = [OrderLine(**line.model_dump()) for line in payload.lines]
    db.add(order)
    db.commit()
    return _to_out(load_order_with_relations(db, order.id))


def _get_or_404(db: Session, order_id: int) -> Order:
    order = load_order_with_relations(db, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db)):
    return _to_out(_get_or_404(db, order_id))


@router.patch("/{order_id}", response_model=OrderOut)
def update_order(order_id: int, payload: OrderUpdate, db: Session = Depends(get_db)):
    order = _get_or_404(db, order_id)
    if order.status != OrderStatus.DRAFT and payload.lines is not None:
        raise HTTPException(status_code=409, detail="Only draft orders can have their lines edited")
    data = payload.model_dump(exclude_unset=True, exclude={"lines"})
    if data.get("customer_id"):
        customer = db.get(Customer, data["customer_id"])
        if customer is None:
            raise HTTPException(status_code=404, detail="Customer not found")
        data.setdefault("customer_name", customer.company_name if customer.is_business and customer.company_name else customer.name)
        data.setdefault("customer_email", customer.email)
    for field, value in data.items():
        setattr(order, field, value)
    if payload.lines is not None:
        order.lines = [OrderLine(**line.model_dump()) for line in payload.lines]
    db.commit()
    return _to_out(_get_or_404(db, order_id))


@router.get("/{order_id}/feasibility", response_model=FeasibilityResult)
def get_feasibility(order_id: int, db: Session = Depends(get_db)):
    order = _get_or_404(db, order_id)
    if not order.lines:
        return FeasibilityResult(feasible=True, materials=[])
    return check_feasibility(db, order)


@router.post("/{order_id}/confirm", response_model=OrderOut)
def confirm(order_id: int, db: Session = Depends(get_db)):
    order = _get_or_404(db, order_id)
    try:
        confirm_order(db, order)
    except OrderConfirmError as exc:
        raise HTTPException(status_code=409, detail={"message": "Insufficient stock", "feasibility": exc.result.model_dump()}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _to_out(_get_or_404(db, order_id))


@router.post("/{order_id}/cancel", response_model=OrderOut)
def cancel(order_id: int, db: Session = Depends(get_db)):
    order = _get_or_404(db, order_id)
    try:
        cancel_order(db, order)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _to_out(_get_or_404(db, order_id))


@router.post("/{order_id}/complete", response_model=OrderOut)
def complete(order_id: int, db: Session = Depends(get_db)):
    order = _get_or_404(db, order_id)
    try:
        complete_order(db, order)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _to_out(_get_or_404(db, order_id))


@router.delete("/{order_id}", status_code=204)
def delete_order(order_id: int, db: Session = Depends(get_db)):
    order = _get_or_404(db, order_id)
    if order.status not in (OrderStatus.DRAFT, OrderStatus.CANCELLED):
        raise HTTPException(status_code=409, detail="Only draft or cancelled orders can be deleted")
    db.delete(order)
    db.commit()
