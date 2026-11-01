import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TreatmentType(str, enum.Enum):
    """A recipe can be a thermal process or a chemical/finishing process —
    both are just an ordered sequence of steps with a temperature, a
    duration, and a medium, so one schema covers both instead of splitting
    into unrelated "heat treatment" vs "chemical treatment" tables."""

    HEAT_TREATMENT = "heat_treatment"  # quench, temper, anneal, normalize
    DAMASCUS_ETCH = "damascus_etch"  # acid etch to reveal the pattern-weld
    BLUING = "bluing"  # hot or rust bluing finish
    BROWNING = "browning"  # traditional rust browning (brunissement)
    ACID_PATINA = "acid_patina"  # forced patina / darkening (ternissement)
    OTHER = "other"


class TreatmentRecipe(Base):
    __tablename__ = "treatment_recipes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    treatment_type: Mapped[TreatmentType] = mapped_column(
        Enum(TreatmentType, name="treatment_type", values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )
    # Free-text material scope (e.g. "1095 / high-carbon steel",
    # "pattern-welded damascus only") — not a Material FK, since a recipe
    # describes what it applies to in the maker's own words, not a specific
    # stock item.
    applies_to: Mapped[str] = mapped_column(String(150), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    steps: Mapped[list["TreatmentStep"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan", order_by="TreatmentStep.step_order"
    )


class TreatmentStep(Base):
    __tablename__ = "treatment_steps"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("treatment_recipes.id", ondelete="CASCADE"), nullable=False)
    recipe: Mapped["TreatmentRecipe"] = relationship(back_populates="steps")

    step_order: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    # e.g. quench oil temp, or an etchant bath temp — nullable since a step
    # like "air cool to room temperature" has no target temperature.
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    # e.g. "quench oil", "ferric chloride 1:3", "vinegar + salt solution"
    medium: Mapped[str | None] = mapped_column(String(150), nullable=True)
