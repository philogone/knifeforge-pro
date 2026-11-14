"""Parametric starting points for the editor (and the demo seed): a few
knifemaking outlines built from real Bézier nodes, in millimetres, y-down.
"""

from __future__ import annotations

import math
from typing import Any

KAPPA = 0.5522847498  # circle-to-cubic-Bézier constant

LAYERS: list[dict[str, Any]] = [
    {"id": "cut", "name": "Découpe", "role": "cut", "visible": True, "locked": False},
    {"id": "holes", "name": "Perçages", "role": "hole", "visible": True, "locked": False},
    {"id": "engrave", "name": "Gravure", "role": "engrave", "visible": True, "locked": False},
    {"id": "grind", "name": "Émouture", "role": "grind", "visible": True, "locked": False},
    {"id": "construction", "name": "Construction", "role": "construction", "visible": True, "locked": False},
    {"id": "dimensions", "name": "Cotes", "role": "dimension", "visible": True, "locked": False},
]


def node(x: float, y: float, ix: float = 0.0, iy: float = 0.0, ox: float = 0.0, oy: float = 0.0) -> dict[str, float]:
    return {"x": round(x, 4), "y": round(y, 4), "ix": round(ix, 4), "iy": round(iy, 4), "ox": round(ox, 4), "oy": round(oy, 4)}


def circle_nodes(cx: float, cy: float, r: float) -> list[dict[str, float]]:
    k = KAPPA * r
    return [
        node(cx + r, cy, 0, -k, 0, k),
        node(cx, cy + r, k, 0, -k, 0),
        node(cx - r, cy, 0, k, 0, -k),
        node(cx, cy - r, -k, 0, k, 0),
    ]


def rounded_rect_nodes(x: float, y: float, w: float, h: float, r: float) -> list[dict[str, float]]:
    r = min(r, w / 2, h / 2)
    k = KAPPA * r
    return [
        node(x + r, y, -k, 0, 0, 0),
        node(x + w - r, y, 0, 0, k, 0),
        node(x + w, y + r, 0, -k, 0, 0),
        node(x + w, y + h - r, 0, 0, 0, k),
        node(x + w - r, y + h, k, 0, 0, 0),
        node(x + r, y + h, 0, 0, -k, 0),
        node(x, y + h - r, 0, k, 0, 0),
        node(x, y + r, 0, 0, 0, -k),
    ]


def ellipse_nodes(cx: float, cy: float, rx: float, ry: float) -> list[dict[str, float]]:
    kx, ky = KAPPA * rx, KAPPA * ry
    return [
        node(cx + rx, cy, 0, -ky, 0, ky),
        node(cx, cy + ry, kx, 0, -kx, 0),
        node(cx - rx, cy, 0, ky, 0, -ky),
        node(cx, cy - ry, -kx, 0, kx, 0),
    ]


def _path(obj_id: str, layer: str, name: str | None, contours: list[list[dict[str, float]]], closed: bool = True) -> dict[str, Any]:
    return {"id": obj_id, "type": "path", "layer": layer, "name": name, "closed": closed, "contours": contours}


def document(objects: list[dict[str, Any]]) -> dict[str, Any]:
    return {"version": 1, "unit": "mm", "layers": [dict(layer) for layer in LAYERS], "objects": objects}


def blank_document() -> dict[str, Any]:
    return document([])


def _tip(x: float, y: float, a: float, la: float, b: float, lb: float) -> dict[str, float]:
    """A true point: the spine comes in at `a` degrees below the horizontal, the edge leaves
    backwards at `b` degrees below the horizontal."""
    ra, rb = math.radians(a), math.radians(b)
    return node(x, y, -math.cos(ra) * la, -math.sin(ra) * la, -math.cos(rb) * lb, math.sin(rb) * lb)


# Blade outlines (same drawings as the editor's shape library, frontend/src/editor/shapes.ts):
# spine at y = 0, edge at y = h, from the spine at the blade's start (t, 0) round the tip back
# to the edge at (t, h). They return the nodes and the tip.


def _drop_point(t: float, l: float, h: float) -> tuple[list[dict[str, float]], tuple[float, float]]:
    tip = (t + l, h * 0.4)
    return [
        node(t, 0),
        node(t + l * 0.56, 0, 0, 0, l * 0.2, 0),
        _tip(tip[0], tip[1], 26, l * 0.12, 36, h * 0.55),
        node(t + l * 0.5, h, l * 0.24, 0, 0, 0),
        node(t, h),
    ], tip


