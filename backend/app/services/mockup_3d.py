"""3D mock-up of the assembled knife, for a 3D printer or a CNC router.

The drawing gives each part's outline; the maker gives each a role and a thickness. Plates are
stacked along z, the drawing plane being the knife seen from the side:
- centre parts (blade, guard, bolster, spacer) are centred on z = 0;
- liners then scales are added outwards on each side, from the blade's faces. A single outline
  given the role "scales" (or "liners") makes the pair, left and right;
- every hole that goes through two parts or more gets a pin through the whole stack it crosses.

Outputs:
- 3MF (one object per part, millimetres), laid flat for printing or assembled for viewing;
- a zip of STL files, one per part, laid flat;
- for a CNC router: a zip of DXF files, one per plate, its thickness in the name, with a report of
  what the cutter cannot reach (inside corners tighter than its radius, holes narrower than it).

Outlines are flattened at the project tolerance (0.01 mm) and triangulated exactly
(stl_export.part_triangles): every solid is closed and its volume is the drawing's area times
its thickness. Limits: plates with square edges (no grind, no rounded or contoured scales).
"""

from __future__ import annotations

import io
import struct
import zipfile
from dataclasses import dataclass, field
from typing import Literal
from xml.sax.saxutils import escape

from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from app.schemas.design import DesignDocument, PathObject
from app.services.geometry_service import extract_parts, object_polygon
from app.services.stl_export import Triangle, _normal, _polygons, part_triangles

Role = Literal["blade", "guard", "bolster", "spacer", "liners", "scales", "liner_left", "liner_right", "scale_left", "scale_right"]
CENTRE = {"blade", "guard", "bolster", "spacer"}
# outward order on each side: liners against the tang, scales over them
SIDE_ORDER = {"liner": 0, "scale": 1}
ROLE_LABEL = {
    "blade": "Lame", "guard": "Garde", "bolster": "Mitre", "spacer": "Entretoise",
    "liner_left": "Platine gauche", "liner_right": "Platine droite", "scale_left": "Plaquette gauche", "scale_right": "Plaquette droite",
}
# print colours (3MF base materials): steel grey, brass, wood, G10 black, pins
ROLE_COLOUR = {
    "blade": "#9AA0A6", "guard": "#B08D57", "bolster": "#B08D57", "spacer": "#3A3A3A",
    "liner_left": "#3A3A3A", "liner_right": "#3A3A3A", "scale_left": "#7A4E2D", "scale_right": "#7A4E2D", "pin": "#C9A227",
}
MAX_THICKNESS_MM = 60.0
LAYOUT_GAP_MM = 6.0
# below the tool's precision: polygonisation slivers, not material really left
MIN_ISSUE_MM = 0.01


class MockupError(ValueError):
    pass


@dataclass
class PartSpec:
    object_id: str
    role: Role
    thickness_mm: float


@dataclass
class Solid:
    name: str
    role: str
    polygons: list[Polygon]  # drawing coordinates (mm, y down)
    z0: float
    z1: float
    # a guard slotted for the tang: (polygons, z0, z1) layers that replace the plain extrusion
    slabs: list[tuple[list[Polygon], float, float]] | None = None

    @property
    def thickness(self) -> float:
        return self.z1 - self.z0


@dataclass
class Assembly:
    solids: list[Solid] = field(default_factory=list)
    pins: list[Solid] = field(default_factory=list)

    @property
    def everything(self) -> list[Solid]:
        return self.solids + self.pins


def _side_parts(spec: PartSpec) -> list[tuple[str, str]]:
    """(side, role) pairs a spec stands for: "scales" is a left and a right scale."""
    if spec.role in ("scales", "liners"):
        kind = spec.role[:-1]
        return [("left", f"{kind}_left"), ("right", f"{kind}_right")]
    if spec.role in CENTRE:
        return [("centre", spec.role)]
    return [(spec.role.split("_")[1], spec.role)]


