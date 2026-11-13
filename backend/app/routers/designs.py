from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload

from app.core.security import require_admin
from app.database import get_db
from app.models.design import Design
from app.models.knife_model import KnifeModel
from app.models.material import Material
from app.schemas.design import (
    DesignCreate,
    DesignDocument,
    DesignOut,
    DesignSummaryOut,
    DesignUpdate,
    OffsetRequest,
    OffsetResult,
)
from app.services.shop_settings_service import get_shop_settings
from app.services import design_templates, export_service, parts_sheet
from app.services.geometry_service import compute_metrics, offset_contours

router = APIRouter(prefix="/api/admin/designs", tags=["designs"], dependencies=[Depends(require_admin)])


def _query(db: Session):
    return db.query(Design).options(joinedload(Design.knife_model), joinedload(Design.material))


def _get_or_404(db: Session, design_id: int) -> Design:
    design = _query(db).filter(Design.id == design_id).first()
    if design is None:
        raise HTTPException(status_code=404, detail="Design not found")
    return design


def _check_refs(db: Session, knife_model_id: int | None, material_id: int | None) -> None:
    if knife_model_id is not None and db.query(KnifeModel.id).filter(KnifeModel.id == knife_model_id).first() is None:
        raise HTTPException(status_code=400, detail="Knife model not found")
    if material_id is not None and db.query(Material.id).filter(Material.id == material_id).first() is None:
        raise HTTPException(status_code=400, detail="Material not found")


def _apply_metrics(design: Design, document: DesignDocument) -> None:
    metrics = compute_metrics(document)
    design.document = document.model_dump(mode="json")
    design.width_mm = metrics.width_mm
    design.height_mm = metrics.height_mm
    design.area_mm2 = metrics.area_mm2
    design.perimeter_mm = metrics.perimeter_mm
    design.part_count = metrics.part_count