def _grind(x0: float, tip: tuple[float, float], h: float, percent: float) -> list[dict[str, float]]:
    """Plunge curving up from the edge near the heel, then running out at the tip."""
    tx, ty = tip[0] - 2, min(tip[1], h)
    length = tx - x0
    gy = h * (1 - percent / 100)
    plunge = min(10, length * 0.1)
    return [
        node(x0, h),
        node(x0 + plunge, gy, -plunge * 0.4, (h - gy) * 0.6),
        node(x0 + length * 0.62, gy),
        node(tx, ty, -length * 0.15, (gy - ty) * 0.3),
    ]


def full_tang_blade(
    blade_len: float = 112, height: float = 32, handle_len: float = 105, handle_h: float = 24, pins: int = 2, pin_d: float = 5
) -> dict[str, Any]:
    """Drop-point blade with its full tang shaped as the handle: sharpening choil, finger guard,
    index groove, palm swell, flared butt. Tip to the right, edge down."""
    t, l, h, hh = handle_len, blade_len, height, min(handle_h, height)
    body, tip = _drop_point(t, l, h)
    last = body.pop()
    rc = max(1, min(3, h * 0.08))
    gb = rc * 0.9
    step = h - hh
    gd = min(2, step * 0.22)
    gw = min(t * 0.22, step * 1.2 + 7)
    sw = hh * 0.07
    edge_start = t + gb + 2 * rc
    outline = body + [
        node(edge_start, h, last["ix"], last["iy"], 0, -rc * KAPPA),
        node(t + gb + rc, h - rc, rc * KAPPA, 0, -rc * KAPPA, 0),
        node(t + gb, h, 0, -rc * KAPPA, 0, rc * 0.5),
        node(t - gb * 0.4, h + gd, gb * 0.8, 0, -gb * 0.9 - step * 0.2, 0),
        node(t - gw, hh - min(1.5, hh * 0.05), gw * 0.5, 0, -t * 0.16, 0),
        node(t * 0.36, hh + sw, t * 0.18, 0, -t * 0.2, 0),
        node(t * 0.06, hh + sw * 0.4, t * 0.12, 0, -t * 0.04, 0),
        node(0, hh * 0.52, 0, hh * 0.32, 0, -hh * 0.3),
        node(t * 0.06, hh * 0.04, -t * 0.04, 0, t * 0.25, 0),
    ]
    objects = [_path("blade", "cut", "Lame", [outline]), _path("grind", "grind", "Émouture", [_grind(edge_start + 1, tip, h, 50)], closed=False)]
    x0, x1 = t * 0.2, t - gw - pin_d
    for i in range(pins):
        cx = x0 + (x1 - x0) * i / (pins - 1) if pins > 1 else (x0 + x1) / 2
        objects.append(_path(f"pin{i + 1}", "holes", f"Perçage {i + 1}", [circle_nodes(cx, hh / 2, pin_d / 2)]))
    objects.append({"id": "dim-blade", "type": "dimension", "layer": "dimensions", "a": [t, 0], "b": [t + l, 0], "offset": -8, "label": None})
    return document(objects)


def folder_blade(blade_len: float = 85, height: float = 20, talon_len: float = 24, pivot_d: float = 4) -> dict[str, Any]:
    """Folding knife blade (demo data): round tang about the pivot hole, flat kick, sharpening choil."""
    t, l, h = talon_len, blade_len, height
    body, tip = _drop_point(t, l, h)
    last = body.pop()
    rc = max(1, min(3, h * 0.08))
    r = h / 2
    cx = max(r * 0.6, t - min(t * 0.45, r * 0.9))
    edge_start = t + 2 * rc
    outline = body + [
        node(edge_start, h, last["ix"], last["iy"], 0, -rc * KAPPA),
        node(t + rc, h - rc, rc * KAPPA, 0, -rc * KAPPA, 0),
        node(t, h, 0, -rc * KAPPA, 0, 0),
        node(cx, h, 0, 0, -r * KAPPA, 0),
        node(cx - r, r, 0, r * KAPPA, 0, -r * KAPPA),
        node(cx, 0, -r * KAPPA, 0, 0, 0),
    ]
    objects = [
        _path("blade", "cut", "Lame", [outline]),
        _path("grind", "grind", "Émouture", [_grind(edge_start + 1, tip, h, 55)], closed=False),
        _path("pivot", "holes", "Pivot", [circle_nodes(cx, r, pivot_d / 2)]),
        {"id": "dim-blade", "type": "dimension", "layer": "dimensions", "a": [t, 0], "b": [t + l, 0], "offset": -8, "label": None},
    ]
    return document(objects)