def assemble(doc: DesignDocument, specs: list[PartSpec], pin_clearance_mm: float = 0.0) -> Assembly:
    if not specs:
        raise MockupError("Give a role to at least one part")
    parts = {p.object_id: p for p in extract_parts(doc)}
    names = {o.id: (o.name or "") for o in doc.objects if isinstance(o, PathObject)}
    for s in specs:
        if s.object_id not in parts:
            raise MockupError(f"Part not found: {s.object_id}")
        if not 0 < s.thickness_mm <= MAX_THICKNESS_MM:
            raise MockupError(f"Thickness must be between 0 and {MAX_THICKNESS_MM} mm")

    asm = Assembly()
    centre = [s for s in specs if s.role in CENTRE]
    # the side stacks start on the blade's faces (or the thickest centre part)
    base = max((s.thickness_mm / 2 for s in centre if s.role == "blade"), default=max((s.thickness_mm / 2 for s in centre), default=0.0))
    blade = next((s for s in centre if s.role == "blade"), None)
    blade_shape = parts[blade.object_id].geometry if blade else None
    for s in centre:
        geom = parts[s.object_id].geometry
        solid = Solid(names[s.object_id] or ROLE_LABEL[s.role], s.role, _polygons(geom), -s.thickness_mm / 2, s.thickness_mm / 2)
        # a guard, bolster or spacer thicker than the blade and over it: slot it for the tang
        # (the blade's own outline, widened by the clearance), so the pieces fit together
        if blade and s is not blade and s.thickness_mm > blade.thickness_mm and geom.intersects(blade_shape):
            half = min(s.thickness_mm / 2, blade.thickness_mm / 2 + pin_clearance_mm / 2)
            slot = blade_shape.buffer(pin_clearance_mm / 2, join_style="mitre") if pin_clearance_mm else blade_shape
            middle = _polygons(geom.difference(slot))
            solid.slabs = [(solid.polygons, -s.thickness_mm / 2, -half), (middle, -half, half), (solid.polygons, half, s.thickness_mm / 2)]
        asm.solids.append(solid)
    for side, sign in (("left", 1), ("right", -1)):
        stack = sorted(
            ((s, role) for s in specs for sd, role in _side_parts(s) if sd == side),
            key=lambda x: SIDE_ORDER[x[1].split("_")[0]],
        )
        z = base
        for s, role in stack:
            z0, z1 = (z, z + s.thickness_mm) if sign > 0 else (-z - s.thickness_mm, -z)
            label = names[s.object_id] or ROLE_LABEL[role]
            if s.role in ("scales", "liners"):
                label = f"{label} ({'gauche' if side == 'left' else 'droite'})"
            asm.solids.append(Solid(label, role, _polygons(parts[s.object_id].geometry), z0, z1))
            z += s.thickness_mm

    # pins: every hole crossing two parts or more, through the stack it crosses
    for obj in doc.objects:
        if not isinstance(obj, PathObject):
            continue
        layer = next((l for l in doc.layers if l.id == obj.layer), None)
        if layer is None or layer.role != "hole" or not layer.visible:
            continue
        hole = object_polygon(obj)
        if hole is None:
            continue
        # the hole is cut out of the parts: test against their filled outline
        crossed = [sd for sd in asm.solids if any(Polygon(p.exterior).contains(hole.representative_point()) for p in sd.polygons)]
        if len(crossed) < 2:
            continue
        pin = hole.buffer(-pin_clearance_mm / 2, quad_segs=32) if pin_clearance_mm else hole
        if pin.is_empty:
            continue
        asm.pins.append(Solid(f"Goupille {obj.name or ''}".strip(), "pin", _polygons(pin), min(s.z0 for s in crossed), max(s.z1 for s in crossed)))
    return asm


# ------------------------------------------------------------------------------------------
# Meshes
# ------------------------------------------------------------------------------------------


def solid_triangles(solid: Solid, flat: bool = False, dx: float = 0.0, dy: float = 0.0) -> list[Triangle]:
    """The solid's closed mesh, in place (z0..z1) or laid flat on z = 0, shifted by (dx, dy)."""
    shift = -solid.z0 if flat else 0.0
    tris: list[Triangle] = []
    for polys, z0, z1 in solid.slabs or [(solid.polygons, solid.z0, solid.z1)]:
        for poly in polys:
            for a, b, c in part_triangles(poly, z1 - z0):
                tris.append(tuple((x + dx, y + dy, z + z0 + shift) for x, y, z in (a, b, c)))  # type: ignore[misc]
    return tris


def _flat_layout(asm: Assembly) -> list[tuple[Solid, float, float]]:
    """Each piece laid flat, in a column, the drawing's left edge at x = 0 (y up after the flip)."""
    placed = []
    y_cursor = 0.0
    for s in asm.everything:
        u = unary_union(s.polygons)
        minx, miny, maxx, maxy = u.bounds
        # after the y flip the piece spans -maxy..-miny: put its bottom at y_cursor
        placed.append((s, -minx, y_cursor + maxy))
        y_cursor += (maxy - miny) + LAYOUT_GAP_MM
    return placed