@router.get("", response_model=list[DesignSummaryOut])
def list_designs(
    knife_model_id: int | None = Query(default=None),
    material_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    query = _query(db)
    if knife_model_id is not None:
        query = query.filter(Design.knife_model_id == knife_model_id)
    if material_id is not None:
        query = query.filter(Design.material_id == material_id)
    return query.order_by(Design.name).all()


@router.post("", response_model=DesignOut, status_code=201)
def create_design(payload: DesignCreate, db: Session = Depends(get_db)):
    _check_refs(db, payload.knife_model_id, payload.material_id)
    design = Design(
        name=payload.name,
        kind=payload.kind,
        notes=payload.notes,
        knife_model_id=payload.knife_model_id,
        material_id=payload.material_id,
        document={},
    )
    _apply_metrics(design, payload.document)
    db.add(design)
    db.commit()
    return _get_or_404(db, design.id)


@router.get("/templates")
def templates():
    """Starting points for the editor's "new design" dialog."""
    return design_templates.list_templates()


@router.post("/geometry/offset", response_model=OffsetResult)
def offset_shape(payload: OffsetRequest):
    """Grow or shrink a closed shape (e.g. add a kerf allowance, inset a scale)."""
    try:
        contours = offset_contours(payload.contours, payload.distance_mm, payload.join)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return OffsetResult(contours=contours)


@router.get("/{design_id}", response_model=DesignOut)
def get_design(design_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, design_id)


@router.patch("/{design_id}", response_model=DesignOut)
def update_design(design_id: int, payload: DesignUpdate, db: Session = Depends(get_db)):
    design = _get_or_404(db, design_id)
    data = payload.model_dump(exclude_unset=True, exclude={"document", "background"})
    _check_refs(db, data.get("knife_model_id"), data.get("material_id"))
    for field, value in data.items():
        setattr(design, field, value)
    if payload.document is not None:
        _apply_metrics(design, payload.document)
    if "background" in payload.model_fields_set:
        design.background = payload.background.model_dump(mode="json") if payload.background else None
    db.commit()
    return _get_or_404(db, design_id)


@router.post("/{design_id}/duplicate", response_model=DesignOut, status_code=201)
def duplicate_design(design_id: int, db: Session = Depends(get_db)):
    source = _get_or_404(db, design_id)
    copy = Design(
        name=f"{source.name} (copie)"[:150],
        kind=source.kind,
        notes=source.notes,
        knife_model_id=source.knife_model_id,
        material_id=source.material_id,
        document=source.document,
        background=source.background,
        width_mm=source.width_mm,
        height_mm=source.height_mm,
        area_mm2=source.area_mm2,
        perimeter_mm=source.perimeter_mm,
        part_count=source.part_count,
    )
    db.add(copy)
    db.commit()
    return _get_or_404(db, copy.id)


@router.delete("/{design_id}", status_code=204)
def delete_design(design_id: int, db: Session = Depends(get_db)):
    design = _get_or_404(db, design_id)
    db.delete(design)
    db.commit()


def _document(design: Design) -> DesignDocument:
    return DesignDocument.model_validate(design.document)


def _safe_filename(name: str, extension: str) -> str:
    stem = "".join(c if c.isalnum() or c in "-_" else "_" for c in name).strip("_") or "design"
    return f"{stem}.{extension}"


@router.get("/{design_id}/export.svg")
def export_svg(
    design_id: int,
    kerf: float = Query(default=0.0, ge=0, le=export_service.MAX_KERF_MM, description="Kerf to compensate (mm)"),
    db: Session = Depends(get_db),
):
    design = _get_or_404(db, design_id)
    try:
        svg = export_service.design_to_svg(_document(design), kerf_mm=kerf)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(
        svg,
        media_type="image/svg+xml",
        headers={"Content-Disposition": f'attachment; filename="{_safe_filename(design.name, "svg")}"'},
    )


@router.get("/{design_id}/export.dxf")
def export_dxf(
    design_id: int,
    curves: str = Query(default="polylines", pattern="^(polylines|arcs)$"),
    kerf: float = Query(default=0.0, ge=0, le=export_service.MAX_KERF_MM, description="Kerf to compensate (mm)"),
    db: Session = Depends(get_db),
):
    design = _get_or_404(db, design_id)
    try:
        data = export_service.design_to_dxf(_document(design), curves=curves, kerf_mm=kerf)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(
        data,
        media_type="application/dxf",
        headers={"Content-Disposition": f'attachment; filename="{_safe_filename(design.name, "dxf")}"'},
    )


@router.get("/{design_id}/parts.pdf")
def export_parts_sheet(
    design_id: int,
    paper: str = Query(default="A4", pattern="^(A4|A3)$"),
    db: Session = Depends(get_db),
):
    """The parts at true size, tiled over several pages if needed, with punch marks."""
    design = _get_or_404(db, design_id)
    try:
        pdf = parts_sheet.parts_sheet_pdf(_document(design), title=design.name, paper=paper, workshop=get_shop_settings(db).workshop_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{_safe_filename(design.name + "-pieces", "pdf")}"'},
    )


@router.get("/{design_id}/plan.svg")
def plan(
    design_id: int,
    paper: str = Query(default="A4", pattern="^(A4|A3)$"),
    scale: float | None = Query(default=None, gt=0, le=1000, description="Scale denominator (2 = 1:2). Auto if omitted."),
    customer: str | None = Query(default=None, max_length=120),
    order_ref: str | None = Query(default=None, max_length=60),
    title: str | None = Query(default=None, max_length=120),
    notes: str | None = Query(default=None, max_length=200),
    download: bool = False,
    db: Session = Depends(get_db),
):
    design = _get_or_404(db, design_id)
    shop = get_shop_settings(db)
    try:
        svg = export_service.plan_svg(
            _document(design),
            title=title or design.name,
            paper=paper,
            scale_denominator=scale,
            customer=customer,
            order_ref=order_ref,
            knife_model=design.knife_model_name,
            material=design.material_name,
            notes=notes or design.notes,
            workshop_name=shop.workshop_name,
            workshop_contact=shop.workshop_contact,
            workshop_logo=shop.workshop_logo,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    headers = {}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{_safe_filename("plan_" + design.name, "svg")}"'
    return Response(svg, media_type="image/svg+xml", headers=headers)