def handle_scale(length: float = 110, width: float = 25, radius: float = 6, hole_inset: float = 14) -> dict[str, Any]:
    objects = [
        _path("scale", "cut", "Plaquette", [rounded_rect_nodes(0, 0, length, width, radius)]),
        _path("pin1", "holes", "Perçage 1", [circle_nodes(hole_inset, width / 2, 2)]),
        _path("pin2", "holes", "Perçage 2", [circle_nodes(length - hole_inset, width / 2, 2)]),
    ]
    return document(objects)


def folder_handle_scale(length: float = 110, width: float = 22, pivot_d: float = 4, pin_d: float = 3) -> dict[str, Any]:
    """Scale of a folding knife, blade side to the right: round nose about the pivot, a light
    finger choil, palm swell, slightly dropped butt (bird's head)."""
    ln, w = length, width
    r = w / 2
    px = ln - r
    outline = [
        node(w * 0.45, w * 0.06, -w * 0.25, 0, ln * 0.3, 0),
        node(px, 0, -ln * 0.25, 0, r * KAPPA, 0),
        node(ln, r, 0, -r * KAPPA, 0, r * KAPPA),
        node(px, w, r * KAPPA, 0, -ln * 0.06, 0),
        node(ln * 0.74, w - min(1.5, w * 0.07), ln * 0.06, 0, -ln * 0.12, 0),
        node(ln * 0.36, w + min(1.5, w * 0.07), ln * 0.16, 0, -ln * 0.18, 0),
        node(0, w * 0.68, ln * 0.04, w * 0.3, 0, -w * 0.32),
    ]
    objects = [
        _path("scale", "cut", "Plaquette", [outline]),
        _path("pivot", "holes", "Pivot", [circle_nodes(px, r, pivot_d / 2)]),
        _path("pin1", "holes", "Goupille arrière", [circle_nodes(w * 0.7, w * 0.5, pin_d / 2)]),
    ]
    return document(objects)


def felicie() -> dict[str, Any]:
    """« Félicie », a fixed blade drawn by hand by a knifemaker (Philogone) with this tool and
    shared as an example: deep finger choil, short handle with a bird's-head butt, 211 × 31 mm."""
    blade = [
        node(211, 8, -22.722, 22.045, -53.218, -9.338),
        node(84, 0, 0, 0, -30.543, 0),
        node(0, 6, 16.295, -4.452, 1.692, 16.662),
        node(41, 26, -10.977, 9.293, 26.108, -15.33),
        node(85, 31, -3.382, -10.836, 90.286, -0.94),
    ]
    objects = [
        _path("blade", "cut", "Lame", [blade]),
        _path("grind", "grind", "Émouture", [[node(81, 24, 0, 0, 14.786, -18.359), node(185, 8, -35.249, -1.28, 0, 0)]], closed=False),
        _path("pin1", "holes", "Perçage 1", [circle_nodes(24, 14, 2)]),
        _path("pin2", "holes", "Perçage 2", [circle_nodes(67, 10, 2)]),
    ]
    return document(objects)


def oval_guard(width: float = 42, height: float = 16, slot_w: float = 18, slot_h: float = 4.5) -> dict[str, Any]:
    objects = [
        _path("guard", "cut", "Garde", [ellipse_nodes(width / 2, height / 2, width / 2, height / 2)]),
        _path(
            "slot", "holes", "Fente de soie", [rounded_rect_nodes((width - slot_w) / 2, (height - slot_h) / 2, slot_w, slot_h, slot_h / 2)]
        ),
    ]
    return document(objects)


# Blade profiles are offered from the editor's shape library (frontend/src/editor/shapes.ts),
# grouped by family; the server lists the other starting points.
TEMPLATES: list[dict[str, Any]] = [
    {"key": "blank", "name": "Page vierge", "kind": "template", "build": blank_document},
    {"key": "felicie", "name": "Couteau « Félicie » (exemple dessiné à la main)", "kind": "blade", "build": felicie},
    {"key": "handle-scale", "name": "Plaquette de manche", "kind": "handle_scale", "build": handle_scale},
    {"key": "folder-handle-scale", "name": "Plaquette de pliant galbée", "kind": "handle_scale", "build": folder_handle_scale},
    {"key": "oval-guard", "name": "Garde ovale à fente", "kind": "guard", "build": oval_guard},
    {"key": "calibration-plate", "name": "Planche de contrôle (pièces étalons)", "kind": "template", "build": lambda: _calibration_plate()},
]


def _calibration_plate() -> dict[str, Any]:
    from app.services.calibration import plate_document  # calibration imports this module

    return plate_document()


def list_templates() -> list[dict[str, Any]]:
    return [{"key": t["key"], "name": t["name"], "kind": t["kind"], "document": t["build"]()} for t in TEMPLATES]
