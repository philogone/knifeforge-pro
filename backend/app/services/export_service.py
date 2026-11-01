"""File exports: SVG (true Bézier curves, 1 unit = 1 mm), DXF (flattened
polylines for laser / waterjet / CNC), nesting layouts, and the dimensioned
client plan sheet.
"""

from __future__ import annotations

import io
import math
from datetime import date
from xml.sax.saxutils import escape

import ezdxf

from app.schemas.design import DesignDocument, DimensionObject, Node, PathObject
from app.services.geometry_service import (
    document_bounds,
    extract_engraving_lines,
    extract_parts,
    flatten_contour,
    polygon_rings,
)
from app.services.nesting_service import NestingResult

CUT_COLOR = "#e11d48"
ENGRAVE_COLOR = "#2563eb"
INK = "#0f172a"
GRIND_DASH = "4 1 0.8 1"  # dash-dot, sheet mm


def _num(value: float) -> str:
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def contour_path_d(nodes: list[Node], closed: bool, dx: float = 0.0, dy: float = 0.0, scale: float = 1.0) -> str:
    """SVG path data for a Bézier contour, optionally translated then scaled."""

    def pt(x: float, y: float) -> str:
        return f"{_num((x + dx) * scale)} {_num((y + dy) * scale)}"

    if not nodes:
        return ""
    parts = [f"M{pt(nodes[0].x, nodes[0].y)}"]

    def segment(a: Node, b: Node) -> str:
        if a.ox == 0 and a.oy == 0 and b.ix == 0 and b.iy == 0:
            return f"L{pt(b.x, b.y)}"
        return f"C{pt(a.x + a.ox, a.y + a.oy)} {pt(b.x + b.ix, b.y + b.iy)} {pt(b.x, b.y)}"

    for i in range(len(nodes) - 1):
        parts.append(segment(nodes[i], nodes[i + 1]))
    if closed:
        parts.append(segment(nodes[-1], nodes[0]))
        parts.append("Z")
    return "".join(parts)


def _object_d(obj: PathObject, dx: float = 0.0, dy: float = 0.0, scale: float = 1.0) -> str:
    return "".join(contour_path_d(c, obj.closed, dx, dy, scale) for c in obj.contours)


def _layer_roles(doc: DesignDocument) -> dict[str, tuple[str, bool]]:
    return {layer.id: (layer.role, layer.visible) for layer in doc.layers}


# ---------------------------------------------------------------------------
# Design -> SVG (1 user unit = 1 mm)
# ---------------------------------------------------------------------------


def design_to_svg(doc: DesignDocument, margin_mm: float = 5.0) -> str:
    bounds = document_bounds(doc)
    if bounds is None:
        raise ValueError("The design has nothing to export")
    minx, miny, maxx, maxy = bounds
    minx -= margin_mm
    miny -= margin_mm
    width = maxx - minx + margin_mm
    height = maxy - miny + margin_mm
    roles = _layer_roles(doc)

    elements: list[str] = []
    for obj in doc.objects:
        if not isinstance(obj, PathObject):
            continue
        role, visible = roles[obj.layer]
        if not visible or role not in ("cut", "hole", "engrave"):
            continue
        color = ENGRAVE_COLOR if role == "engrave" else CUT_COLOR
        fill = ' fill-rule="evenodd"' if obj.closed else ""
        elements.append(
            f'<path d="{_object_d(obj)}" fill="none" stroke="{color}" stroke-width="0.1"{fill}'
            f' data-layer="{escape(role)}"/>'
        )
    body = "\n  ".join(elements)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_num(width)}mm" height="{_num(height)}mm" '
        f'viewBox="{_num(minx)} {_num(miny)} {_num(width)} {_num(height)}">\n  {body}\n</svg>\n'
    )


# ---------------------------------------------------------------------------
# Nesting -> SVG
# ---------------------------------------------------------------------------

_PALETTE = ["#fecdd3", "#bae6fd", "#bbf7d0", "#fde68a", "#ddd6fe", "#fed7aa", "#a5f3fc", "#fbcfe8"]


