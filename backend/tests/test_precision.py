"""Metrology tests: every figure the tool produces must be right to well
below 0.1 mm. These compare against closed-form geometry, not against
snapshots of previous output."""

import io
import itertools
import math
import re
import xml.etree.ElementTree as ET

import ezdxf
import pytest

from app.schemas.design import DesignDocument, Node
from app.services import design_templates as tpl
from app.services.export_service import design_to_dxf, design_to_svg, nesting_to_dxf, plan_svg
from app.services.geometry_service import (
    DEFAULT_TOLERANCE_MM,
    compute_metrics,
    extract_parts,
    flatten_contour,
    offset_contours,
)
from app.services.nesting_service import NestItem, pack
from tests.helpers import circle_obj, doc, rect_obj, simple_blade

KAPPA_RADIAL_ERROR = 0.000273  # max relative radius error of the 4-arc Bézier circle


def circle_doc(r):
    return doc([circle_obj("c", 0, 0, r, layer="cut")])


@pytest.mark.parametrize("r", [3.0, 12.3, 25.0, 60.0])
def test_circle_area_and_perimeter_match_closed_form(r):
    m = compute_metrics(circle_doc(r))
    # flattening error (0.01 mm) + Bézier circle error (0.027 %) bound the deviation
    assert m.width_mm == pytest.approx(2 * r, abs=0.05)
    # inscribed polygon: area deficit <= perimeter * tolerance, perimeter deficit is far smaller
    assert abs(m.area_mm2 - math.pi * r * r) <= 2 * math.pi * r * DEFAULT_TOLERANCE_MM
    assert abs(m.perimeter_mm - 2 * math.pi * r) <= 0.02 + 2 * math.pi * r * KAPPA_RADIAL_ERROR


def test_flattened_curve_stays_within_tolerance_of_true_bezier():
    nodes = [Node(**n) for n in tpl.circle_nodes(0, 0, 40.0)]
    pts = flatten_contour(nodes, True, DEFAULT_TOLERANCE_MM)
    # the exact Bézier circle has radial error <= 0.0273 % of r; flattening adds <= tolerance
    worst = max(abs(math.hypot(x, y) - 40.0) for x, y in pts)
    assert worst <= 40.0 * KAPPA_RADIAL_ERROR + 1e-9
    # chords are inscribed: no vertex-to-vertex chord sags more than the tolerance
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        mid = math.hypot((x0 + x1) / 2, (y0 + y1) / 2)
        assert 40.0 - mid <= DEFAULT_TOLERANCE_MM + 40.0 * KAPPA_RADIAL_ERROR


def test_rectangle_dimensions_are_exact_to_the_micron():
    m = compute_metrics(doc([rect_obj("r", 10.1, 20.2, 123.4, 17.6)]))
    assert (m.width_mm, m.height_mm) == (123.4, 17.6)
    assert m.area_mm2 == pytest.approx(123.4 * 17.6, abs=0.01)
    assert m.perimeter_mm == pytest.approx(2 * (123.4 + 17.6), abs=0.01)


def test_holes_are_subtracted_exactly():
    d = doc([rect_obj("r", 0, 0, 100, 40), circle_obj("h", 50, 20, 5.0)])
    m = compute_metrics(d)
    assert m.area_mm2 == pytest.approx(100 * 40 - math.pi * 25, rel=5e-4)


@pytest.mark.parametrize("dist", [-3.0, 0.25, 2.5])
def test_offset_distance_is_exact(dist):
    nodes = [Node(**n) for n in tpl.rounded_rect_nodes(0, 0, 80, 30, 6)]
    out = offset_contours([nodes], dist)
    width = max(n.x for n in out[0]) - min(n.x for n in out[0])
    height = max(n.y for n in out[0]) - min(n.y for n in out[0])
    assert width == pytest.approx(80 + 2 * dist, abs=0.01)
    assert height == pytest.approx(30 + 2 * dist, abs=0.01)


