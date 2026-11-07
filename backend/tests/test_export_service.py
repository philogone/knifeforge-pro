import re
import io
import xml.etree.ElementTree as ET

import ezdxf
import pytest

from app.schemas.design import DesignDocument
from app.services import design_templates as tpl
from app.services.export_service import design_to_dxf, design_to_svg, nesting_to_dxf, nesting_to_svg, plan_svg
from app.services.nesting_service import NestingResult, NestItem, pack
from app.services.geometry_service import extract_parts
from tests.helpers import doc


def blade_doc():
    return DesignDocument.model_validate(tpl.drop_point_blade())


def test_design_svg_is_well_formed_and_uses_real_millimetres_and_curves():
    svg = design_to_svg(blade_doc())
    root = ET.fromstring(svg)
    assert root.attrib["width"].endswith("mm") and "viewBox" in root.attrib
    paths = root.findall("{http://www.w3.org/2000/svg}path")
    assert len(paths) == 3  # blade + 2 pin holes
    assert any("C" in p.attrib["d"] for p in paths)  # Bézier curves kept, not flattened


def test_design_svg_rejects_empty_design():
    with pytest.raises(ValueError):
        design_to_svg(doc([]))


def test_design_dxf_has_cut_polylines_for_outline_and_holes_in_mm():
    data = design_to_dxf(blade_doc())
    dxf = ezdxf.read(io.StringIO(data.decode("utf-8")))
    cuts = [e for e in dxf.modelspace() if e.dxftype() == "LWPOLYLINE" and e.dxf.layer == "CUT"]
    assert len(cuts) == 3  # outline + two holes
    assert dxf.header["$INSUNITS"] == 4  # millimetres
    xs = [p[0] for e in cuts for p in e.get_points()]
    assert min(xs) == pytest.approx(0, abs=1e-6) and max(xs) == pytest.approx(182, abs=0.01)
    ys = [p[1] for e in cuts for p in e.get_points()]
    assert min(ys) >= -1e-6  # shifted into the positive quadrant


def test_plan_has_title_block_scale_and_dimensions_and_escapes_text():
    svg = plan_svg(
        blade_doc(), title="Lame <test> & co", customer="A & B <x>", order_ref="CMD-42", knife_model="Bushcraft", material="1095"
    )
    root = ET.fromstring(svg)  # raises if text wasn't escaped
    text = " ".join(t.text or "" for t in root.iter("{http://www.w3.org/2000/svg}text"))
    assert "Lame <test> & co" in text and "A & B <x>" in text and "CMD-42" in text
    assert "1:1" in text  # a 182 x 32 mm blade fits A4 at full size
    assert "182 mm" in text and "32 mm" in text  # overall dimensions
    assert "112 mm" in text  # the template's own user dimension (blade length)


def test_plan_picks_a_reduction_for_big_parts_and_supports_a3():
    from tests.helpers import rect_doc

    svg = plan_svg(rect_doc(600, 100), title="Long", paper="A4")
    assert "1:2.5" in svg or "1:4" in svg or "1:5" in svg
    assert 'width="420mm"' in plan_svg(rect_doc(100, 50), title="x", paper="A3")
    with pytest.raises(ValueError):
        plan_svg(rect_doc(10, 10), title="x", paper="B7")


def _nesting_result():
    part = extract_parts(blade_doc())[0]
    items = [NestItem(1, "Lame", part.name, part.geometry, i + 1) for i in range(7)]
    sheets, unplaced = pack(items, 1000, 50, 2.0, 3.0)
    return NestingResult(1, "Acier", 1000, 50, 2.0, 3.0, 7, sheets, unplaced, 5.0)


def test_nesting_svg_and_dxf_per_sheet():
    result = _nesting_result()
    assert result.sheets_needed == 2 and result.stock_sufficient
    svg = nesting_to_svg(result, 0)
    ET.fromstring(svg)
    assert svg.count("<path") == 5
    dxf = ezdxf.read(io.StringIO(nesting_to_dxf(result, 1).decode("utf-8")))
    layers = {e.dxf.layer for e in dxf.modelspace()}
    assert layers == {"SHEET", "CUT"}
    with pytest.raises(ValueError):
        nesting_to_svg(result, 5)


