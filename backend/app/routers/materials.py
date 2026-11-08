from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.security import require_admin
from app.database import get_db
from app.models.material import Material
from app.schemas.cutting import CandidateOrderOut, CuttingOptimizeRequest, CuttingPlanOut
from app.schemas.stock_movement import StockMovementOut
from app.schemas.material import (
    MaterialCreate,
    MaterialOut,
    MaterialRestock,
    MaterialUpdate,
    YieldCalcRequest,
    YieldCalcResult,
)
from app.models.stock_movement import MovementReason, StockMovement
from app.services.costing_service import apply_weighted_average_restock
from app.services.stock_ledger import record_movement
from app.services.cutting_service import list_candidate_orders, optimize_cutting
from app.services.yield_service import compute_yield

router = APIRouter(prefix="/api/admin/materials", tags=["materials"], dependencies=[Depends(require_admin)])


def _query(db: Session):
    return db.query(Material).options(joinedload(Material.saw_blade))


@router.get("", response_model=list[MaterialOut])
def list_materials(db: Session = Depends(get_db)):
    return _query(db).order_by(Material.name).all()


@router.post("", response_model=MaterialOut, status_code=201)
def create_material(payload: MaterialCreate, db: Session = Depends(get_db)):
    material = Material(**payload.model_dump())
    db.add(material)
    db.flush()
    record_movement(db, material, material.quantity_in_stock, MovementReason.INITIAL)
    db.commit()
    return _query(db).filter(Material.id == material.id).first()


def _get_or_404(db: Session, material_id: int) -> Material:
    material = _query(db).filter(Material.id == material_id).first()
    if material is None:
        raise HTTPException(status_code=404, detail="Material not found")
    return material


@router.patch("/{material_id}", response_model=MaterialOut)
def update_material(material_id: int, payload: MaterialUpdate, db: Session = Depends(get_db)):
    material = _get_or_404(db, material_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(material, field, value)
    db.commit()
    return _get_or_404(db, material_id)


@router.post("/{material_id}/restock", response_model=MaterialOut)
def restock_material(material_id: int, payload: MaterialRestock, db: Session = Depends(get_db)):
    material = _get_or_404(db, material_id)
    try:
        apply_weighted_average_restock(material, payload.quantity_delta, payload.purchase_price, payload.shipping_cost)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    cost = (payload.purchase_price or 0.0) + (payload.shipping_cost or 0.0)
    record_movement(
        db,
        material,
        payload.quantity_delta,
        MovementReason.RESTOCK if cost > 0 else MovementReason.CORRECTION,
        cost=cost or None,
    )
    db.commit()
    return _get_or_404(db, material_id)


@router.post("/{material_id}/yield-calc", response_model=YieldCalcResult)
def yield_calc(material_id: int, payload: YieldCalcRequest, db: Session = Depends(get_db)):
    material = _get_or_404(db, material_id)
    try:
        return compute_yield(material, payload.blank_length_mm, payload.blank_width_mm, payload.quantity_needed)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{material_id}/cutting-candidates", response_model=list[CandidateOrderOut])
def cutting_candidates(material_id: int, db: Session = Depends(get_db)):
    return list_candidate_orders(db, material_id)


@router.post("/{material_id}/cutting-optimizer", response_model=CuttingPlanOut)
def cutting_optimizer(material_id: int, payload: CuttingOptimizeRequest, db: Session = Depends(get_db)):
    try:
        plan = optimize_cutting(db, material_id, payload.order_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return plan


@router.delete("/{material_id}", status_code=204)
def delete_material(material_id: int, db: Session = Depends(get_db)):
    material = _get_or_404(db, material_id)
    db.delete(material)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Material is used by one or more knife models") from exc


@router.get("/{material_id}/movements", response_model=list[StockMovementOut])
def stock_movements(material_id: int, limit: int = 200, db: Session = Depends(get_db)):
    """The ledger behind the stock figure, newest first."""
    _get_or_404(db, material_id)
    return (
        db.query(StockMovement)
        .filter(StockMovement.material_id == material_id)
        .order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
        .limit(min(max(limit, 1), 1000))
        .all()
    )
