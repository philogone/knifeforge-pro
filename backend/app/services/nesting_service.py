"""True-shape nesting of design parts onto stock sheets/bars.

The older ``yield_service`` grid estimate and ``cutting_service`` 1-D bin
packing work from *blank dimensions*. Once a maker has actually drawn the
blade profile / scales / guard, those dimensions are no longer a guess: this
module places the real outlines (Bézier-flattened polygons, holes included)
onto the stock, allowing rotation, and reports how many sheets or bars that
really takes.

Algorithm — deterministic greedy bottom-left with compaction:

1. Parts are sorted largest-area first.
2. For each part, every allowed rotation is tried on every open sheet
   (first-fit); candidate anchor points come from the corners of parts
   already placed, and the first collision-free candidate is *compacted*
   (slid toward the origin along both axes until it touches something).
   Sliding is what lets a blade tip settle into the concave gap beside a
   previous blade instead of wasting a rectangle around it.
3. Among rotations, the placement that extends least along the sheet's long
   axis wins.
4. A new sheet is opened only when the part fits nowhere else.

Like the 1-D optimizer this is a heuristic, not a proven optimum — but it is
fast, reproducible (the export endpoints re-run it), and uses real geometry.
Spacing between parts is enforced by inflating each part by half the spacing
and refusing overlaps.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from shapely import affinity
from shapely.geometry.base import BaseGeometry
from sqlalchemy.orm import Session

from app.models.design import Design
from app.models.material import DimensionType, Material
from app.models.order import Order, OrderStatus
from app.schemas.design import DesignDocument
from app.services.geometry_service import DEFAULT_TOLERANCE_MM, extract_parts, polygon_rings
from app.services.order_service import load_order_with_relations

MAX_ITEMS = 500
_EPS = 1e-6
# Orders in these states still need their material cut (same rule as cutting_service).
_CUTTABLE_STATUSES = (OrderStatus.DRAFT, OrderStatus.CONFIRMED)
DEFAULT_ROTATIONS = (0.0, 90.0, 180.0, 270.0)


@dataclass
class NestItem:
    design_id: int
    design_name: str
    part_name: str
    geometry: BaseGeometry
    instance: int
    order_id: int | None = None
    customer_name: str | None = None

    @property
    def area(self) -> float:
        return self.geometry.area


@dataclass
class _Variant:
    angle: float
    shape: BaseGeometry  # normalised: bounds start at (0, 0)
    guard: BaseGeometry  # shape inflated by half the spacing
    width: float
    height: float


@dataclass
class Placement:
    item: NestItem
    x: float
    y: float
    rotation_deg: float
    geometry: BaseGeometry
    guard: BaseGeometry
    guard_bounds: tuple[float, float, float, float] = (0, 0, 0, 0)


@dataclass
class Sheet:
    index: int
    placements: list[Placement] = field(default_factory=list)

    def used_area(self) -> float:
        return sum(p.geometry.area for p in self.placements)


@dataclass
class Unplaced:
    item: NestItem
    reason: str


@dataclass
class NestingResult:
    material_id: int
    material_name: str
    sheet_length_mm: float
    sheet_width_mm: float
    spacing_mm: float
    margin_mm: float
    total_parts: int
    sheets: list[Sheet]
    unplaced: list[Unplaced]
    stock_sheets_available: float

    @property
    def placed_parts(self) -> int:
        return sum(len(s.placements) for s in self.sheets)

    @property
    def sheets_needed(self) -> int:
        return len(self.sheets)

    @property
    def sheet_area(self) -> float:
        return self.sheet_length_mm * self.sheet_width_mm

    @property
    def used_area(self) -> float:
        return sum(s.used_area() for s in self.sheets)

    @property
    def utilization_pct(self) -> float:
        total = self.sheet_area * len(self.sheets)
        return round(self.used_area / total * 100, 2) if total else 0.0

    @property
    def waste_area(self) -> float:
        return round(self.sheet_area * len(self.sheets) - self.used_area, 2)

    @property
    def stock_sufficient(self) -> bool:
        return self.stock_sheets_available + _EPS >= len(self.sheets)


# ---------------------------------------------------------------------------
# Collecting what has to be cut
# ---------------------------------------------------------------------------


def _design_parts(design: Design):
    return extract_parts(DesignDocument.model_validate(design.document))


def _expand(design: Design, quantity: int, start_instance: int, order: Order | None) -> list[NestItem]:
    parts = _design_parts(design)
    items: list[NestItem] = []
    for q in range(quantity):
        for part in parts:
            items.append(
                NestItem(
                    design_id=design.id,
                    design_name=design.name,
                    part_name=part.name,
                    geometry=part.geometry,
                    instance=start_instance + q,
                    order_id=order.id if order else None,
                    customer_name=order.customer_name if order else None,
                )
            )
    return items


def _orders_to_use(db: Session, order_ids: list[int] | None) -> list[Order]:
    # None = every eligible order (default); [] = deliberately none selected.
    if order_ids is not None and len(order_ids) == 0:
        return []
    query = db.query(Order).filter(Order.status.in_(_CUTTABLE_STATUSES))
    if order_ids is not None:
        query = query.filter(Order.id.in_(order_ids))
    return query.order_by(Order.id).all()


def collect_items(
    db: Session,
    material: Material,
    explicit: list[tuple[int, int]],
    order_ids: list[int] | None,
) -> list[NestItem]:
    """``explicit`` is a list of (design_id, quantity). Orders contribute every
    design linked to the order line's knife model *and* assigned to this material."""
    items: list[NestItem] = []
    for design_id, quantity in explicit:
        design = db.query(Design).filter(Design.id == design_id).first()
        if design is None:
            raise ValueError(f"Design {design_id} not found")
        items.extend(_expand(design, quantity, 1, None))

    for order in _orders_to_use(db, order_ids):
        full = load_order_with_relations(db, order.id)
        for line in full.lines:
            designs = (
                db.query(Design)
                .filter(Design.knife_model_id == line.knife_model_id, Design.material_id == material.id)
                .order_by(Design.id)
                .all()
            )
            for design in designs:
                items.extend(_expand(design, line.quantity, 1, order))
    if len(items) > MAX_ITEMS:
        raise ValueError(f"Too many parts to nest ({len(items)} > {MAX_ITEMS}); select fewer orders")
    return items


