from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.core.security import require_admin
from app.database import get_db
from app.models.design import Design
from app.models.knife_model import KnifeModel
from app.models.material import Material
from app.models.order import Order
from app.models.saw_blade import SawBlade
from app.models.treatment import TreatmentRecipe
from app.routers.knife_models import _query as _knife_model_query
from app.routers.knife_models import _to_out as _knife_model_to_out
from app.routers.orders import _to_out as _order_to_out
from app.schemas.design import DesignOut
from app.schemas.knife_model import KnifeModelOut
from app.schemas.material import MaterialOut
from app.schemas.order import OrderOut
from app.schemas.saw_blade import SawBladeOut
from app.schemas.shop_settings import ShopSettingsOut, ShopSettingsUpdate
from app.schemas.treatment import TreatmentRecipeOut
from app.services.order_service import load_order_with_relations
from app.services.seed_service import clear_mock_data, seed_mock_data, seed_mock_designs
from app.services.shop_settings_service import get_shop_settings

router = APIRouter(prefix="/api/admin/settings", tags=["settings"], dependencies=[Depends(require_admin)])


@router.get("/shop", response_model=ShopSettingsOut)
def get_shop(db: Session = Depends(get_db)):
    return get_shop_settings(db)


@router.patch("/shop", response_model=ShopSettingsOut)
def update_shop(payload: ShopSettingsUpdate, db: Session = Depends(get_db)):
    settings = get_shop_settings(db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(settings, field, value)
    db.commit()
    db.refresh(settings)
    return settings


@router.get("/mock-data")
def mock_data_status(db: Session = Depends(get_db)):
    enabled = db.query(Material).filter(Material.is_mock.is_(True)).first() is not None
    return {"enabled": enabled}


@router.post("/mock-data/seed")
def seed(db: Session = Depends(get_db)):
    created = seed_mock_data(db)
    created += seed_mock_designs(db)
    return {"seeded": created}


@router.post("/mock-data/clear")
def clear(db: Session = Depends(get_db)):
    removed = clear_mock_data(db)
    return {"removed": removed}


@router.get("/export")
def export_data(db: Session = Depends(get_db)):
    """Full JSON backup of everything in the database (including demo data,
    flagged via is_mock on each record) — a maker's own copy of their
    catalog, recipes, knife models, and order history, downloadable from
    the browser. Not an automatic scheduled backup; the maker triggers it
    from Settings whenever they want a snapshot."""
    materials = db.query(Material).options(joinedload(Material.saw_blade)).order_by(Material.name).all()
    saw_blades = db.query(SawBlade).order_by(SawBlade.name).all()
    recipes = db.query(TreatmentRecipe).order_by(TreatmentRecipe.name).all()
    knife_models = _knife_model_query(db).order_by(KnifeModel.name).all()
    orders = db.query(Order).order_by(Order.created_at).all()
    designs = db.query(Design).options(joinedload(Design.knife_model), joinedload(Design.material)).order_by(Design.name).all()
    shop = get_shop_settings(db)

    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "shop_settings": ShopSettingsOut.model_validate(shop).model_dump(mode="json"),
        "materials": [MaterialOut.model_validate(m).model_dump(mode="json") for m in materials],
        "saw_blades": [SawBladeOut.model_validate(b).model_dump(mode="json") for b in saw_blades],
        "treatment_recipes": [TreatmentRecipeOut.model_validate(r).model_dump(mode="json") for r in recipes],
        "knife_models": [
            KnifeModelOut.model_validate(_knife_model_to_out(m)).model_dump(mode="json") for m in knife_models
        ],
        "orders": [
            OrderOut.model_validate(_order_to_out(load_order_with_relations(db, o.id))).model_dump(mode="json")
            for o in orders
        ],
        "designs": [DesignOut.model_validate(d).model_dump(mode="json") for d in designs],
    }
