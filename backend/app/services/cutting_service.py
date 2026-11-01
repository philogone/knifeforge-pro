"""Cross-order cutting-stock optimization for LENGTH materials.

A maker rarely cuts one order at a time — if three different orders each
need a knife using the same steel, cutting them from separate bars (one
bar per order) wastes material that a shared cutting plan wouldn't. This
aggregates blank-length demand for one material across every DRAFT and
CONFIRMED order by default (even mixing different knife models with
different blank lengths) and packs them onto the fewest bars using
First-Fit Decreasing bin packing: sort all pieces longest-first, place
each into the first bar with enough remaining room, open a new bar only
when none fits. Pass explicit order_ids to run it against a specific
hand-picked batch instead — e.g. "just the orders I'm cutting today" —
via list_candidate_orders() for the picker and optimize_cutting(...,
order_ids=[...]) to run it on that exact subset.

FFD is a well-known, simple heuristic — typically within ~22% of optimal
for bin packing, often exact for small/real-world piece counts. It is not
a guaranteed-optimal solver (that's a much harder problem — column
generation / integer programming), which is an appropriate boundary for a
starter kit. True 2D nesting for AREA (sheet) materials with mixed blank
sizes is a substantially harder rectangle-packing problem and is out of
scope here entirely.
"""

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.material import DimensionType, Material
from app.models.order import Order, OrderStatus
from app.services.order_service import load_order_with_relations


@dataclass
class CutPiece:
    length_mm: float
    order_id: int
    customer_name: str
    knife_model_name: str


@dataclass
class CutBar:
    pieces: list[CutPiece] = field(default_factory=list)
    waste_mm: float = 0.0


@dataclass
class CuttingPlan:
    material_id: int
    material_name: str
    kerf_mm: float
    stock_length_mm: float
    total_pieces: int
    bars_needed: int
    total_waste_mm: float
    waste_percentage: float
    bars: list[CutBar]


@dataclass
class CandidateOrder:
    order_id: int
    customer_name: str
    status: str
    piece_count: int
    total_length_mm: float


# Orders in these two states still need their material physically cut — a
# DRAFT hasn't been confirmed yet but a maker may want to plan ahead for
# it; a CONFIRMED order already had its stock deducted and is the most
# likely to go into production next, so it must not be excluded. COMPLETED
# orders are already built (nothing left to cut) and CANCELLED orders
# aren't happening — both are excluded.
_CUTTABLE_STATUSES = (OrderStatus.DRAFT, OrderStatus.CONFIRMED)


def _pieces_for_order(order, material_id: int) -> list[CutPiece]:
    pieces: list[CutPiece] = []
    for line in order.lines:
        for kmm in line.knife_model.materials:
            if kmm.material_id != material_id or kmm.blank_length_mm is None:
                continue
            for _ in range(line.quantity):
                pieces.append(
                    CutPiece(
                        length_mm=kmm.blank_length_mm,
                        order_id=order.id,
                        customer_name=order.customer_name,
                        knife_model_name=line.knife_model.name,
                    )
                )
    return pieces


def list_candidate_orders(db: Session, material_id: int) -> list[CandidateOrder]:
    """Every draft or confirmed order that would contribute at least one
    piece of this material — for a picker UI to choose which orders to
    include in a cutting run before optimizing."""
    orders = db.query(Order).filter(Order.status.in_(_CUTTABLE_STATUSES)).all()
    candidates: list[CandidateOrder] = []
    for order in orders:
        full_order = load_order_with_relations(db, order.id)
        pieces = _pieces_for_order(full_order, material_id)
        if pieces:
            candidates.append(
                CandidateOrder(
                    order_id=order.id,
                    customer_name=order.customer_name,
                    status=order.status.value,
                    piece_count=len(pieces),
                    total_length_mm=round(sum(p.length_mm for p in pieces), 2),
                )
            )
    return candidates


def collect_pieces(db: Session, material_id: int, order_ids: list[int] | None) -> list[CutPiece]:
    # order_ids=None means "every eligible order" (the default); an empty
    # list is a deliberate "none selected" from the picker UI and must
    # return zero pieces, not silently fall back to the full set.
    if order_ids is not None and len(order_ids) == 0:
        return []
    query = db.query(Order).filter(Order.status.in_(_CUTTABLE_STATUSES))
    if order_ids is not None:
        query = query.filter(Order.id.in_(order_ids))
    orders = query.all()

    pieces: list[CutPiece] = []
    for order in orders:
        full_order = load_order_with_relations(db, order.id)
        pieces.extend(_pieces_for_order(full_order, material_id))
    return pieces


def optimize_cutting(db: Session, material_id: int, order_ids: list[int] | None = None) -> CuttingPlan:
    material = db.query(Material).filter(Material.id == material_id).first()
    if material is None:
        raise ValueError("Material not found")
    if material.dimension_type != DimensionType.LENGTH:
        raise ValueError("Cutting optimization only applies to LENGTH materials")
    if not material.standard_length_mm:
        raise ValueError("Material has no standard_length_mm set")

    stock_length = material.standard_length_mm
    kerf = material.kerf_mm

    pieces = collect_pieces(db, material_id, order_ids)
    if not pieces:
        return CuttingPlan(material.id, material.name, kerf, stock_length, 0, 0, 0.0, 0.0, [])

    for piece in pieces:
        if piece.length_mm + kerf > stock_length:
            raise ValueError(
                f'"{piece.knife_model_name}" needs a {piece.length_mm}mm blank (+{kerf}mm kerf), '
                f"longer than this material's {stock_length}mm standard stock length"
            )

    sorted_pieces = sorted(pieces, key=lambda p: p.length_mm, reverse=True)
    bars: list[CutBar] = []

    for piece in sorted_pieces:
        needed = piece.length_mm + kerf
        target = next((bar for bar in bars if bar.waste_mm >= needed), None)
        if target is None:
            target = CutBar(waste_mm=stock_length)
            bars.append(target)
        target.pieces.append(piece)
        target.waste_mm = round(target.waste_mm - needed, 2)

    total_waste = round(sum(bar.waste_mm for bar in bars), 2)
    total_stock_used = len(bars) * stock_length
    waste_percentage = round((total_waste / total_stock_used) * 100, 2) if total_stock_used else 0.0

    return CuttingPlan(
        material_id=material.id,
        material_name=material.name,
        kerf_mm=kerf,
        stock_length_mm=stock_length,
        total_pieces=len(pieces),
        bars_needed=len(bars),
        total_waste_mm=total_waste,
        waste_percentage=waste_percentage,
        bars=bars,
    )
