import io

import pytest
from pypdf import PdfReader
from shapely.geometry import Polygon

from app.schemas.design import DesignDocument
from app.services import calibration
from app.services.calibration import BY_KEY, FEATURES, analyse, plate_document, sheet_pdf
from app.services.export_service import kerf_compensated_rings
from app.services.geometry_service import extract_parts, flatten_contour


def plate():
    return DesignDocument.model_validate(plate_document())


def contour_named(doc, name):
    obj = next(o for o in doc.objects if o.name == name)
    return Polygon(flatten_contour(obj.contours[0], True))


def test_the_drawn_parts_have_their_nominal_dimensions():
    doc = plate()
    x0, y0, x1, y1 = contour_named(doc, "Plaque de contrôle").bounds
    assert (x1 - x0, y1 - y0) == pytest.approx((BY_KEY["A"].nominal_mm, BY_KEY["B"].nominal_mm), abs=1e-9)
    x0, _, x1, _ = contour_named(doc, "Carré 25").bounds
    assert x1 - x0 == pytest.approx(25, abs=1e-9)
    for name, key in (("Disque Ø 30", "D"), ("Perçage Ø 3", "E"), ("Perçage Ø 5", "F"), ("Perçage Ø 10", "G"), ("Perçage Ø 20", "H")):
        x0, _, x1, _ = contour_named(doc, name).bounds
        assert x1 - x0 == pytest.approx(BY_KEY[key].nominal_mm, abs=0.01), name
    _, y0, _, y1 = contour_named(doc, "Fente 30 × 6").bounds
    assert y1 - y0 == pytest.approx(BY_KEY["J"].nominal_mm, abs=1e-9)
    a = contour_named(doc, "Perçage Ø 10").centroid
    b = contour_named(doc, "Perçage Ø 10 (entraxe)").centroid
    assert b.x - a.x == pytest.approx(BY_KEY["K"].nominal_mm, abs=0.005)


def test_three_parts_with_their_holes_and_no_overlap():
    parts = extract_parts(plate())
    assert len(parts) == 3
    plate_part = max(parts, key=lambda p: p.geometry.area)
    assert len(plate_part.geometry.interiors) == 7
    for i, a in enumerate(parts):
        for b in parts[i + 1:]:
            assert a.geometry.distance(b.geometry) >= 5


def test_compensated_export_moves_every_edge_by_half_the_kerf():
    rings = kerf_compensated_rings(plate(), 0.2)
    outer = max((Polygon(r) for r in rings), key=lambda p: p.area)
    x0, y0, x1, y1 = outer.bounds
    assert x1 - x0 == pytest.approx(120.2, abs=0.002)


def simulate(k_used, k_real, scale=1.0):
    """What a caliper reads on a cut made with compensation k_used by a beam removing k_real."""
    out = {}
    for f in FEATURES:
        n = f.nominal_mm * scale
        out[f.key] = n + (k_used - k_real) if f.kind == "outside" else n - (k_used - k_real) if f.kind == "inside" else n
    return out


def test_recovers_the_real_kerf_and_suggests_it():
    result = analyse(0.15, simulate(0.15, 0.27))
    assert result.kerf_estimate_mm == pytest.approx(0.27, abs=1e-9)
    assert result.kerf_spread_mm == pytest.approx(0, abs=1e-9)
    assert result.suggested_kerf_mm == 0.27
    assert result.max_error_mm == pytest.approx(0.12, abs=1e-9)
    assert not result.within_tolerance
    assert result.residual_mm == pytest.approx(0, abs=1e-9)
    assert result.advice == ["use_suggested"]


def test_a_good_cut_is_within_tolerance():
    result = analyse(0.2, simulate(0.2, 0.23))
    assert result.within_tolerance and result.advice == ["ok"]


def test_scale_error_is_reported_from_the_centre_distance():
    m = simulate(0.2, 0.2)
    m["K"] = 80.2
    result = analyse(0.2, m)
    assert result.scale_error_ppm == pytest.approx(2500)
    assert "scale" in result.advice


def test_inconsistent_readings_are_flagged():
    m = simulate(0.2, 0.2)
    m["E"] = 3.5  # a hole drifted: estimates disagree
    result = analyse(0.2, m)
    assert "inconsistent" in result.advice


def test_partial_measurements_and_validation():
    assert analyse(0, {"A": 119.8}).kerf_estimate_mm == pytest.approx(0.2)
    with pytest.raises(ValueError):
        analyse(0, {"Z": 1})
    with pytest.raises(ValueError):
        analyse(0, {"A": -1})
    with pytest.raises(ValueError):
        analyse(5, {"A": 120})


def test_sheet_draws_the_plate_at_true_size():
    pdf = sheet_pdf(0.2, "Laser fibre", "Acier 3 mm", "Atelier test")
    reader = PdfReader(io.BytesIO(pdf))
    assert len(reader.pages) == 1
    text = reader.pages[0].extract_text()
    assert "Planche de contrôle" in text and "Entraxe" in text and "0,20 mm" in text


def test_api(client):
    feats = client.get("/api/admin/calibration/features").json()
    assert [f["key"] for f in feats] == [f.key for f in FEATURES]
    r = client.post("/api/admin/calibration/analyse", json={"kerf_used_mm": 0, "measurements": {"A": 119.7, "E": 3.3}})
    assert r.status_code == 200 and r.json()["suggested_kerf_mm"] == 0.3
    assert client.post("/api/admin/calibration/analyse", json={"kerf_used_mm": 0, "measurements": {"Q": 1}}).status_code == 422
    sheet = client.get("/api/admin/calibration/sheet.pdf?kerf=0.2")
    assert sheet.status_code == 200 and sheet.content.startswith(b"%PDF")
    templates = {t["key"]: t for t in client.get("/api/admin/designs/templates").json()}
    assert "calibration-plate" in templates
