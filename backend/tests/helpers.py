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
