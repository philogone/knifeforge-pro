from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.database import get_db
from app.models.saw_blade import SawBlade
from app.schemas.saw_blade import SawBladeCreate, SawBladeOut, SawBladeUpdate

router = APIRouter(prefix="/api/admin/saw-blades", tags=["saw-blades"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[SawBladeOut])
def list_saw_blades(db: Session = Depends(get_db)):
    return db.query(SawBlade).order_by(SawBlade.name).all()


@router.post("", response_model=SawBladeOut, status_code=201)
def create_saw_blade(payload: SawBladeCreate, db: Session = Depends(get_db)):
    blade = SawBlade(**payload.model_dump())
    db.add(blade)
    db.commit()
    db.refresh(blade)
    return blade


def _get_or_404(db: Session, blade_id: int) -> SawBlade:
    blade = db.query(SawBlade).filter(SawBlade.id == blade_id).first()
    if blade is None:
        raise HTTPException(status_code=404, detail="Saw blade not found")
    return blade


@router.patch("/{blade_id}", response_model=SawBladeOut)
def update_saw_blade(blade_id: int, payload: SawBladeUpdate, db: Session = Depends(get_db)):
    blade = _get_or_404(db, blade_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(blade, field, value)
    db.commit()
    db.refresh(blade)
    return blade


@router.delete("/{blade_id}", status_code=204)
def delete_saw_blade(blade_id: int, db: Session = Depends(get_db)):
    # Materials referencing this blade have saw_blade_id set to NULL by the
    # DB (ondelete="SET NULL") — their kerf_mm is unaffected either way.
    blade = _get_or_404(db, blade_id)
    db.delete(blade)
    db.commit()
