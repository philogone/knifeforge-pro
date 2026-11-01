from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.database import get_db
from app.schemas.nesting import (
    NestingCandidatesOut,
    NestingExportRequest,
    NestingRequest,
    NestingResultOut,
    PlacementOut,
    SheetOut,
    UnplacedOut,
)
from app.services import export_service
from app.services.nesting_service import NestingResult, list_candidates, placement_rings, run_nesting

router = APIRouter(prefix="/api/admin/nesting", tags=["nesting"], dependencies=[Depends(require_admin)])


def _run(db: Session, request: NestingRequest) -> NestingResult:
    try:
        return run_nesting(
            db,
            material_id=request.material_id,
            explicit=[(i.design_id, i.quantity) for i in request.items],
            order_ids=request.order_ids,
            spacing_mm=request.spacing_mm,
            margin_mm=request.margin_mm,
            rotations=request.rotations,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _to_out(result: NestingResult) -> NestingResultOut:
    sheets = []
    for sheet in result.sheets:
        used = sheet.used_area()
        sheets.append(
            SheetOut(
                index=sheet.index,
                used_area_mm2=round(used, 2),
                utilization_pct=round(used / result.sheet_area * 100, 2) if result.sheet_area else 0.0,
                placements=[
                    PlacementOut(
                        design_id=p.item.design_id,
                        design_name=p.item.design_name,
                        part_name=p.item.part_name,
                        instance=p.item.instance,
                        order_id=p.item.order_id,
                        customer_name=p.item.customer_name,
                        x=p.x,
                        y=p.y,
                        rotation_deg=p.rotation_deg,
                        outline=placement_rings(p),
                    )
                    for p in sheet.placements
                ],
            )
        )
    return NestingResultOut(
        material_id=result.material_id,
        material_name=result.material_name,
        sheet_length_mm=result.sheet_length_mm,
        sheet_width_mm=result.sheet_width_mm,
        spacing_mm=result.spacing_mm,
        margin_mm=result.margin_mm,
        total_parts=result.total_parts,
        placed_parts=result.placed_parts,
        sheets_needed=result.sheets_needed,
        utilization_pct=result.utilization_pct,
        waste_area_mm2=result.waste_area,
        stock_sheets_available=result.stock_sheets_available,
        stock_sufficient=result.stock_sufficient,
        sheets=sheets,
        unplaced=[
            UnplacedOut(
                design_id=u.item.design_id, design_name=u.item.design_name, part_name=u.item.part_name, reason=u.reason
            )
            for u in result.unplaced
        ],
    )


@router.get("/candidates", response_model=NestingCandidatesOut)
def candidates(material_id: int = Query(...), db: Session = Depends(get_db)):
    found = list_candidates(db, material_id)
    return NestingCandidatesOut(orders=found.orders, designs=found.designs)


@router.post("/run", response_model=NestingResultOut)
def run(payload: NestingRequest, db: Session = Depends(get_db)):
    return _to_out(_run(db, payload))


@router.post("/export")
def export(payload: NestingExportRequest, db: Session = Depends(get_db)):
    """Re-runs the (deterministic) nesting and returns one sheet as SVG or DXF."""
    result = _run(db, payload.request)
    try:
        if payload.format == "dxf":
            body = export_service.nesting_to_dxf(result, payload.sheet_index)
            media = "application/dxf"
        else:
            body = export_service.nesting_to_svg(result, payload.sheet_index).encode("utf-8")
            media = "image/svg+xml"
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    filename = f"nesting_sheet_{payload.sheet_index + 1}.{payload.format}"
    return Response(body, media_type=media, headers={"Content-Disposition": f'attachment; filename="{filename}"'})