def _rings_d(rings: list[list[tuple[float, float]]]) -> str:
    out = []
    for ring in rings:
        out.append("M" + "L".join(f"{_num(x)} {_num(y)}" for x, y in ring) + "Z")
    return "".join(out)


def nesting_to_svg(result: NestingResult, sheet_index: int) -> str:
    if not 0 <= sheet_index < len(result.sheets):
        raise ValueError("Sheet index out of range")
    sheet = result.sheets[sheet_index]
    w, h = result.sheet_length_mm, result.sheet_width_mm
    colors: dict[int, str] = {}
    shapes: list[str] = []
    for placement in sheet.placements:
        color = colors.setdefault(placement.item.design_id, _PALETTE[len(colors) % len(_PALETTE)])
        rings = polygon_rings(placement.geometry)
        minx, miny, maxx, maxy = placement.geometry.bounds
        label = escape(placement.item.design_name)
        shapes.append(
            f'<path d="{_rings_d(rings)}" fill="{color}" fill-rule="evenodd" stroke="{CUT_COLOR}" stroke-width="0.2"/>'
            f'<text x="{_num((minx + maxx) / 2)}" y="{_num((miny + maxy) / 2)}" font-size="{_num(min(6.0, max(2.0, (maxy - miny) / 6)))}" '
            f'text-anchor="middle" fill="{INK}" font-family="sans-serif">{label}</text>'
        )
    body = "\n  ".join(shapes)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_num(w)}mm" height="{_num(h)}mm" viewBox="0 0 {_num(w)} {_num(h)}">\n'
        f'  <rect x="0" y="0" width="{_num(w)}" height="{_num(h)}" fill="#f8fafc" stroke="{INK}" stroke-width="0.4"/>\n'
        f"  {body}\n</svg>\n"
    )


# ---------------------------------------------------------------------------
# DXF (R2010). DXF is y-up, the editor is y-down: y is flipped on export so the
# part looks the same in a CAD/CAM viewer.
# ---------------------------------------------------------------------------


def _new_dxf() -> ezdxf.document.Drawing:
    dxf = ezdxf.new("R2010")
    dxf.units = ezdxf.units.MM
    dxf.layers.add("CUT", color=1)
    dxf.layers.add("ENGRAVE", color=5)
    dxf.layers.add("SHEET", color=8)
    return dxf


def _dxf_bytes(dxf: ezdxf.document.Drawing) -> bytes:
    stream = io.StringIO()
    dxf.write(stream)
    return stream.getvalue().encode("utf-8")


def design_to_dxf(doc: DesignDocument) -> bytes:
    parts = extract_parts(doc)
    lines = extract_engraving_lines(doc)
    if not parts and not lines:
        raise ValueError("The design has nothing to export")
    bounds = document_bounds(doc)
    assert bounds is not None
    minx, _, _, maxy = bounds

    dxf = _new_dxf()
    msp = dxf.modelspace()
    for part in parts:
        for ring in polygon_rings(part.geometry):
            msp.add_lwpolyline([(x - minx, maxy - y) for x, y in ring], close=True, dxfattribs={"layer": "CUT"})
    for line in lines:
        msp.add_lwpolyline([(x - minx, maxy - y) for x, y in line], dxfattribs={"layer": "ENGRAVE"})
    return _dxf_bytes(dxf)


def nesting_to_dxf(result: NestingResult, sheet_index: int) -> bytes:
    if not 0 <= sheet_index < len(result.sheets):
        raise ValueError("Sheet index out of range")
    sheet = result.sheets[sheet_index]
    h = result.sheet_width_mm
    dxf = _new_dxf()
    msp = dxf.modelspace()
    msp.add_lwpolyline(
        [(0, 0), (result.sheet_length_mm, 0), (result.sheet_length_mm, h), (0, h)],
        close=True,
        dxfattribs={"layer": "SHEET"},
    )
    for placement in sheet.placements:
        for ring in polygon_rings(placement.geometry):
            msp.add_lwpolyline([(x, h - y) for x, y in ring], close=True, dxfattribs={"layer": "CUT"})
    return _dxf_bytes(dxf)