@dataclass
class NestingCandidates:
    orders: list[dict]
    designs: list[Design]
    # order lines whose knife model uses this material but has no design for it:
    # their parts cannot be nested until a design is linked to model + material
    unlinked: list[dict]


def list_candidates(db: Session, material_id: int) -> NestingCandidates:
    designs = db.query(Design).filter(Design.material_id == material_id).order_by(Design.name).all()
    orders_out: list[dict] = []
    unlinked: list[dict] = []
    for order in _orders_to_use(db, None):
        full = load_order_with_relations(db, order.id)
        count = 0
        for line in full.lines:
            linked = [d for d in designs if d.knife_model_id == line.knife_model_id]
            for design in linked:
                count += design.part_count * line.quantity
            uses_material = any(m.material_id == material_id for m in line.knife_model.materials)
            if uses_material and not linked:
                unlinked.append(
                    {
                        "order_id": order.id,
                        "customer_name": order.customer_name,
                        "knife_model_id": line.knife_model_id,
                        "knife_model_name": line.knife_model.name,
                        "quantity": line.quantity,
                    }
                )
        if count:
            orders_out.append(
                {
                    "order_id": order.id,
                    "customer_name": order.customer_name,
                    "status": order.status.value,
                    "part_count": count,
                }
            )
    return NestingCandidates(orders=orders_out, designs=designs, unlinked=unlinked)


# ---------------------------------------------------------------------------
# Packing
# ---------------------------------------------------------------------------


def _normalise(geometry: BaseGeometry) -> BaseGeometry:
    minx, miny, _, _ = geometry.bounds
    return affinity.translate(geometry, -minx, -miny)


_BUFFER_QUAD_SEGS = 16
_SIMPLIFY_MM = 0.002


def _guard_radius(distance: float) -> float:
    return distance / math.cos(math.pi / (4 * _BUFFER_QUAD_SEGS)) + _SIMPLIFY_MM


def _outer_buffer(shape: BaseGeometry, distance: float) -> BaseGeometry:
    """Buffer that is guaranteed to contain the true offset curve: Shapely's
    round joins are inscribed in the ideal circle, so the radius is enlarged by
    1/cos(pi / (4 * quad_segs)) and by the simplification tolerance. The result
    can only be *larger* than the exact offset (by a few hundredths of a mm),
    never smaller, so the requested spacing is never under-delivered."""
    radius = _guard_radius(distance)
    return shape.buffer(radius, quad_segs=_BUFFER_QUAD_SEGS).simplify(_SIMPLIFY_MM, preserve_topology=True)


def _make_variants(item: NestItem, rotations: tuple[float, ...], half_spacing: float) -> list[_Variant]:
    variants: list[_Variant] = []
    for angle in rotations:
        rotated = affinity.rotate(item.geometry, angle, origin="centroid") if angle else item.geometry
        shape = _normalise(rotated)
        w = shape.bounds[2]
        h = shape.bounds[3]
        # Symmetric parts produce identical variants — skip duplicates.
        if any(
            abs(v.width - w) < 1e-3 and abs(v.height - h) < 1e-3 and v.shape.symmetric_difference(shape).area < 1e-3
            for v in variants
        ):
            continue
        guard = _outer_buffer(shape, half_spacing) if half_spacing > 0 else shape
        variants.append(_Variant(angle=angle % 360, shape=shape, guard=guard, width=w, height=h))
    return variants


