from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.database import get_db
from app.schemas.production import ProductionOverviewOut
from app.services.production_service import build_overview

router = APIRouter(prefix="/api/admin/production", tags=["production"], dependencies=[Depends(require_admin)])


@router.get("/overview", response_model=ProductionOverviewOut)
def overview(db: Session = Depends(get_db)):
    return build_overview(db)