def _vertices_and_faces(tris: list[Triangle]) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    index: dict[tuple[float, float, float], int] = {}
    verts: list[tuple[float, float, float]] = []
    faces = []
    for t in tris:
        ids = []
        for v in t:
            key = (round(v[0], 6), round(v[1], 6), round(v[2], 6))
            if key not in index:
                index[key] = len(verts)
                verts.append(key)
            ids.append(index[key])
        if len(set(ids)) == 3:
            faces.append(tuple(ids))
    return verts, faces  # type: ignore[return-value]


def to_3mf(asm: Assembly, layout: Literal["flat", "assembled"] = "flat", title: str = "KnifeForge Pro") -> bytes:
    pieces = _flat_layout(asm) if layout == "flat" else [(s, 0.0, 0.0) for s in asm.everything]
    roles = sorted({s.role for s, _, _ in pieces})
    material_id = {r: i for i, r in enumerate(roles)}
    objects = []
    for n, (s, dx, dy) in enumerate(pieces, start=1):
        verts, faces = _vertices_and_faces(solid_triangles(s, flat=layout == "flat", dx=dx, dy=dy))
        v = "".join(f'<vertex x="{x:.6f}" y="{y:.6f}" z="{z:.6f}"/>' for x, y, z in verts)
        f = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in faces)
        objects.append(
            f'<object id="{n + 1}" type="model" name="{escape(s.name)}" pid="1" pindex="{material_id[s.role]}">'
            f"<mesh><vertices>{v}</vertices><triangles>{f}</triangles></mesh></object>"
        )
    materials = "".join(f'<base name="{escape(ROLE_LABEL.get(r, "Goupille"))}" displaycolor="{ROLE_COLOUR[r]}"/>' for r in roles)
    items = "".join(f'<item objectid="{n + 1}"/>' for n in range(1, len(pieces) + 1))
    model = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<model unit="millimeter" xml:lang="fr-FR" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
        f'<metadata name="Title">{escape(title)}</metadata><metadata name="Application">KnifeForge Pro</metadata>'
        f'<resources><basematerials id="1">{materials}</basematerials>{"".join(objects)}</resources>'
        f"<build>{items}</build></model>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>',
        )
        z.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>',
        )
        z.writestr("3D/3dmodel.model", model)
    return buf.getvalue()


def _stl(tris: list[Triangle], name: str) -> bytes:
    header = name.encode("ascii", "replace")[:80].ljust(80, b" ")
    out = [header, struct.pack("<I", len(tris))]
    for t in tris:
        out.append(struct.pack("<12fH", *_normal(t), *t[0], *t[1], *t[2], 0))
    return b"".join(out)


def _mm(value: float) -> str:
    return f"{round(value, 2):g}".replace(".", ",")


def _slug(text: str) -> str:
    keep = "".join(c if c.isalnum() else "_" for c in text.lower())
    return "_".join(filter(None, keep.split("_")))[:40] or "piece"


def to_stl_zip(asm: Assembly) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for n, s in enumerate(asm.everything, start=1):
            z.writestr(f"{n:02d}_{_slug(s.name)}_{_mm(s.thickness)}mm.stl", _stl(solid_triangles(s, flat=True), s.name))
    return buf.getvalue()


# ------------------------------------------------------------------------------------------
# CNC router: one DXF per plate, and what the cutter cannot reach
# ------------------------------------------------------------------------------------------


@dataclass
class ToolIssue:
    part: str
    kind: Literal["corner", "hole_too_small", "hole_corner"]
    x: float
    y: float
    size_mm: float  # thickest material left in a corner (square to the outline), or the hole's width