def test_plan_overall_dimensions_do_not_overlap_user_dimensions():
    # The blade template has a user dimension along its bottom edge (112 mm, offset 8 mm): the overall
    # 182 mm width used to be drawn 7 mm below the part, i.e. on top of it.
    root = ET.fromstring(plan_svg(blade_doc(), title="x"))
    lines = [
        tuple(float(line.attrib[k]) for k in ("x1", "y1", "x2", "y2"))
        for line in root.iter("{http://www.w3.org/2000/svg}line")
        if line.attrib.get("stroke-width") == "0.25"  # dimension lines (extension lines are 0.18)
    ]
    horizontal = sorted(y1 for x1, y1, x2, y2 in lines if abs(y1 - y2) < 1e-6)
    vertical = sorted(x1 for x1, y1, x2, y2 in lines if abs(x1 - x2) < 1e-6)
    assert len(horizontal) == 2  # user 112 mm + overall 182 mm
    for group in (horizontal, vertical):
        for a, b in zip(group, group[1:]):
            assert b - a >= 5.0  # room for the 3.5 mm label between parallel dimension lines


def test_plan_draws_grind_lines_dash_dot_with_a_legend_but_never_cuts_them():
    blade = blade_doc()
    assert any(o.layer == "grind" for o in blade.objects)
    root = ET.fromstring(plan_svg(blade, title="x"))
    grind = [p for p in root.iter("{http://www.w3.org/2000/svg}path") if p.attrib.get("data-layer") == "grind"]
    assert len(grind) == 1 and grind[0].attrib["stroke-dasharray"] and grind[0].attrib["fill"] == "none"
    assert "émouture" in ET.tostring(root, encoding="unicode")
    # cut exports and the part itself ignore it
    assert "grind" not in design_to_svg(blade)
    dxf = ezdxf.read(io.StringIO(design_to_dxf(blade).decode("utf-8")))
    assert {e.dxf.layer for e in dxf.modelspace()} <= {"CUT", "ENGRAVE"}
    without = blade.model_copy(update={"objects": [o for o in blade.objects if o.layer != "grind"]})
    assert [p.area for p in extract_parts(blade)] == [p.area for p in extract_parts(without)]


def test_plan_has_no_grind_legend_without_grind_lines():
    svg = plan_svg(doc([]).model_copy(update={"objects": blade_doc().objects[:1]}), title="x")
    assert "émouture" not in svg and 'data-layer="grind"' not in svg


def test_plan_prints_a_100_mm_scale_check_and_the_workshop_identity():
    svg = plan_svg(
        blade_doc(),
        title="x",
        workshop_name="Atelier Dupont & fils",
        workshop_contact="06 00 00 00 00 · atelier@example.com",
        workshop_logo="data:image/png;base64,iVBORw0KGgo=",
    )
    root = ET.fromstring(svg)
    ns = "{http://www.w3.org/2000/svg}"
    # 1 SVG unit is 1 mm on paper: the page size in mm equals the viewBox
    page_w = float(root.attrib["width"].removesuffix("mm"))
    assert root.attrib["viewBox"].split()[2] == f"{page_w:g}"
    check = next(g for g in root.iter(f"{ns}g") if g.attrib.get("data-role") == "scale-check")
    frame = next(r for r in check.iter(f"{ns}rect") if r.attrib.get("fill") == "none")
    assert float(frame.attrib["width"]) == 100.0
    text = " ".join(t.text or "" for t in root.iter(f"{ns}text"))
    assert "100 mm" in text and "Atelier Dupont & fils" in text and "atelier@example.com" in text
    assert root.find(f"{ns}image") is not None
    assert re.search(r"\d{2}/\d{2}/\d{4}", text)  # date as a French reader writes it


def test_plan_without_workshop_identity_has_no_logo():
    root = ET.fromstring(plan_svg(blade_doc(), title="x"))
    assert root.find("{http://www.w3.org/2000/svg}image") is None
