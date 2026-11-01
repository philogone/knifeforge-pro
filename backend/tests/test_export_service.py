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