def tool_check(asm: Assembly, tool_diameter_mm: float) -> list[ToolIssue]:
    """A cutter of radius r runs around the outline (outside) and inside the holes: it cannot
    reach outline corners tighter than r (material left), nor fit in a hole narrower than 2r."""
    r = tool_diameter_mm / 2
    issues: list[ToolIssue] = []
    seen: set[int] = set()  # a pair of scales is one outline: checked once
    for s in asm.solids:
        for poly in s.polygons:
            if id(poly) in seen:
                continue
            seen.add(id(poly))
            outer = Polygon(poly.exterior)
            left = outer.buffer(r, quad_segs=32).buffer(-r, quad_segs=32).difference(outer)
            for g in _polygons(left):
                depth = _depth(g, outer) if g.area > 1e-6 else 0.0
                if depth >= MIN_ISSUE_MM:
                    c = g.representative_point()
                    issues.append(ToolIssue(s.name, "corner", c.x, c.y, round(depth, 3)))
            for ring in poly.interiors:
                hole = Polygon(ring)
                inner = hole.buffer(-r, quad_segs=32)
                c = hole.centroid
                if inner.is_empty:
                    minx, miny, maxx, maxy = hole.bounds
                    issues.append(ToolIssue(s.name, "hole_too_small", c.x, c.y, round(min(maxx - minx, maxy - miny), 3)))
                    continue
                left = hole.difference(inner.buffer(r, quad_segs=32))
                for g in _polygons(left):
                    depth = _depth(g, hole.exterior) if g.area > 1e-6 else 0.0
                    if depth >= MIN_ISSUE_MM:
                        p = g.representative_point()
                        issues.append(ToolIssue(s.name, "hole_corner", p.x, p.y, round(depth, 3)))
    return issues


def _depth(left: Polygon, edge) -> float:
    """How thick the material left in a corner is: its farthest point from the outline."""
    boundary = edge.exterior if hasattr(edge, "exterior") else edge
    return max(boundary.distance(Point(xy)) for xy in left.exterior.coords)


def to_cnc_zip(doc: DesignDocument, asm: Assembly, specs: list[PartSpec], tool_diameter_mm: float, title: str = "KnifeForge Pro") -> bytes:
    from app.services.export_service import design_to_dxf

    holes = [o for o in doc.objects if isinstance(o, PathObject) and next((l.role for l in doc.layers if l.id == o.layer), "") == "hole"]
    issues = tool_check(asm, tool_diameter_mm)
    buf = io.BytesIO()
    lines = [
        f"{title} : pièces pour l'usinage (fraiseuse 3 axes)",
        "",
        "Un fichier DXF par plaque, en millimètres, contour à la cote (sans compensation : la FAO",
        "décale la trajectoire du rayon de la fraise). Épaisseur dans le nom du fichier ; zéro Z en",
        "surface de la plaque. Les attaches qui tiennent les pièces se posent dans la FAO.",
        "",
        "Plaques :",
    ]
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        done: set[tuple[str, float]] = set()
        n = 0
        for s in specs:
            count = 2 if s.role in ("scales", "liners") else 1
            key = (s.object_id, s.thickness_mm)
            if key in done:
                continue
            done.add(key)
            n += 1
            obj = next(o for o in doc.objects if isinstance(o, PathObject) and o.id == s.object_id)
            sub = DesignDocument(version=doc.version, unit=doc.unit, layers=doc.layers, objects=[obj, *holes])
            name = f"{n:02d}_{_slug(obj.name or ROLE_LABEL.get(s.role, s.role))}_ep{_mm(s.thickness_mm)}mm.dxf"
            z.writestr(name, design_to_dxf(sub))
            lines.append(f"  {name} : épaisseur {s.thickness_mm:g} mm, {count} pièce(s)")
        pins = [p for p in asm.pins]
        if pins:
            lines += ["", "Goupilles et rivets (à couper dans la barre, non usinés) :"]
            for p in pins:
                u = unary_union(p.polygons)
                minx, miny, maxx, maxy = u.bounds
                lines.append(f"  {p.name} : Ø {maxx - minx:.2f} mm, longueur {p.thickness:.2f} mm")
        lines += ["", f"Contrôle de la fraise Ø {tool_diameter_mm:g} mm :"]
        if not issues:
            lines.append("  rien à signaler : la fraise atteint tous les contours.")
        for i in issues:
            where = f"x {i.x:.2f}, y {i.y:.2f} mm"
            if i.kind == "corner":
                lines.append(f"  {i.part} : angle intérieur trop serré ({where}), la fraise y laisse jusqu'à {i.size_mm:.2f} mm de matière")
            elif i.kind == "hole_corner":
                lines.append(f"  {i.part} : angle de perçage trop serré ({where}), jusqu'à {i.size_mm:.2f} mm de matière laissée")
            else:
                lines.append(f"  {i.part} : perçage de {i.size_mm:.2f} mm plus étroit que la fraise ({where}) : à percer")
        z.writestr("LISEZMOI.txt", "\r\n".join(lines) + "\r\n")
    return buf.getvalue()