def test_svg_export_keeps_exact_coordinates_and_size():
    svg = design_to_svg(doc([rect_obj("r", 12.3456, 7.891, 100.25, 20.5, layer="cut")]), margin_mm=0)
    root = ET.fromstring(svg)
    path = root.find("{http://www.w3.org/2000/svg}path")
    nums = [float(v) for v in re.findall(r"-?\d+\.?\d*", path.attrib["d"])]
    xs, ys = nums[0::2], nums[1::2]
    assert max(xs) - min(xs) == pytest.approx(100.25, abs=0.001)
    assert max(ys) - min(ys) == pytest.approx(20.5, abs=0.001)
    assert float(root.attrib["width"].removesuffix("mm")) == pytest.approx(100.25, abs=0.001)


def test_dxf_export_size_and_curve_fidelity():
    data = design_to_dxf(circle_doc(30.0))
    dxf = ezdxf.read(io.StringIO(data.decode("utf-8")))
    poly = next(e for e in dxf.modelspace() if e.dxftype() == "LWPOLYLINE")
    pts = [(p[0], p[1]) for p in poly.get_points()]
    xs = [p[0] for p in pts]
    assert max(xs) - min(xs) == pytest.approx(60.0, abs=0.02)
    cx = (max(xs) + min(xs)) / 2
    cy = (max(p[1] for p in pts) + min(p[1] for p in pts)) / 2
    assert max(abs(math.hypot(x - cx, y - cy) - 30.0) for x, y in pts) < 0.02


def test_plan_overall_dimensions_are_the_real_ones():
    svg = plan_svg(doc([rect_obj("r", 0, 0, 123.4, 17.6, layer="cut")]), title="t")
    assert "123.4" in svg and "17.6" in svg


@pytest.mark.parametrize("spacing,margin", [(0.5, 0), (2, 3), (4.7, 1.3)])
def test_nesting_spacing_and_margin_are_hard_minimums_for_curved_parts(spacing, margin):
    blade = DesignDocument.model_validate(simple_blade())
    part = extract_parts(blade)[0]
    scale = DesignDocument.model_validate(tpl.handle_scale())
    sp = extract_parts(scale)[0]
    items = [NestItem(1, "b", part.name, part.geometry, i + 1) for i in range(4)] + [
        NestItem(2, "s", sp.name, sp.geometry, i + 1) for i in range(6)
    ]
    sheets, unplaced = pack(items, 400, 120, spacing=spacing, margin=margin)
    assert not unplaced
    for sheet in sheets:
        for a, b in itertools.combinations(sheet.placements, 2):
            # exact distance between the flattened outlines (0.01 mm chord error)
            assert a.geometry.distance(b.geometry) >= spacing - 1e-6
        for p in sheet.placements:
            x0, y0, x1, y1 = p.geometry.bounds
            assert x0 >= margin - 1e-6 and y0 >= margin - 1e-6
            assert x1 <= 400 - margin + 1e-6 and y1 <= 120 - margin + 1e-6


def test_nesting_dxf_places_parts_at_the_planned_coordinates():
    from app.services.nesting_service import NestingResult  # noqa: F401  (type only)
    from types import SimpleNamespace

    d = doc([rect_obj("r", 0, 0, 50, 20, layer="cut")])
    part = extract_parts(d)[0]
    items = [NestItem(1, "d", part.name, part.geometry, i + 1) for i in range(3)]
    sheets, _ = pack(items, 200, 100, spacing=2, margin=3)
    result = SimpleNamespace(sheet_length_mm=200.0, sheet_width_mm=100.0, sheets=[SimpleNamespace(placements=sheets[0].placements)])
    dxf = ezdxf.read(io.StringIO(nesting_to_dxf(result, 0).decode("utf-8")))
    cuts = [e for e in dxf.modelspace() if e.dxftype() == "LWPOLYLINE" and e.dxf.layer == "CUT"]
    got = sorted((round(min(p[0] for p in e.get_points()), 4), round(100 - max(p[1] for p in e.get_points()), 4)) for e in cuts)
    want = sorted((round(p.geometry.bounds[0], 4), round(p.geometry.bounds[1], 4)) for p in sheets[0].placements)
    assert got == want
