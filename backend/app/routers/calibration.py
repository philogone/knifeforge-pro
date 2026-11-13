from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.database import get_db
from app.schemas.calibration import AnalysisOut, CalibrationIn, FeatureOut
from app.services import calibration
from app.services.shop_settings_service import get_shop_settings

router = APIRouter(prefix="/api/admin/calibration", tags=["calibration"], dependencies=[Depends(require_admin)])


@router.get("/features", response_model=list[FeatureOut])
def features():
    """The dimensions to measure on the calibration plate."""
    return [asdict(f) for f in calibration.FEATURES]


@router.post("/analyse", response_model=AnalysisOut)
def analyse(payload: CalibrationIn):
    """Errors, real kerf and machine scale from the caliper readings."""
    try:
        return asdict(calibration.analyse(payload.kerf_used_mm, payload.measurements))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/sheet.pdf")
def sheet(
    kerf: float = Query(default=0.0, ge=0, le=calibration.MAX_KERF_MM),
    machine: str | None = Query(default=None, max_length=80),
    material: str | None = Query(default=None, max_length=80),
    db: Session = Depends(get_db),
):
    """The measurement sheet: the parts at 1:1 with their letters and the table to fill in."""
    pdf = calibration.sheet_pdf(kerf, machine, material, get_shop_settings(db).workshop_name)
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="planche-de-controle-releve.pdf"'})
