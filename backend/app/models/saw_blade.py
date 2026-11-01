import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SawType(str, enum.Enum):
    BAND_SAW = "band_saw"
    CIRCULAR_SAW = "circular_saw"
    ABRASIVE_CUTOFF = "abrasive_cutoff"
    HACKSAW = "hacksaw"
    OTHER = "other"


class SawBlade(Base):
    """A reusable saw/blade catalog entry — kerf width is a property of the
    physical tool doing the cutting, not something to guess per material.
    A Material references one of these (optionally) to auto-fill its
    kerf_mm; the resolved kerf_mm on the material stays the number actually
    used in yield/cutting-optimizer math, editable independently in case a
    maker's real-world kerf differs slightly from the catalog nominal
    value (blade wear, wobble, etc.)."""

    __tablename__ = "saw_blades"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    saw_type: Mapped[SawType] = mapped_column(
        Enum(SawType, name="saw_type", values_callable=lambda e: [x.value for x in e]), nullable=False
    )
    # Blade/disc diameter — meaningful for circular saws and abrasive
    # cutoff wheels, not for band saws or hacksaws.
    diameter_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    kerf_mm: Mapped[float] = mapped_column(Float, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
