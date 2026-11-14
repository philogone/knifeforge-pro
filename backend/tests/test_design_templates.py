"""The editor's starting templates: every blade or scale outline is a clean, simple polygon
with its holes and grind line inside it."""

import pytest
from shapely.geometry import LineString, Polygon

from app.schemas.design import DesignDocument
from app.services import design_templates as tpl
from app.services.geometry_service import DEFAULT_TOLERANCE_MM, extract_parts, flatten_contour


def _blade(document):
    doc = DesignDocument.model_validate(document)
    objects = {o.id: o for o in doc.objects}
    outline = flatten_contour((objects.get("blade") or objects["scale"]).contours[0], True, DEFAULT_TOLERANCE_MM)
    return doc, objects, Polygon(outline)


@pytest.mark.parametrize(
    "build",
    [tpl.full_tang_blade, tpl.folder_blade, lambda: tpl.folder_blade(105, 20, 26, 4, "laguiole"), tpl.folder_handle_scale],
    ids=["full-tang", "folder", "laguiole", "folder-scale"],
)
def test_blade_outline_is_simple_and_holds_its_details(build):
    doc, objects, blade = _blade(build())
    assert blade.is_valid and blade.exterior.is_simple  # no self-crossing, the outline is cut as drawn
    holes = [o for o in doc.objects if o.layer == "holes"]
    assert holes
    for h in holes:
        ring = Polygon(flatten_contour(h.contours[0], True, DEFAULT_TOLERANCE_MM))
        assert blade.buffer(-0.5).contains(ring)  # at least half a millimetre of steel round each hole
    if "grind" in objects:
        grind = LineString(flatten_contour(objects["grind"].contours[0], False, DEFAULT_TOLERANCE_MM))
        assert blade.buffer(1e-6).contains(grind)
    parts = extract_parts(doc)
    assert len(parts) == 1 and len(parts[0].geometry.interiors) == len(holes)


def test_full_tang_blade_dimensions():
    _, _, blade = _blade(tpl.full_tang_blade(blade_len=112, height=32, handle_len=105, handle_h=24))
    minx, miny, maxx, maxy = blade.bounds
    assert maxx == pytest.approx(105 + 112, abs=1e-6)  # the tip
    assert miny == pytest.approx(0, abs=1e-6)  # spine
    assert 32 < maxy < 34.5  # edge at 32, finger guard just below it


def test_templates_listed_are_valid_documents():
    for t in tpl.list_templates():
        DesignDocument.model_validate(t["document"])
