from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.database import get_db
from app.schemas.dashboard import DashboardOut
from app.services.dashboard_service import build_dashboard

router = APIRouter(prefix="/api/admin/dashboard", tags=["dashboard"], dependencies=[Depends(require_admin)])


@router.get("", response_model=DashboardOut)
def dashboard(db: Session = Depends(get_db)):
    return build_dashboard(db)