# ---------------------------------------------------------------------------
# Client plan sheet
# ---------------------------------------------------------------------------

PAPER_SIZES_MM = {"A4": (297.0, 210.0), "A3": (420.0, 297.0)}  # landscape (w, h)
_STANDARD_SCALES = [1, 2, 2.5, 4, 5, 10, 20, 25, 50, 100]
TITLE_BLOCK_H = 32.0
SHEET_MARGIN = 10.0


def _pick_scale(width_mm: float, height_mm: float, avail_w: float, avail_h: float) -> float:
    """Smallest reduction (largest drawing) from the standard series that fits.
    Returns a denominator: 1 = full size, 2 = 1:2…"""
    for denom in _STANDARD_SCALES:
        if width_mm / denom <= avail_w and height_mm / denom <= avail_h:
            return float(denom)
    return float(_STANDARD_SCALES[-1])


def _arrow(x: float, y: float, ux: float, uy: float, size: float = 2.4) -> str:
    """Filled arrow head whose tip is at (x, y) pointing along (ux, uy)."""
    nx, ny = -uy, ux
    bx, by = x - ux * size, y - uy * size
    pts = [(x, y), (bx + nx * size / 3.2, by + ny * size / 3.2), (bx - nx * size / 3.2, by - ny * size / 3.2)]
    return f'<polygon points="{" ".join(f"{_num(px)},{_num(py)}" for px, py in pts)}" fill="{INK}"/>'


def _dimension_svg(ax: float, ay: float, bx: float, by: float, offset: float, text: str) -> str:
    """Dimension line between two points in *paper* coordinates."""
    dx, dy = bx - ax, by - ay
    length = math.hypot(dx, dy)
    if length < 0.5:
        return ""
    ux, uy = dx / length, dy / length
    nx, ny = -uy, ux
    sign = 1 if offset >= 0 else -1
    off = abs(offset)
    ext = off + 2.0
    a2 = (ax + nx * sign * off, ay + ny * sign * off)
    b2 = (bx + nx * sign * off, by + ny * sign * off)
    out = [
        f'<line x1="{_num(ax + nx * sign * 1.0)}" y1="{_num(ay + ny * sign * 1.0)}" x2="{_num(ax + nx * sign * ext)}" y2="{_num(ay + ny * sign * ext)}" stroke="{INK}" stroke-width="0.18"/>',
        f'<line x1="{_num(bx + nx * sign * 1.0)}" y1="{_num(by + ny * sign * 1.0)}" x2="{_num(bx + nx * sign * ext)}" y2="{_num(by + ny * sign * ext)}" stroke="{INK}" stroke-width="0.18"/>',
        f'<line x1="{_num(a2[0])}" y1="{_num(a2[1])}" x2="{_num(b2[0])}" y2="{_num(b2[1])}" stroke="{INK}" stroke-width="0.25"/>',
        _arrow(a2[0], a2[1], -ux, -uy),
        _arrow(b2[0], b2[1], ux, uy),
    ]
    angle = math.degrees(math.atan2(dy, dx))
    if angle > 90 or angle < -90:
        angle += 180
    mx, my = (a2[0] + b2[0]) / 2 + nx * sign * 1.2, (a2[1] + b2[1]) / 2 + ny * sign * 1.2
    out.append(
        f'<text x="{_num(mx)}" y="{_num(my)}" font-size="3.5" text-anchor="middle" fill="{INK}" font-family="sans-serif" '
        f'transform="rotate({_num(angle)} {_num(mx)} {_num(my)})">{escape(text)}</text>'
    )
    return "".join(out)


def _fmt_mm(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".") + " mm"


