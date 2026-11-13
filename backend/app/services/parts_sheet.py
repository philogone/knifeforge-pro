"""Parts sheet: the design printed at true size (1:1), to glue on steel, wood or G10 and work
from by hand.

- Thin black outlines (cut and holes), engraving in blue, grind lines dash-dot.
- A punch mark (cross) at the centre of every hole, to centre-punch before drilling.
- A part larger than the paper is tiled over several pages that overlap by `OVERLAP_MM`; the
  overlap is shaded and carries registration crosses at the same design coordinates on both
  pages, so the pages line up exactly.
- Every page has a 100 mm check bar: if it does not measure 100 mm, the printer scaled the page.

Curves are drawn as true Béziers (no flattening): the printer's own resolution is the limit.
"""

from __future__ import annotations

import io
import math
from datetime import date

from reportlab.lib.colors import Color, HexColor
from reportlab.pdfgen import canvas

from app.schemas.design import DesignDocument, Node, PathObject
from app.services.geometry_service import document_bounds, flatten_contour

PT_PER_MM = 72 / 25.4
PAPERS_MM = {"A4": (210.0, 297.0), "A3": (297.0, 420.0)}  # portrait (w, h)
MARGIN_MM = 10.0
FOOTER_MM = 18.0
OVERLAP_MM = 15.0
REGISTRATION_STEP_MM = 25.0
CHECK_BAR_MM = 100.0
MAX_PAGES = 40

INK = HexColor("#0f172a")
ENGRAVE = HexColor("#2563eb")
GRIND = HexColor("#6f6a60")
MUTED = HexColor("#6f6a60")
OVERLAP_FILL = Color(0.43, 0.42, 0.38, alpha=0.08)
DRAWN_ROLES = ("cut", "hole", "engrave", "grind")


class PartsSheetError(ValueError):
    pass


def _layout(width: float, height: float, paper: str) -> tuple[float, float, int, int]:
    """Orientation giving the fewest pages: (page_w, page_h, columns, rows)."""
    best = None
    pw, ph = PAPERS_MM[paper]
    for page_w, page_h in ((pw, ph), (ph, pw)):
        area_w = page_w - 2 * MARGIN_MM
        area_h = page_h - 2 * MARGIN_MM - FOOTER_MM
        cols = max(1, math.ceil((width - OVERLAP_MM) / (area_w - OVERLAP_MM))) if width > area_w else 1
        rows = max(1, math.ceil((height - OVERLAP_MM) / (area_h - OVERLAP_MM))) if height > area_h else 1
        if best is None or cols * rows < best[2] * best[3]:
            best = (page_w, page_h, cols, rows)
    return best


def hole_centres(doc: DesignDocument) -> list[tuple[float, float]]:
    """Centre of each closed contour on a hole layer (centre of its flattened outline's box:
    exact for circles and symmetric slots)."""
    roles = {layer.id: layer.role for layer in doc.layers}
    centres = []
    for obj in doc.objects:
        if not isinstance(obj, PathObject) or roles.get(obj.layer) != "hole" or not obj.closed:
            continue
        for contour in obj.contours:
            pts = flatten_contour(contour, True)
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            centres.append(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2))
    return centres


