from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.database import get_db
from app.models.treatment import TreatmentRecipe, TreatmentStep
from app.schemas.treatment import TreatmentRecipeCreate, TreatmentRecipeOut, TreatmentRecipeUpdate

router = APIRouter(prefix="/api/admin/treatment-recipes", tags=["treatments"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[TreatmentRecipeOut])
def list_recipes(db: Session = Depends(get_db)):
    return db.query(TreatmentRecipe).order_by(TreatmentRecipe.name).all()


@router.post("", response_model=TreatmentRecipeOut, status_code=201)
def create_recipe(payload: TreatmentRecipeCreate, db: Session = Depends(get_db)):
    data = payload.model_dump(exclude={"steps"})
    recipe = TreatmentRecipe(**data)
    recipe.steps = [TreatmentStep(**step.model_dump()) for step in payload.steps]
    db.add(recipe)
    db.commit()
    db.refresh(recipe)
    return recipe


def _get_or_404(db: Session, recipe_id: int) -> TreatmentRecipe:
    recipe = db.query(TreatmentRecipe).filter(TreatmentRecipe.id == recipe_id).first()
    if recipe is None:
        raise HTTPException(status_code=404, detail="Treatment recipe not found")
    return recipe


@router.patch("/{recipe_id}", response_model=TreatmentRecipeOut)
def update_recipe(recipe_id: int, payload: TreatmentRecipeUpdate, db: Session = Depends(get_db)):
    recipe = _get_or_404(db, recipe_id)
    data = payload.model_dump(exclude_unset=True, exclude={"steps"})
    for field, value in data.items():
        setattr(recipe, field, value)
    if payload.steps is not None:
        recipe.steps = [TreatmentStep(**step.model_dump()) for step in payload.steps]
    db.commit()
    db.refresh(recipe)
    return recipe


@router.delete("/{recipe_id}", status_code=204)
def delete_recipe(recipe_id: int, db: Session = Depends(get_db)):
    recipe = _get_or_404(db, recipe_id)
    db.delete(recipe)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Recipe is used by one or more knife models") from exc
