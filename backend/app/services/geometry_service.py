"""Geometry helpers for design documents: Bézier flattening, polygon building
(with even-odd holes), metrics, and offsetting. Everything is in millimetres,
y-down (the editor's world space).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from shapely.geometry import LineString, MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from app.schemas.design import DesignDocument, Node, PathObject

# Max distance between a flattened polyline and the true curve, in mm. 0.05 mm
# is far below what a saw, laser or belt grinder can hold.
DEFAULT_TOLERANCE_MM = 0.05

Point = tuple[float, float]


def _wang_segments(p0: Point, c1: Point, c2: Point, p1: Point, tolerance: float) -> int:
    """Number of line segments needed to approximate a cubic Bézier within
    ``tolerance`` (Wang's formula for uniform subdivision)."""
    ddx1 = p0[0] - 2 * c1[0] + c2[0]
    ddy1 = p0[1] - 2 * c1[1] + c2[1]
    ddx2 = c1[0] - 2 * c2[0] + p1[0]
    ddy2 = c1[1] - 2 * c2[1] + p1[1]
    m = max(math.hypot(ddx1, ddy1), math.hypot(ddx2, ddy2))
    if m == 0:
        return 1
    return max(1, min(256, math.ceil(math.sqrt(0.75 * m / tolerance))))


def _segment_points(a: Node, b: Node, tolerance: float) -> list[Point]:
    """Points along the segment a -> b, excluding the start point, including the end."""
    p0 = (a.x, a.y)
    p1 = (b.x, b.y)
    c1 = (a.x + a.ox, a.y + a.oy)
    c2 = (b.x + b.ix, b.y + b.iy)
    if a.ox == 0 and a.oy == 0 and b.ix == 0 and b.iy == 0:
        return [p1]
    n = _wang_segments(p0, c1, c2, p1, tolerance)
    points: list[Point] = []
    for i in range(1, n + 1):
        t = i / n
        mt = 1 - t
        x = mt**3 * p0[0] + 3 * mt**2 * t * c1[0] + 3 * mt * t**2 * c2[0] + t**3 * p1[0]
        y = mt**3 * p0[1] + 3 * mt**2 * t * c1[1] + 3 * mt * t**2 * c2[1] + t**3 * p1[1]
        points.append((x, y))
    return points


def flatten_contour(nodes: list[Node], closed: bool, tolerance: float = DEFAULT_TOLERANCE_MM) -> list[Point]:
    """Flatten a Bézier contour to a polyline. For a closed contour the first
    point is NOT repeated at the end."""
    if not nodes:
        return []
    points: list[Point] = [(nodes[0].x, nodes[0].y)]
    for i in range(len(nodes) - 1):
        points.extend(_segment_points(nodes[i], nodes[i + 1], tolerance))
    if closed:
        closing = _segment_points(nodes[-1], nodes[0], tolerance)
        # drop the final point: it coincides with the start point
        points.extend(closing[:-1])
    return points


def _ring_polygon(points: list[Point]) -> Polygon | None:
    if len(points) < 3:
        return None
    poly = Polygon(points)
    if not poly.is_valid:
        poly = poly.buffer(0)
    if poly.is_empty or poly.area < 1e-6:
        return None
    return poly


def object_polygon(obj: PathObject, tolerance: float = DEFAULT_TOLERANCE_MM) -> BaseGeometry | None:
    """Area geometry of a closed path object. Several contours are combined
    with the even-odd rule (outer outline minus inner cut-outs)."""
    if not obj.closed:
        return None
    result: BaseGeometry | None = None
    for contour in obj.contours:
        poly = _ring_polygon(flatten_contour(contour, True, tolerance))
        if poly is None:
            continue
        result = poly if result is None else result.symmetric_difference(poly)
    if result is None or result.is_empty:
        return None
    return result


@dataclass
class Part:
    """One physical piece to cut: a closed outline on a ``cut`` layer, minus
    any ``hole``-layer shapes that overlap it."""

    object_id: str
    name: str
    geometry: BaseGeometry

    @property
    def area(self) -> float:
        return self.geometry.area


def _layer_map(doc: DesignDocument):
    return {layer.id: layer for layer in doc.layers}


def extract_parts(doc: DesignDocument, tolerance: float = DEFAULT_TOLERANCE_MM) -> list[Part]:
    layers = _layer_map(doc)
    holes: list[BaseGeometry] = []
    cuts: list[tuple[PathObject, BaseGeometry]] = []
    for obj in doc.objects:
        if not isinstance(obj, PathObject):
            continue
        layer = layers[obj.layer]
        if not layer.visible:
            continue
        if layer.role not in ("cut", "hole"):
            continue
        geometry = object_polygon(obj, tolerance)
        if geometry is None:
            continue
        if layer.role == "hole":
            holes.append(geometry)
        else:
            cuts.append((obj, geometry))

    hole_union = unary_union(holes) if holes else None
    parts: list[Part] = []
    for index, (obj, geometry) in enumerate(cuts):
        if hole_union is not None and geometry.intersects(hole_union):
            geometry = geometry.difference(hole_union)
        if geometry.is_empty or geometry.area < 1e-6:
            continue
        parts.append(Part(object_id=obj.id, name=obj.name or f"Part {index + 1}", geometry=geometry))
    return parts


def extract_engraving_lines(doc: DesignDocument, tolerance: float = DEFAULT_TOLERANCE_MM) -> list[list[Point]]:
    """Polylines of every visible ``engrave``-layer path (open or closed)."""
    layers = _layer_map(doc)
    lines: list[list[Point]] = []
    for obj in doc.objects:
        if not isinstance(obj, PathObject):
            continue
        layer = layers[obj.layer]
        if not layer.visible or layer.role != "engrave":
            continue
        for contour in obj.contours:
            points = flatten_contour(contour, obj.closed, tolerance)
            if obj.closed and points:
                points = points + [points[0]]
            if len(points) >= 2:
                lines.append(points)
    return lines


def polygon_rings(geometry: BaseGeometry) -> list[list[Point]]:
    """Exterior + interior rings of every polygon in the geometry (rings are
    returned closed-less: the first point is not repeated)."""
    polygons: list[Polygon]
    if isinstance(geometry, Polygon):
        polygons = [geometry]
    elif isinstance(geometry, MultiPolygon):
        polygons = list(geometry.geoms)
    else:
        polygons = [g for g in getattr(geometry, "geoms", []) if isinstance(g, Polygon)]
    rings: list[list[Point]] = []
    for poly in polygons:
        rings.append([(x, y) for x, y in poly.exterior.coords[:-1]])
        for interior in poly.interiors:
            rings.append([(x, y) for x, y in interior.coords[:-1]])
    return rings


@dataclass
class DesignMetrics:
    width_mm: float
    height_mm: float
    area_mm2: float
    perimeter_mm: float
    part_count: int


def compute_metrics(doc: DesignDocument, tolerance: float = DEFAULT_TOLERANCE_MM) -> DesignMetrics:
    parts = extract_parts(doc, tolerance)
    if not parts:
        return DesignMetrics(0.0, 0.0, 0.0, 0.0, 0)
    union = unary_union([p.geometry for p in parts])
    minx, miny, maxx, maxy = union.bounds
    return DesignMetrics(
        width_mm=round(maxx - minx, 3),
        height_mm=round(maxy - miny, 3),
        area_mm2=round(sum(p.area for p in parts), 2),
        perimeter_mm=round(sum(p.geometry.length for p in parts), 2),
        part_count=len(parts),
    )


def document_bounds(doc: DesignDocument, tolerance: float = DEFAULT_TOLERANCE_MM) -> tuple[float, float, float, float] | None:
    """Bounds of everything drawable that is visible and not construction
    geometry (cut, hole and engrave layers)."""
    layers = _layer_map(doc)
    geoms: list[BaseGeometry] = []
    for obj in doc.objects:
        if not isinstance(obj, PathObject):
            continue
        layer = layers[obj.layer]
        if not layer.visible or layer.role not in ("cut", "hole", "engrave"):
            continue
        for contour in obj.contours:
            points = flatten_contour(contour, obj.closed, tolerance)
            if len(points) >= 2:
                geoms.append(LineString(points))
    if not geoms:
        return None
    union = unary_union(geoms)
    minx, miny, maxx, maxy = union.bounds
    return (minx, miny, maxx, maxy)


# ---------------------------------------------------------------------------
# Offset (grow / shrink) — used for kerf allowance, scale-inset, blade bevels…
# ---------------------------------------------------------------------------

_JOIN_STYLES = {"round": 1, "mitre": 2, "bevel": 3}


def offset_contours(
    contours: list[list[Node]], distance_mm: float, join: str = "round", tolerance: float = DEFAULT_TOLERANCE_MM
) -> list[list[Node]]:
    """Grow (positive) or shrink (negative) a closed shape. Returns polygon
    contours (corner nodes only, no handles) — exterior first, then holes."""
    shape: BaseGeometry | None = None
    for contour in contours:
        poly = _ring_polygon(flatten_contour(contour, True, tolerance))
        if poly is None:
            continue
        shape = poly if shape is None else shape.symmetric_difference(poly)
    if shape is None or shape.is_empty:
        raise ValueError("Shape is empty or degenerate")

    result = shape.buffer(distance_mm, join_style=_JOIN_STYLES.get(join, 1), quad_segs=16, mitre_limit=4.0)
    result = result.simplify(tolerance / 2, preserve_topology=True)
    if result.is_empty:
        raise ValueError("Offset collapses the shape")

    out: list[list[Node]] = []
    for ring in polygon_rings(result):
        if len(ring) >= 3:
            out.append([Node(x=round(x, 4), y=round(y, 4)) for x, y in ring])
    if not out:
        raise ValueError("Offset collapses the shape")
    return out