def _boxes_overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _collides(sheet: Sheet, variant: _Variant, x: float, y: float) -> bool:
    gx0, gy0, gx1, gy1 = variant.guard.bounds
    box = (gx0 + x, gy0 + y, gx1 + x, gy1 + y)
    guard_world: BaseGeometry | None = None
    for placed in sheet.placements:
        if not _boxes_overlap(box, placed.guard_bounds):
            continue
        if guard_world is None:
            guard_world = affinity.translate(variant.guard, x, y)
        if guard_world.intersects(placed.guard):
            return True
    return False


def _slide(sheet: Sheet, variant: _Variant, x: float, y: float, axis: int, limit: float) -> tuple[float, float]:
    """Move toward smaller coordinate along ``axis`` (0 = x, 1 = y) as far as
    possible, never below ``limit``, using a shrinking step."""
    step = 32.0
    while step >= 0.01:
        while True:
            pos = (x, y)[axis]
            target = max(limit, pos - step)
            if target >= pos - 1e-9:
                break
            nx, ny = (target, y) if axis == 0 else (x, target)
            if _collides(sheet, variant, nx, ny):
                break
            x, y = nx, ny
        step /= 2
    return x, y


def _candidate_axes(sheet: Sheet, margin: float, spacing: float) -> tuple[list[float], list[float]]:
    xs = {margin}
    ys = {margin}
    for p in sheet.placements:
        minx, miny, maxx, maxy = p.geometry.bounds
        xs.update((maxx + spacing, minx))
        ys.update((maxy + spacing, miny))
    return sorted(xs), sorted(ys)


def _best_on_sheet(
    sheet: Sheet,
    variants: list[_Variant],
    sheet_w: float,
    sheet_h: float,
    margin: float,
    spacing: float,
    primary_axis: int,
):
    xs, ys = _candidate_axes(sheet, margin, spacing)
    best = None
    best_score: tuple[float, float] | None = None
    max_x = sheet_w - margin
    max_y = sheet_h - margin
    for variant in variants:
        if variant.width > max_x - margin + _EPS or variant.height > max_y - margin + _EPS:
            continue
        found: tuple[float, float] | None = None
        outer, inner = (xs, ys) if primary_axis == 0 else (ys, xs)
        for a in outer:
            for b in inner:
                x, y = (a, b) if primary_axis == 0 else (b, a)
                if x + variant.width > max_x + _EPS or y + variant.height > max_y + _EPS:
                    continue
                if not _collides(sheet, variant, x, y):
                    found = (x, y)
                    break
            if found:
                break
        if found is None:
            continue
        x, y = found
        for _ in range(8):
            nx, ny = _slide(sheet, variant, x, y, 1, margin)
            nx, ny = _slide(sheet, variant, nx, ny, 0, margin)
            if abs(nx - x) < 1e-6 and abs(ny - y) < 1e-6:
                break
            x, y = nx, ny
        extent = (x + variant.width, y) if primary_axis == 0 else (y + variant.height, x)
        if best_score is None or extent < best_score:
            best_score = extent
            best = (variant, x, y)
    return best


def _pack_once(
    items: list[NestItem],
    sheet_length: float,
    sheet_width: float,
    spacing: float,
    margin: float,
    rotations: tuple[float, ...] = DEFAULT_ROTATIONS,
    max_sheets: int = 200,
) -> tuple[list[Sheet], list[Unplaced]]:
    spacing = max(spacing, 0.02)
    # + DEFAULT_TOLERANCE_MM: flattened outlines are inscribed in the true
    # curves by up to that much, so each guard is grown to compensate.
    half = spacing / 2 + DEFAULT_TOLERANCE_MM
    primary_axis = 0 if sheet_length >= sheet_width else 1

    # distance between two flat edges whose guards just touch
    gap = 2 * _guard_radius(half) + 1e-6

    sheets: list[Sheet] = []
    unplaced: list[Unplaced] = []
    variant_cache: dict[int, list[_Variant]] = {}

    ordered = sorted(items, key=lambda it: (-it.area, it.design_id, it.part_name, it.instance))
    for item in ordered:
        key = id(item.geometry)
        if key not in variant_cache:
            variant_cache[key] = _make_variants(item, rotations, half)
        variants = variant_cache[key]

        fits_empty = any(
            v.width <= sheet_length - 2 * margin + _EPS and v.height <= sheet_width - 2 * margin + _EPS
            for v in variants
        )
        if not fits_empty:
            unplaced.append(Unplaced(item, "too_large"))
            continue

        placed = False
        for sheet in sheets:
            best = _best_on_sheet(sheet, variants, sheet_length, sheet_width, margin, gap, primary_axis)
            if best is not None:
                _commit(sheet, item, *best)
                placed = True
                break
        if placed:
            continue
        if len(sheets) >= max_sheets:
            unplaced.append(Unplaced(item, "sheet_limit"))
            continue
        sheet = Sheet(index=len(sheets))
        best = _best_on_sheet(sheet, variants, sheet_length, sheet_width, margin, gap, primary_axis)
        if best is None:  # cannot happen if fits_empty, but never loop/crash
            unplaced.append(Unplaced(item, "too_large"))
            continue
        sheets.append(sheet)
        _commit(sheet, item, *best)

    return sheets, unplaced


