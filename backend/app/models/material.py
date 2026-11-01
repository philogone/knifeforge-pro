import enum
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Enum, Float, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.saw_blade import SawBlade


class MaterialCategory(str, enum.Enum):
    BLADE_STEEL = "blade_steel"
    HANDLE_MATERIAL = "handle_material"
    FITTING = "fitting"  # bolsters, guards, pommels, mitres — structural/decorative metal parts
    HARDWARE = "hardware"  # rivets, screws, pocket clips, small fasteners
    CONSUMABLE = "consumable"


class MetalType(str, enum.Enum):
    STAINLESS_STEEL = "stainless_steel"
    CARBON_STEEL = "carbon_steel"
    TITANIUM = "titanium"
    MOKUME_GANE = "mokume_gane"
    BRASS = "brass"
    COPPER = "copper"
    NICKEL_SILVER = "nickel_silver"
    OTHER = "other"


class DimensionType(str, enum.Enum):
    """How stock QUANTITY for this material is measured and consumed —
    orthogonal to its physical length/width/thickness, which are always
    available as descriptive fields regardless of this value.

    LENGTH: bar/rod stock, tracked and consumed in millimeters (e.g. steel
    flat bar for blades). AREA: sheet stock, tracked and consumed in square
    millimeters (e.g. handle scales cut from a sheet). COUNT: discrete
    pre-shaped units, tracked and consumed as whole items (e.g. pins,
    rivets, pre-cut handle blocks) — no cutting math applies, but the piece
    still has real dimensions worth recording (e.g. a scale pair's size).
    """

    LENGTH = "length"
    AREA = "area"
    COUNT = "count"


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[MaterialCategory] = mapped_column(
        Enum(MaterialCategory, name="material_category", values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )
    dimension_type: Mapped[DimensionType] = mapped_column(
        Enum(DimensionType, name="dimension_type", values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )

    # Metal classification — relevant for BLADE_STEEL and FITTING materials.
    # metal_type is the broad family (for filtering); steel_grade is the
    # specific commercial reference (e.g. "1095", "N690Co", "RWL34") —
    # free text since grade naming isn't standardized across suppliers.
    metal_type: Mapped[MetalType | None] = mapped_column(
        Enum(MetalType, name="metal_type", values_callable=lambda e: [x.value for x in e]), nullable=True
    )
    steel_grade: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Wood-specific descriptors — relevant for HANDLE_MATERIAL made of wood.
    wood_species: Mapped[str | None] = mapped_column(String(100), nullable=True)
    wood_grade: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Free-text designation of what the piece physically is, e.g. "Jeu de
    # plaquettes" (scale pair), "Quillon" (guard), "Mitre" (bolster cap) —
    # the space of real-world piece shapes is too varied for a fixed enum.
    piece_type: Mapped[str | None] = mapped_column(String(150), nullable=True)

    # Physical dimensions of one standard stock unit as purchased (a bar, a
    # sheet, or a single discrete piece) — always recorded regardless of
    # dimension_type, since even a COUNT piece (a handle block, a quillon)
    # has a real length/width/thickness worth knowing when selecting stock.
    # For LENGTH/AREA materials, length (and width, for AREA) additionally
    # drive the cutting/yield math; thickness is descriptive only.
    standard_length_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    standard_width_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    standard_thickness_mm: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Saw/cut width lost per cut, in mm — only meaningful for LENGTH stock.
    # This is the number actually used in yield/cutting-optimizer math.
    # Optionally auto-filled from a SawBlade catalog entry (below) but
    # always independently editable, since real-world kerf can drift from
    # a blade's nominal spec (wear, wobble, technique).
    kerf_mm: Mapped[float] = mapped_column(Float, default=2.0)
    saw_blade_id: Mapped[int | None] = mapped_column(ForeignKey("saw_blades.id", ondelete="SET NULL"), nullable=True)
    saw_blade: Mapped["SawBlade | None"] = relationship()

    # Running stock level in the material's own unit: mm for LENGTH,
    # mm^2 for AREA, whole units for COUNT.
    quantity_in_stock: Mapped[float] = mapped_column(Float, default=0.0)
    low_stock_threshold: Mapped[float] = mapped_column(Float, default=0.0)

    unit_cost: Mapped[float] = mapped_column(Float, default=0.0)

    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    @property
    def saw_blade_name(self) -> str | None:
        return self.saw_blade.name if self.saw_blade else None
