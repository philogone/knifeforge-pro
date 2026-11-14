"""Small builders for design documents used across the tests."""

from app.schemas.design import DesignDocument
from app.services import design_templates as tpl


def doc(objects):
    return DesignDocument.model_validate(tpl.document(objects))


def rect_obj(obj_id, x, y, w, h, layer="cut", name=None):
    nodes = [tpl.node(x, y), tpl.node(x + w, y), tpl.node(x + w, y + h), tpl.node(x, y + h)]
    return {"id": obj_id, "type": "path", "layer": layer, "name": name, "closed": True, "contours": [nodes]}


def circle_obj(obj_id, cx, cy, r, layer="holes"):
    return {"id": obj_id, "type": "path", "layer": layer, "name": None, "closed": True, "contours": [tpl.circle_nodes(cx, cy, r)]}


def rect_doc(w, h, name="Rect"):
    return doc([rect_obj("r", 0, 0, w, h, name=name)])


def simple_blade(
    blade_len: float = 112, tang_len: float = 70, height: float = 32, tang_width: float = 16, pin_holes: int = 2
) -> dict:
    """Fixed test fixture: a 182 x 32 mm drop point with a stepped tang (simple, known numbers)."""
    ty = height * 0.2
    t, l, h = tang_len, blade_len, height
    outline = [
        tpl.node(0, ty),
        tpl.node(t - 6, ty),
        tpl.node(t, 0),
        tpl.node(t + l * 0.72, 0, 0, 0, l * 0.17, 0),
        tpl.node(t + l, h * 0.55, -l * 0.08, -h * 0.38, -l * 0.05, h * 0.3),
        tpl.node(t + l * 0.55, h, l * 0.2, 0, 0, 0),
        tpl.node(t, h),
        tpl.node(t - 6, ty + tang_width),
        tpl.node(0, ty + tang_width),
    ]
    objects = [tpl._path("blade", "cut", "Lame", [outline])]
    # grind line: plunge curving up from the edge near the ricasso, then running out at the tip
    grind = [
        tpl.node(t + 3, h),
        tpl.node(t + 10, h * 0.5, -3, h * 0.3, 0, 0),
        tpl.node(t + l * 0.62, h * 0.5),
        tpl.node(t + l, h * 0.55, -l * 0.15, -h * 0.02, 0, 0),
    ]
    objects.append(tpl._path("grind", "grind", "Émouture", [grind], closed=False))
    for i in range(pin_holes):
        cx = t * (0.22 + 0.4 * i / max(1, pin_holes - 1)) if pin_holes > 1 else t * 0.4
        objects.append(tpl._path(f"pin{i + 1}", "holes", f"Perçage {i + 1}", [tpl.circle_nodes(cx, ty + tang_width / 2, 2.5)]))
    objects.append(
        {"id": "dim-blade", "type": "dimension", "layer": "dimensions", "a": [t, h], "b": [t + l, h], "offset": 8, "label": None}
    )
    return tpl.document(objects)
