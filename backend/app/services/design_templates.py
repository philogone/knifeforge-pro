"""Parametric starting points for the editor (and the demo seed): a few
knifemaking outlines built from real Bézier nodes, in millimetres, y-down.
"""

from __future__ import annotations

from typing import Any

KAPPA = 0.5522847498  # circle-to-cubic-Bézier constant

LAYERS: list[dict[str, Any]] = [
    {"id": "cut", "name": "Découpe", "role": "cut", "visible": True, "locked": False},
    {"id": "holes", "name": "Perçages", "role": "hole", "visible": True, "locked": False},
    {"id": "engrave", "name": "Gravure", "role": "engrave", "visible": True, "locked": False},
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


def drop_point_blade(
    blade_len: float = 112, tang_len: float = 70, height: float = 32, tang_width: float = 16, pin_holes: int = 2
) -> dict[str, Any]:
    """Drop-point blade with a full-width-ish tang, tip to the right, edge down."""
    ty = height * 0.2
    t, l, h = tang_len, blade_len, height
    outline = [
        node(0, ty),
        node(t - 6, ty),
        node(t, 0),
        node(t + l * 0.72, 0, 0, 0, l * 0.17, 0),
        node(t + l, h * 0.55, -l * 0.08, -h * 0.38, -l * 0.05, h * 0.3),
        node(t + l * 0.55, h, l * 0.2, 0, 0, 0),
        node(t, h),
        node(t - 6, ty + tang_width),
        node(0, ty + tang_width),
    ]
    objects = [_path("blade", "cut", "Lame", [outline])]
    for i in range(pin_holes):
        cx = t * (0.22 + 0.4 * i / max(1, pin_holes - 1)) if pin_holes > 1 else t * 0.4
        objects.append(_path(f"pin{i + 1}", "holes", f"Perçage {i + 1}", [circle_nodes(cx, ty + tang_width / 2, 2.5)]))
    objects.append(
        {"id": "dim-blade", "type": "dimension", "layer": "dimensions", "a": [t, h], "b": [t + l, h], "offset": 8, "label": None}
    )
    return document(objects)


def handle_scale(length: float = 110, width: float = 25, radius: float = 6, hole_inset: float = 14) -> dict[str, Any]:
    objects = [
        _path("scale", "cut", "Plaquette", [rounded_rect_nodes(0, 0, length, width, radius)]),
        _path("pin1", "holes", "Perçage 1", [circle_nodes(hole_inset, width / 2, 2)]),
        _path("pin2", "holes", "Perçage 2", [circle_nodes(length - hole_inset, width / 2, 2)]),
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


TEMPLATES: list[dict[str, Any]] = [
    {"key": "blank", "name": "Page vierge", "kind": "template", "build": blank_document},
    {"key": "drop-point-blade", "name": "Lame drop-point + soie", "kind": "blade", "build": drop_point_blade},
    {
        "key": "folder-blade",
        "name": "Lame de pliant",
        "kind": "blade",
        "build": lambda: drop_point_blade(blade_len=75, tang_len=35, height=26, tang_width=12),
    },
    {"key": "handle-scale", "name": "Plaquette de manche", "kind": "handle_scale", "build": handle_scale},
    {"key": "oval-guard", "name": "Garde ovale à fente", "kind": "guard", "build": oval_guard},
]


def list_templates() -> list[dict[str, Any]]:
    return [{"key": t["key"], "name": t["name"], "kind": t["kind"], "document": t["build"]()} for t in TEMPLATES]
