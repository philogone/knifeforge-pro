from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.security import require_admin
from app.database import get_db
from app.models.knife_model import KnifeModel, KnifeModelMaterial, KnifeModelTreatment
from app.schemas.costing import CostBreakdownOut
from app.schemas.knife_model import KnifeModelCreate, KnifeModelOut, KnifeModelUpdate
from app.services.costing_service import compute_full_costing
from app.services.shop_settings_service import get_shop_settings

router = APIRouter(prefix="/api/admin/knife-models", tags=["knife-models"], dependencies=[Depends(require_admin)])


def _query(db: Session):
    return db.query(KnifeModel).options(
        joinedload(KnifeModel.materials).joinedload(KnifeModelMaterial.material),
        joinedload(KnifeModel.treatments).joinedload(KnifeModelTreatment.treatment_recipe),
    )


def _to_out(model: KnifeModel) -> dict:
    data = {
        "id": model.id,
        "name": model.name,
        "knife_type": model.knife_type,
        "base_labor_hours": model.base_labor_hours,
        "sale_price": model.sale_price,
        "margin_percent_override": model.margin_percent_override,
        "is_mock": model.is_mock,
        "created_at": model.created_at,
        "materials": [
            {
                "id": m.id,
                "material_id": m.material_id,
                "material_name": m.material.name,
                "role": m.role,
                "blank_length_mm": m.blank_length_mm,
                "blank_width_mm": m.blank_width_mm,
                "blank_thickness_mm": m.blank_thickness_mm,
                "quantity": m.quantity,
            }
            for m in model.materials
        ],
        "treatments": [
            {
                "id": t.id,
                "treatment_recipe_id": t.treatment_recipe_id,
                "treatment_recipe_name": t.treatment_recipe.name,
                "step_order": t.step_order,
            }
            for t in model.treatments
        ],
    }
    return data


@router.get("", response_model=list[KnifeModelOut])
def list_knife_models(db: Session = Depends(get_db)):
    models = _query(db).order_by(KnifeModel.name).all()
    return [_to_out(m) for m in models]


@router.post("", response_model=KnifeModelOut, status_code=201)
def create_knife_model(payload: KnifeModelCreate, db: Session = Depends(get_db)):
    model = KnifeModel(
        name=payload.name,
        knife_type=payload.knife_type,
        base_labor_hours=payload.base_labor_hours,
        sale_price=payload.sale_price,
        margin_percent_override=payload.margin_percent_override,
    )
    model.materials = [KnifeModelMaterial(**m.model_dump()) for m in payload.materials]
    model.treatments = [KnifeModelTreatment(**t.model_dump()) for t in payload.treatments]
    db.add(model)
    db.commit()
    return _to_out(_query(db).filter(KnifeModel.id == model.id).first())


def _get_or_404(db: Session, model_id: int) -> KnifeModel:
    model = _query(db).filter(KnifeModel.id == model_id).first()
    if model is None:
        raise HTTPException(status_code=404, detail="Knife model not found")
    return model


@router.patch("/{model_id}", response_model=KnifeModelOut)
def update_knife_model(model_id: int, payload: KnifeModelUpdate, db: Session = Depends(get_db)):
    model = _get_or_404(db, model_id)
    data = payload.model_dump(exclude_unset=True, exclude={"materials", "treatments"})
    for field, value in data.items():
        setattr(model, field, value)
    if payload.materials is not None:
        model.materials = [KnifeModelMaterial(**m.model_dump()) for m in payload.materials]
    if payload.treatments is not None:
        model.treatments = [KnifeModelTreatment(**t.model_dump()) for t in payload.treatments]
    db.commit()
    return _to_out(_query(db).filter(KnifeModel.id == model_id).first())


@router.get("/{model_id}/cost-breakdown", response_model=CostBreakdownOut)
def cost_breakdown(model_id: int, db: Session = Depends(get_db)):
    model = _get_or_404(db, model_id)
    return compute_full_costing(model, get_shop_settings(db))


@router.delete("/{model_id}", status_code=204)
def delete_knife_model(model_id: int, db: Session = Depends(get_db)):
    model = _get_or_404(db, model_id)
    db.delete(model)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Knife model is used by one or more orders") from exc