def parts_sheet_pdf(doc: DesignDocument, title: str, paper: str = "A4", workshop: str | None = None) -> bytes:
    if paper not in PAPERS_MM:
        raise PartsSheetError("Unknown paper size")
    bounds = document_bounds(doc)
    if bounds is None:
        raise PartsSheetError("The design has nothing to export")
    minx, miny, maxx, maxy = bounds
    # a little air around the parts so outlines never sit on the tile edge
    minx, miny, maxx, maxy = minx - 3, miny - 3, maxx + 3, maxy + 3
    width, height = maxx - minx, maxy - miny
    page_w, page_h, cols, rows = _layout(width, height, paper)
    if cols * rows > MAX_PAGES:
        raise PartsSheetError("Too large for a parts sheet: use the client plan at a reduced scale")
    area_w = page_w - 2 * MARGIN_MM
    area_h = page_h - 2 * MARGIN_MM - FOOTER_MM
    step_x = area_w - OVERLAP_MM
    step_y = area_h - OVERLAP_MM

    roles = {layer.id: (layer.role, layer.visible) for layer in doc.layers}
    holes = hole_centres(doc)
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(page_w * PT_PER_MM, page_h * PT_PER_MM))
    c.setTitle(title)
    c.setCreator("KnifeForge Pro")
    total = cols * rows

    for row in range(rows):
        for col in range(cols):
            # design window shown on this page
            wx0 = minx + col * step_x
            wy0 = miny + row * step_y
            wx1, wy1 = wx0 + area_w, wy0 + area_h
            ox, oy = MARGIN_MM, page_h - MARGIN_MM  # page mm of the window's top-left

            def to_pt(x: float, y: float) -> tuple[float, float]:
                return ((ox + x - wx0) * PT_PER_MM, (oy - (y - wy0)) * PT_PER_MM)

            c.saveState()
            clip = c.beginPath()
            clip.rect(MARGIN_MM * PT_PER_MM, (page_h - MARGIN_MM - area_h) * PT_PER_MM, area_w * PT_PER_MM, area_h * PT_PER_MM)
            c.clipPath(clip, stroke=0, fill=0)

            # overlap strips shared with the neighbouring pages, and their registration crosses
            c.setFillColor(OVERLAP_FILL)
            strips = []
            if col > 0:
                strips.append((wx0, wy0, wx0 + OVERLAP_MM, wy1))
            if col < cols - 1:
                strips.append((wx1 - OVERLAP_MM, wy0, wx1, wy1))
            if row > 0:
                strips.append((wx0, wy0, wx1, wy0 + OVERLAP_MM))
            if row < rows - 1:
                strips.append((wx0, wy1 - OVERLAP_MM, wx1, wy1))
            for sx0, sy0, sx1, sy1 in strips:
                x0, y0 = to_pt(sx0, sy1)
                x1, y1 = to_pt(sx1, sy0)
                c.rect(x0, y0, x1 - x0, y1 - y0, stroke=0, fill=1)
                c.setStrokeColor(MUTED)
                c.setLineWidth(0.3)
                gx = math.ceil(sx0 / REGISTRATION_STEP_MM) * REGISTRATION_STEP_MM
                while gx <= sx1:
                    gy = math.ceil(sy0 / REGISTRATION_STEP_MM) * REGISTRATION_STEP_MM
                    while gy <= sy1:
                        px, py = to_pt(gx, gy)
                        arm = 2.5 * PT_PER_MM
                        c.line(px - arm, py, px + arm, py)
                        c.line(px, py - arm, px, py + arm)
                        c.circle(px, py, 1.2 * PT_PER_MM, stroke=1, fill=0)
                        gy += REGISTRATION_STEP_MM
                    gx += REGISTRATION_STEP_MM

            # the parts, as true Béziers
            for obj in doc.objects:
                if not isinstance(obj, PathObject):
                    continue
                role, visible = roles.get(obj.layer, ("construction", False))
                if not visible or role not in DRAWN_ROLES:
                    continue
                c.setStrokeColor(ENGRAVE if role == "engrave" else GRIND if role == "grind" else INK)
                c.setLineWidth(0.5 if role == "grind" else 0.35)
                c.setDash([4 * PT_PER_MM, PT_PER_MM, 0.8 * PT_PER_MM, PT_PER_MM] if role == "grind" else [])
                path = c.beginPath()
                for contour in obj.contours:
                    _bezier_contour(path, contour, obj.closed, to_pt)
                c.drawPath(path, stroke=1, fill=0)
            c.setDash([])

            # punch marks: a cross through each hole centre, longer than the hole
            c.setStrokeColor(INK)
            c.setLineWidth(0.3)
            for hx, hy in holes:
                px, py = to_pt(hx, hy)
                arm = 3.5 * PT_PER_MM
                c.line(px - arm, py, px + arm, py)
                c.line(px, py - arm, px, py + arm)
            c.restoreState()

            _footer(c, page_w, title, workshop, row, col, rows, cols, total)
            c.showPage()
    c.save()
    return buffer.getvalue()


def _bezier_contour(path, nodes: list[Node], closed: bool, to_pt) -> None:
    if not nodes:
        return
    path.moveTo(*to_pt(nodes[0].x, nodes[0].y))
    pairs = list(zip(nodes, nodes[1:]))
    if closed:
        pairs.append((nodes[-1], nodes[0]))
    for a, b in pairs:
        if a.ox == 0 and a.oy == 0 and b.ix == 0 and b.iy == 0:
            path.lineTo(*to_pt(b.x, b.y))
        else:
            path.curveTo(*to_pt(a.x + a.ox, a.y + a.oy), *to_pt(b.x + b.ix, b.y + b.iy), *to_pt(b.x, b.y))
    if closed:
        path.close()


def _footer(c, page_w: float, title: str, workshop: str | None, row: int, col: int, rows: int, cols: int, total: int) -> None:
    base = MARGIN_MM * PT_PER_MM
    left = MARGIN_MM * PT_PER_MM
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(left, base + 9 * PT_PER_MM, title[:80])
    c.setFont("Helvetica", 7)
    c.setFillColor(MUTED)
    who = f"{workshop} · " if workshop else ""
    c.drawString(left, base + 5 * PT_PER_MM, f"{who}Feuille de pièces · échelle 1:1 · imprimer à 100 %, sans « ajuster à la page » · {date.today():%d/%m/%Y}")
    page = row * cols + col + 1
    where = f"page {page}/{total}" + (f" · ligne {row + 1}, colonne {col + 1}" if total > 1 else "")
    c.drawRightString((page_w - MARGIN_MM) * PT_PER_MM, base + 9 * PT_PER_MM, where)
    # 100 mm check bar, alternating 10 mm blocks
    bar_y = base + 0.8 * PT_PER_MM
    for i in range(10):
        c.setFillColor(INK if i % 2 == 0 else HexColor("#ffffff"))
        c.setStrokeColor(INK)
        c.setLineWidth(0.3)
        c.rect(left + i * 10 * PT_PER_MM, bar_y, 10 * PT_PER_MM, 1.6 * PT_PER_MM, stroke=1, fill=1)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 6.5)
    c.drawString(left + (CHECK_BAR_MM + 2) * PT_PER_MM, bar_y + 0.2 * PT_PER_MM, "← doit mesurer 100 mm")
