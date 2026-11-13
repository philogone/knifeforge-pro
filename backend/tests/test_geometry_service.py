import math

import pytest

from app.schemas.design import Node
from app.services import design_templates as tpl
from app.services.geometry_service import (
    compute_metrics,
    extract_engraving_lines,
    extract_parts,
    flatten_contour,
    offset_contours,
)
from tests.helpers import circle_obj, doc, rect_obj


def nodes(raw):
    return [Node(**n) for n in raw]


def test_straight_segments_are_not_subdivided():
    pts = flatten_contour(nodes([tpl.node(0, 0), tpl.node(10, 0), tpl.node(10, 10)]), closed=False)
    assert pts == [(0, 0), (10, 0), (10, 10)]


def test_circle_flattens_within_tolerance():
    r = 10
    pts = flatten_contour(nodes(tpl.circle_nodes(0, 0, r)), closed=True, tolerance=0.05)
    # Every flattened vertex is on the true circle (Bézier approximation error ~0.03% of r)
    assert max(abs(math.hypot(x, y) - r) for x, y in pts) < 0.01
    assert len(pts) > 16


def test_part_area_matches_analytic_area():
    metrics = compute_metrics(doc([circle_obj("c", 0, 0, 10, layer="cut")]))
    assert metrics.area_mm2 == pytest.approx(math.pi * 100, rel=0.005)
    assert metrics.part_count == 1
    assert metrics.width_mm == pytest.approx(20, abs=0.05)


def test_hole_layer_is_subtracted_from_cut_parts():
    d = doc([rect_obj("plate", 0, 0, 100, 20), circle_obj("pin", 20, 10, 3)])
    parts = extract_parts(d)
    assert len(parts) == 1
    assert parts[0].area == pytest.approx(2000 - math.pi * 9, rel=0.005)
    metrics = compute_metrics(d)
    assert metrics.width_mm == 100 and metrics.height_mm == 20
    # perimeter includes the hole's circumference
    assert metrics.perimeter_mm == pytest.approx(240 + 2 * math.pi * 3, rel=0.01)


def test_compound_path_uses_even_odd_rule():
    outer = [tpl.node(0, 0), tpl.node(30, 0), tpl.node(30, 30), tpl.node(0, 30)]
    inner = [tpl.node(10, 10), tpl.node(20, 10), tpl.node(20, 20), tpl.node(10, 20)]
    obj = {"id": "ring", "type": "path", "layer": "cut", "name": None, "closed": True, "contours": [outer, inner]}
    assert compute_metrics(doc([obj])).area_mm2 == pytest.approx(900 - 100)


def test_hidden_and_construction_layers_are_ignored():
    d = doc([rect_obj("a", 0, 0, 10, 10), rect_obj("b", 50, 0, 10, 10, layer="construction")])
    assert compute_metrics(d).part_count == 1
    d.layers[0].visible = False
    assert compute_metrics(d).part_count == 0


def test_open_paths_on_cut_layer_do_not_become_parts():
    open_path = {"id": "o", "type": "path", "layer": "cut", "name": None, "closed": False, "contours": [[tpl.node(0, 0), tpl.node(5, 5)]]}
    assert extract_parts(doc([open_path])) == []


def test_engraving_lines_include_open_and_closed_paths():
    open_path = {"id": "o", "type": "path", "layer": "engrave", "name": None, "closed": False, "contours": [[tpl.node(0, 0), tpl.node(5, 5)]]}
    closed = rect_obj("c", 0, 0, 4, 4, layer="engrave")
    lines = extract_engraving_lines(doc([open_path, closed]))
    assert len(lines) == 2
    assert lines[1][0] == lines[1][-1]  # closed path polyline is explicitly closed


def test_offset_grows_square_with_rounded_corners():
    square = nodes([tpl.node(0, 0), tpl.node(10, 0), tpl.node(10, 10), tpl.node(0, 10)])
    out = offset_contours([square], 1.0, "round")
    from shapely.geometry import Polygon

    area = Polygon([(n.x, n.y) for n in out[0]]).area
    assert area == pytest.approx(100 + 4 * 10 + math.pi, rel=0.01)


def test_offset_mitre_keeps_square_corners():
    square = nodes([tpl.node(0, 0), tpl.node(10, 0), tpl.node(10, 10), tpl.node(0, 10)])
    out = offset_contours([square], 1.0, "mitre")
    from shapely.geometry import Polygon

    assert Polygon([(n.x, n.y) for n in out[0]]).area == pytest.approx(144, rel=0.001)


def test_offset_that_collapses_the_shape_raises():
    square = nodes([tpl.node(0, 0), tpl.node(10, 0), tpl.node(10, 10), tpl.node(0, 10)])
    with pytest.raises(ValueError):
        offset_contours([square], -6.0)


def test_templates_are_valid_documents_with_expected_parts():
    from app.schemas.design import DesignDocument

    for template in tpl.list_templates():
        parsed = DesignDocument.model_validate(template["document"])
        if template["key"] == "blank":
            assert compute_metrics(parsed).part_count == 0
        elif template["key"] == "calibration-plate":
            assert compute_metrics(parsed).part_count == 3  # plate, square, disc
        else:
            metrics = compute_metrics(parsed)
            assert metrics.part_count == 1 and metrics.area_mm2 > 100
