import enum
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.material import Material
    from app.models.treatment import TreatmentRecipe


class MaterialRole(str, enum.Enum):
    BLADE = "blade"
    HANDLE = "handle"
    FITTING = "fitting"
    HARDWARE = "hardware"
    OTHER = "other"


class KnifeType(str, enum.Enum):
    FIXED = "fixed"
    FOLDER = "folder"
    KITCHEN = "kitchen"
    TABLE = "table"
    JAPANESE = "japanese"
    OTHER = "other"


class KnifeModel(Base):
    __tablename__ = "knife_models"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    knife_type: Mapped[KnifeType] = mapped_column(
        Enum(KnifeType, name="knife_type", values_callable=lambda e: [x.value for x in e]),
        default=KnifeType.FIXED,
    )
    # Estimated time to build ONE unit of this knife model, in hours.
    base_labor_hours: Mapped[float] = mapped_column(Float, default=0.0)
    sale_price: Mapped[float] = mapped_column(Float, default=0.0)
    # Overrides ShopSettings.default_margin_percent for this model only —
    # e.g. a folder might carry a higher margin than a simple fixed blade.
    margin_percent_override: Mapped[float | None] = mapped_column(Float, nullable=True)

    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    materials: Mapped[list["KnifeModelMaterial"]] = relationship(
        back_populates="knife_model", cascade="all, delete-orphan"
    )
    treatments: Mapped[list["KnifeModelTreatment"]] = relationship(
        back_populates="knife_model", cascade="all, delete-orphan", order_by="KnifeModelTreatment.step_order"
    )


class KnifeModelMaterial(Base):
    """One raw-material requirement of a knife model — how much of a given
    Material is consumed per unit built, expressed in whatever shape makes
    sense for that material's dimension_type."""

    __tablename__ = "knife_model_materials"

    id: Mapped[int] = mapped_column(primary_key=True)
    knife_model_id: Mapped[int] = mapped_column(ForeignKey("knife_models.id", ondelete="CASCADE"), nullable=False)
    knife_model: Mapped["KnifeModel"] = relationship(back_populates="materials")
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id", ondelete="RESTRICT"), nullable=False)
    material: Mapped["Material"] = relationship()

    role: Mapped[MaterialRole] = mapped_column(
        Enum(MaterialRole, name="material_role", values_callable=lambda e: [x.value for x in e]),
        default=MaterialRole.OTHER,
    )

    # For LENGTH materials: length of the blank cut from the bar (mm).
    blank_length_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    # For AREA materials: width of the blank, paired with blank_length_mm
    # to give the blank's area (mm x mm). Unused for LENGTH/COUNT.
    blank_width_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Descriptive only (doesn't affect stock math) — the stock thickness
    # this blank is cut from, for matching against Material.standard_thickness_mm.
    blank_thickness_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    # For COUNT materials: how many discrete units this knife needs.
    quantity: Mapped[float] = mapped_column(Float, default=1.0)


class KnifeModelTreatment(Base):
    """One step in a knife model's processing pipeline — a knife typically
    goes through several TreatmentRecipes in sequence (e.g. quench & temper,
    then an acid etch to reveal a damascus pattern, then a patina finish),
    so this is an ordered many-to-many, not a single FK."""

    __tablename__ = "knife_model_treatments"

    id: Mapped[int] = mapped_column(primary_key=True)
    knife_model_id: Mapped[int] = mapped_column(ForeignKey("knife_models.id", ondelete="CASCADE"), nullable=False)
    knife_model: Mapped["KnifeModel"] = relationship(back_populates="treatments")
    treatment_recipe_id: Mapped[int] = mapped_column(
        ForeignKey("treatment_recipes.id", ondelete="RESTRICT"), nullable=False
    )
    treatment_recipe: Mapped["TreatmentRecipe"] = relationship()
    step_order: Mapped[int] = mapped_column(Integer, default=0)
