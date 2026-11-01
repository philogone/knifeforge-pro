import enum
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.knife_model import KnifeModel
    from app.models.material import Material


class DesignKind(str, enum.Enum):
    BLADE = "blade"
    HANDLE_SCALE = "handle_scale"
    GUARD = "guard"
    BOLSTER = "bolster"
    SHEATH = "sheath"
    TEMPLATE = "template"
    OTHER = "other"


class Design(Base):
    """A 2D vector pattern (gabarit) drawn in the built-in editor, in real-world
    millimetres. ``document`` is the editor's own JSON format (layers + Bézier
    paths + dimension annotations — see ``app.schemas.design.DesignDocument``);
    the numeric columns below are derived from it on every save so lists, the
    cost/stock views and the nesting preview never have to re-parse geometry.
    """

    __tablename__ = "designs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    kind: Mapped[DesignKind] = mapped_column(
        Enum(DesignKind, name="design_kind", values_callable=lambda e: [x.value for x in e]),
        default=DesignKind.BLADE,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Which knife model this pattern belongs to, and which stock material it is
    # cut from (drives the nesting planner). Both are optional and SET NULL on
    # delete: removing a model or material never destroys the drawing itself.
    knife_model_id: Mapped[int | None] = mapped_column(
        ForeignKey("knife_models.id", ondelete="SET NULL"), nullable=True, index=True
    )
    knife_model: Mapped["KnifeModel | None"] = relationship()
    material_id: Mapped[int | None] = mapped_column(
        ForeignKey("materials.id", ondelete="SET NULL"), nullable=True, index=True
    )
    material: Mapped["Material | None"] = relationship()

    document: Mapped[dict] = mapped_column(JSON, nullable=False)
    # Optional reference image for tracing (see DesignBackground). Kept out of
    # `document` so geometry, exports and nesting never see it.
    background: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Derived metrics (recomputed from `document` by geometry_service on save).
    width_mm: Mapped[float] = mapped_column(Float, default=0.0)
    height_mm: Mapped[float] = mapped_column(Float, default=0.0)
    area_mm2: Mapped[float] = mapped_column(Float, default=0.0)
    perimeter_mm: Mapped[float] = mapped_column(Float, default=0.0)
    part_count: Mapped[int] = mapped_column(Integer, default=0)

    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    @property
    def knife_model_name(self) -> str | None:
        return self.knife_model.name if self.knife_model else None

    @property
    def material_name(self) -> str | None:
        return self.material.name if self.material else None