def plan_svg(
    doc: DesignDocument,
    title: str,
    paper: str = "A4",
    scale_denominator: float | None = None,
    customer: str | None = None,
    order_ref: str | None = None,
    knife_model: str | None = None,
    material: str | None = None,
    notes: str | None = None,
) -> str:
    if paper not in PAPER_SIZES_MM:
        raise ValueError(f"Unknown paper size {paper!r}")
    bounds = document_bounds(doc)
    if bounds is None:
        raise ValueError("The design has nothing to draw")
    minx, miny, maxx, maxy = bounds
    dw, dh = maxx - minx, maxy - miny
    page_w, page_h = PAPER_SIZES_MM[paper]

    # Room reserved around the drawing for the two overall dimension lines.
    dim_room = 16.0
    avail_w = page_w - 2 * SHEET_MARGIN - dim_room
    avail_h = page_h - 2 * SHEET_MARGIN - TITLE_BLOCK_H - dim_room
    denom = scale_denominator or _pick_scale(dw, dh, avail_w, avail_h)
    s = 1.0 / denom

    draw_w, draw_h = dw * s, dh * s
    ox = SHEET_MARGIN + (avail_w - draw_w) / 2 + 2
    oy = SHEET_MARGIN + (avail_h - draw_h) / 2 + 2

    def X(x: float) -> float:
        return ox + (x - minx) * s

    def Y(y: float) -> float:
        return oy + (y - miny) * s

    roles = _layer_roles(doc)
    shapes: list[str] = []
    for obj in doc.objects:
        if not isinstance(obj, PathObject):
            continue
        role, visible = roles[obj.layer]
        if not visible or role not in ("cut", "hole", "engrave"):
            continue
        color = INK if role != "engrave" else ENGRAVE_COLOR
        width = 0.5 if role == "cut" else 0.3
        fill = ' fill-rule="evenodd"' if obj.closed else ""
        shapes.append(
            f'<path d="{_object_d(obj, -minx, -miny, s)}" transform="translate({_num(ox)} {_num(oy)})" '
            f'fill="none" stroke="{color}" stroke-width="{width}"{fill}/>'
        )
    # Grind lines: drawn over the part, dash-dot (the drawing convention), never part of its size.
    # The dash pattern is in sheet mm so it reads the same at any scale.
    grind_lines = 0
    for obj in doc.objects:
        if not isinstance(obj, PathObject):
            continue
        role, visible = roles[obj.layer]
        if not visible or role != "grind":
            continue
        grind_lines += 1
        shapes.append(
            f'<path d="{_object_d(obj, -minx, -miny, s)}" transform="translate({_num(ox)} {_num(oy)})" '
            f'fill="none" stroke="{INK}" stroke-width="0.3" stroke-dasharray="{GRIND_DASH}" data-layer="grind"/>'
        )

    dims: list[str] = []
    # User-placed dimensions on dimension layers. Track how far their lines reach below / right of
    # the part so the overall dimensions go beyond them instead of being drawn on top of them.
    lowest, rightmost = Y(maxy), X(maxx)
    for obj in doc.objects:
        if not isinstance(obj, DimensionObject):
            continue
        role, visible = roles[obj.layer]
        if not visible:
            continue
        measured = math.hypot(obj.b[0] - obj.a[0], obj.b[1] - obj.a[1])
        label = obj.label or _fmt_mm(measured)
        ax, ay, bx, by = X(obj.a[0]), Y(obj.a[1]), X(obj.b[0]), Y(obj.b[1])
        offset = obj.offset * s if obj.offset else 6.0
        dims.append(_dimension_svg(ax, ay, bx, by, offset, label))
        length = math.hypot(bx - ax, by - ay)
        if length >= 0.5:
            nx, ny = -(by - ay) / length * offset, (bx - ax) / length * offset
            lowest = max(lowest, ay + ny, by + ny)
            rightmost = max(rightmost, ax + nx, bx + nx)
    # Overall width (below) and height (right), at least 7 mm out and 7 mm past any user dimension
    dims.append(_dimension_svg(X(minx), Y(maxy), X(maxx), Y(maxy), max(7.0, lowest - Y(maxy) + 7.0), _fmt_mm(dw)))
    dims.append(_dimension_svg(X(maxx), Y(maxy), X(maxx), Y(miny), max(7.0, rightmost - X(maxx) + 7.0), _fmt_mm(dh)))

    # Title block
    tb_x, tb_y = SHEET_MARGIN, page_h - SHEET_MARGIN - TITLE_BLOCK_H
    tb_w = page_w - 2 * SHEET_MARGIN
    cell = tb_w / 4
    scale_label = "1:1" if denom == 1 else f"1:{_num(denom)}"
    fields = [
        ("Client", customer or "—"),
        ("Commande", order_ref or "—"),
        ("Modèle", knife_model or "—"),
        ("Matière", material or "—"),
        ("Échelle", scale_label),
        ("Dimensions", f"{_fmt_mm(dw)} × {_fmt_mm(dh)}"),
        ("Date", date.today().isoformat()),
        ("Papier", f"{paper} paysage"),
    ]
    tb: list[str] = [
        f'<rect x="{_num(tb_x)}" y="{_num(tb_y)}" width="{_num(tb_w)}" height="{_num(TITLE_BLOCK_H)}" fill="none" stroke="{INK}" stroke-width="0.5"/>',
        f'<text x="{_num(tb_x + 3)}" y="{_num(tb_y + 7)}" font-size="6" font-weight="bold" fill="{INK}" font-family="sans-serif">{escape(title)}</text>',
    ]
    if grind_lines:
        # legend: a short dash-dot sample, then its meaning, top right of the title block
        lx = tb_x + tb_w - 3
        tb.append(
            f'<text x="{_num(lx)}" y="{_num(tb_y + 4.2)}" font-size="2.6" text-anchor="end" fill="{INK}" font-family="sans-serif">Ligne d’émouture</text>'
            f'<line x1="{_num(lx - 44)}" y1="{_num(tb_y + 3.3)}" x2="{_num(lx - 32)}" y2="{_num(tb_y + 3.3)}" stroke="{INK}" stroke-width="0.3" stroke-dasharray="{GRIND_DASH}"/>'
        )
    if notes:
        notes_y = tb_y + 8.6 if grind_lines else tb_y + 7
        tb.append(
            f'<text x="{_num(tb_x + tb_w - 3)}" y="{_num(notes_y)}" font-size="3.2" text-anchor="end" fill="{INK}" font-family="sans-serif">{escape(notes[:120])}</text>'
        )
    row_h = (TITLE_BLOCK_H - 11) / 2
    for i, (label, value) in enumerate(fields):
        cx = tb_x + (i % 4) * cell
        cy = tb_y + 11 + (i // 4) * row_h
        tb.append(
            f'<rect x="{_num(cx)}" y="{_num(cy)}" width="{_num(cell)}" height="{_num(row_h)}" fill="none" stroke="{INK}" stroke-width="0.25"/>'
            f'<text x="{_num(cx + 2)}" y="{_num(cy + 3.6)}" font-size="2.4" fill="#64748b" font-family="sans-serif">{escape(label)}</text>'
            f'<text x="{_num(cx + 2)}" y="{_num(cy + row_h - 2)}" font-size="3.6" fill="{INK}" font-family="sans-serif">{escape(value)}</text>'
        )

    frame = (
        f'<rect x="{_num(SHEET_MARGIN / 2)}" y="{_num(SHEET_MARGIN / 2)}" width="{_num(page_w - SHEET_MARGIN)}" '
        f'height="{_num(page_h - SHEET_MARGIN)}" fill="none" stroke="{INK}" stroke-width="0.35"/>'
    )
    body = "\n  ".join([frame, *shapes, *dims, *tb])
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_num(page_w)}mm" height="{_num(page_h)}mm" '
        f'viewBox="0 0 {_num(page_w)} {_num(page_h)}">\n'
        f'  <rect width="{_num(page_w)}" height="{_num(page_h)}" fill="#ffffff"/>\n  {body}\n</svg>\n'
    )


# Re-exported for tests
__all__ = [
    "contour_path_d",
    "design_to_dxf",
    "design_to_svg",
    "flatten_contour",
    "nesting_to_dxf",
    "nesting_to_svg",
    "plan_svg",
]
