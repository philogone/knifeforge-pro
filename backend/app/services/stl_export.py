"""STL export: the cut parts extruded to a thickness, for 3D printing a marking or drilling jig,
a mock-up of the knife, or a template to trace around.

Each part (holes subtracted) becomes a closed solid: top and bottom faces from a constrained
Delaunay triangulation of the outline (every outline edge is kept, so the faces follow the
part exactly), side walls from every ring. Outlines are flattened at the project tolerance
(0.01 mm). Units are millimetres; y is flipped so the solid reads like the drawing seen from above.
"""

from __future__ import annotations

import struct

import shapely
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient

from app.schemas.design import DesignDocument
from app.services.geometry_service import extract_parts

MIN_THICKNESS_MM = 0.1
MAX_THICKNESS_MM = 100.0

Vec = tuple[float, float, float]
Triangle = tuple[Vec, Vec, Vec]


def _polygons(geometry) -> list[Polygon]:
    if geometry.geom_type == "Polygon":
        return [geometry]
    return [g for g in getattr(geometry, "geoms", []) if g.geom_type == "Polygon"]


def part_triangles(polygon: Polygon, thickness: float) -> list[Triangle]:
    """Closed, outward-facing triangle mesh of one polygon extruded from z = 0 to `thickness`."""
    # flip y (drawing is y down), then exterior counter-clockwise, holes clockwise
    flipped = orient(Polygon([(x, -y) for x, y in polygon.exterior.coords], [[(x, -y) for x, y in r.coords] for r in polygon.interiors]), 1.0)
    triangles: list[Triangle] = []
    for tri in shapely.constrained_delaunay_triangles(flipped).geoms:
        a, b, c = orient(tri, 1.0).exterior.coords[:3]
        triangles.append(((a[0], a[1], thickness), (b[0], b[1], thickness), (c[0], c[1], thickness)))  # top, seen from +z
        triangles.append(((a[0], a[1], 0.0), (c[0], c[1], 0.0), (b[0], b[1], 0.0)))  # bottom, reversed
    for ring in [flipped.exterior, *flipped.interiors]:
        pts = list(ring.coords)[:-1]
        for i, (ax, ay) in enumerate(pts):
            bx, by = pts[(i + 1) % len(pts)]
            a0, b0, a1, b1 = (ax, ay, 0.0), (bx, by, 0.0), (ax, ay, thickness), (bx, by, thickness)
            # exterior CCW / holes CW: (b0 − a0) × (b1 − a0) points away from the material
            triangles.append((a0, b0, b1))
            triangles.append((a0, b1, a1))
    return triangles


def _normal(t: Triangle) -> Vec:
    (ax, ay, az), (bx, by, bz), (cx, cy, cz) = t
    ux, uy, uz = bx - ax, by - ay, bz - az
    vx, vy, vz = cx - ax, cy - ay, cz - az
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    length = (nx * nx + ny * ny + nz * nz) ** 0.5 or 1.0
    return (nx / length, ny / length, nz / length)


def design_to_stl(doc: DesignDocument, thickness_mm: float, name: str = "KnifeForge Pro") -> bytes:
    if not MIN_THICKNESS_MM <= thickness_mm <= MAX_THICKNESS_MM:
        raise ValueError(f"Thickness must be between {MIN_THICKNESS_MM} and {MAX_THICKNESS_MM} mm")
    triangles: list[Triangle] = []
    for part in extract_parts(doc):
        for polygon in _polygons(part.geometry):
            triangles.extend(part_triangles(polygon, thickness_mm))
    if not triangles:
        raise ValueError("The design has nothing to export")
    header = name.encode("ascii", "replace")[:80].ljust(80, b" ")
    out = [header, struct.pack("<I", len(triangles))]
    for t in triangles:
        out.append(struct.pack("<12fH", *_normal(t), *t[0], *t[1], *t[2], 0))
    return b"".join(out)
