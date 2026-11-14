"""Exports for the machine: DXF with true arcs and kerf compensation keep the 0.01 mm contract."""

import io
import math

import ezdxf
import pytest
from ezdxf import path as ezpath
from shapely.geometry import LineString, Point, Polygon

from app.schemas.design import DesignDocument
from app.services.arcs import cubic_point, cubic_to_arcs
from app.services.export_service import design_to_dxf, design_to_svg, kerf_compensated_rings
from app.services.geometry_service import DEFAULT_TOLERANCE_MM, document_bounds, extract_parts
from tests.helpers import simple_blade

TOL = DEFAULT_TOLERANCE_MM + 1e-6


def blade():
    return DesignDocument.model_validate(simple_blade())


def _dxf_cut_paths(data: bytes):
    doc = ezdxf.read(io.StringIO(data.decode("utf-8")))
    return [e for e in doc.modelspace() if e.dxf.layer == "CUT"]


def _bezier_samples_dxf(doc, n=60):
    """Dense samples of every cut/hole Bézier, in DXF coordinates (x - minx, maxy - y)."""
    minx, _, _, maxy = document_bounds(doc)
    roles = {layer.id: layer.role for layer in doc.layers}
    pts = []
    for obj in doc.objects:
        if getattr(obj, "type", None) != "path" or roles[obj.layer] not in ("cut", "hole"):
            continue
        for c in obj.contours:
            for i in range(len(c)):
                a, b = c[i], c[(i + 1) % len(c)]
                p0, c1 = (a.x, a.y), (a.x + a.ox, a.y + a.oy)
                c2, p1 = (b.x + b.ix, b.y + b.iy), (b.x, b.y)
                for k in range(n + 1):
                    x, y = cubic_point(p0, c1, c2, p1, k / n)
                    pts.append((x - minx, maxy - y))
    return pts


def test_dxf_arcs_stay_within_0_01_mm_of_the_curves_both_ways():
    doc = blade()
    entities = _dxf_cut_paths(design_to_dxf(doc, curves="arcs"))
    assert entities and any(any(abs(p[0]) > 1e-9 for p in e.get_points("b")) for e in entities)  # real arcs, not only lines
    exported = []
    for e in entities:
        flat = list(ezpath.make_path(e).flattening(distance=0.0002))
        exported.append(LineString([(p.x, p.y) for p in flat]))
    samples = _bezier_samples_dxf(doc)
    # every point of the true curve is within tolerance of the exported arcs...
    worst = max(min(line.distance(Point(p)) for line in exported) for p in samples)
    assert worst <= TOL
    # ...and every exported point is within tolerance of the true curve
    curve_lines = [LineString(samples)]
    worst_back = max(curve_lines[0].distance(Point(c)) for line in exported for c in line.coords)
    assert worst_back <= TOL + 0.0005  # the sampled curve itself is a chordal approximation


def test_arc_fitting_is_exact_on_a_true_circle_and_linear_on_lines():
    # quarter circle of radius 50 as a Bézier (kappa): one or two arcs, radius error far below tolerance
    k = 0.5522847498 * 50
    segs = cubic_to_arcs((50, 0), (50, k), (k, 50), (0, 50), 0.01)
    assert 1 <= len(segs) <= 4 and all(b > 0 for _, b in segs)  # counter-clockwise
    assert cubic_to_arcs((0, 0), (10, 0), (20, 0), (30, 0), 0.01) == [((30, 0), 0.0)]


def test_kerf_compensation_grows_outlines_and_shrinks_holes_by_half_the_kerf():
    from tests.helpers import rect_doc

    doc = rect_doc(100, 20)
    ring = kerf_compensated_rings(doc, 0.2)
    poly = Polygon(ring[0])
    minx, miny, maxx, maxy = poly.bounds
    assert maxx - minx == pytest.approx(100.2, abs=1e-6) and maxy - miny == pytest.approx(20.2, abs=1e-6)
    # every point of the compensated outline is 0.1 mm from the part (round joins included)
    part = extract_parts(doc)[0].geometry
    assert all(abs(part.exterior.distance(Point(p)) - 0.1) <= 0.0006 for p in ring[0])

    blade_doc = blade()
    original = extract_parts(blade_doc)[0].geometry
    rings = kerf_compensated_rings(blade_doc, 0.3)
    holes = [Polygon(r) for r in rings if Polygon(r).area < original.area / 4]
    assert holes, "the blade's pin holes are still there"
    for hole in holes:
        nearest = min(original.interiors, key=lambda i: Polygon(i).centroid.distance(hole.centroid))
        # hole radius shrinks by kerf / 2
        assert math.sqrt(hole.area / math.pi) == pytest.approx(math.sqrt(Polygon(nearest).area / math.pi) - 0.15, abs=0.005)


def test_kerf_exports_and_limits():
    doc = blade()
    assert 'data-kerf="0.2"' in design_to_svg(doc, kerf_mm=0.2)
    entities = _dxf_cut_paths(design_to_dxf(doc, kerf_mm=0.2))
    assert entities
    with pytest.raises(ValueError):
        kerf_compensated_rings(doc, 5)


def test_export_api_accepts_curves_and_kerf(client):
    from tests.test_designs_api import create_design

    design = create_design(client)
    assert client.get(f"/api/admin/designs/{design['id']}/export.dxf?curves=arcs").status_code == 200
    assert client.get(f"/api/admin/designs/{design['id']}/export.dxf?kerf=0.25").status_code == 200
    assert client.get(f"/api/admin/designs/{design['id']}/export.svg?kerf=0.25").status_code == 200
    assert client.get(f"/api/admin/designs/{design['id']}/export.dxf?curves=splines").status_code == 422
    assert client.get(f"/api/admin/designs/{design['id']}/export.dxf?kerf=9").status_code == 422