def pack(
    items: list[NestItem],
    sheet_length: float,
    sheet_width: float,
    spacing: float,
    margin: float,
    rotations: tuple[float, ...] = DEFAULT_ROTATIONS,
    max_sheets: int = 200,
) -> tuple[list[Sheet], list[Unplaced]]:
    """Greedy bottom-left packing, run for the requested rotation set and for
    its axis-aligned subsets (0/180 only, 90/270 only); the best layout wins
    (fewest unplaced, then fewest sheets, then shortest used length). Mixing
    orientations greedily can be worse than keeping all parts aligned, so the
    subsets are cheap insurance. Deterministic."""
    candidates = [tuple(rotations)]
    flat = tuple(r for r in rotations if round(r) % 180 == 0)
    upright = tuple(r for r in rotations if round(r) % 180 == 90)
    for subset in (flat, upright):
        if subset and subset != tuple(rotations):
            candidates.append(subset)
    primary = 0 if sheet_length >= sheet_width else 1
    best = None
    best_key = None
    for rots in candidates:
        sheets, unplaced = _pack_once(items, sheet_length, sheet_width, spacing, margin, rots, max_sheets)
        last = sheets[-1].placements if sheets else []
        extent = max((p.geometry.bounds[2 + primary] for p in last), default=0.0)
        key = (len(unplaced), len(sheets), round(extent, 3))
        if best_key is None or key < best_key:
            best, best_key = (sheets, unplaced), key
    assert best is not None
    return best


def _commit(sheet: Sheet, item: NestItem, variant: _Variant, x: float, y: float) -> None:
    geometry = affinity.translate(variant.shape, x, y)
    guard = affinity.translate(variant.guard, x, y)
    sheet.placements.append(
        Placement(
            item=item,
            x=round(x, 3),
            y=round(y, 3),
            rotation_deg=round(variant.angle, 3),
            geometry=geometry,
            guard=guard,
            guard_bounds=guard.bounds,
        )
    )


def run_nesting(
    db: Session,
    material_id: int,
    explicit: list[tuple[int, int]],
    order_ids: list[int] | None,
    spacing_mm: float,
    margin_mm: float,
    rotations: list[float] | None,
) -> NestingResult:
    material = db.query(Material).filter(Material.id == material_id).first()
    if material is None:
        raise ValueError("Material not found")
    if material.dimension_type == DimensionType.COUNT:
        raise ValueError("Nesting only applies to LENGTH (bar) and AREA (sheet) materials")
    if not material.standard_length_mm or not material.standard_width_mm:
        raise ValueError("Material needs standard_length_mm and standard_width_mm to nest parts on it")

    length = material.standard_length_mm
    width = material.standard_width_mm
    items = collect_items(db, material, explicit, order_ids)

    angles = tuple(sorted({a % 360 for a in rotations})) if rotations else DEFAULT_ROTATIONS
    sheets, unplaced = pack(items, length, width, spacing_mm, margin_mm, angles)

    if material.dimension_type == DimensionType.LENGTH:
        available = material.quantity_in_stock / length if length else 0.0
    else:
        available = material.quantity_in_stock / (length * width)

    return NestingResult(
        material_id=material.id,
        material_name=material.name,
        sheet_length_mm=length,
        sheet_width_mm=width,
        spacing_mm=max(spacing_mm, 0.02),
        margin_mm=margin_mm,
        total_parts=len(items),
        sheets=sheets,
        unplaced=unplaced,
        stock_sheets_available=round(available, 3),
    )


def placement_rings(placement: Placement) -> list[list[list[float]]]:
    return [[[round(x, 3), round(y, 3)] for x, y in ring] for ring in polygon_rings(placement.geometry)]

