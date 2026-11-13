"""3D mock-up: plates stacked to the hundredth, pins through the holes, closed solids, 3MF and
CNC outputs."""

import io
import math
import zipfile
from collections import Counter
from xml.etree import ElementTree as ET

import pytest

from app.schemas.design import DesignDocument, Layer, Node, PathObject
from app.services.mockup_3d import MockupError, PartSpec, assemble, solid_triangles, to_3mf, to_cnc_zip, to_stl_zip, tool_check
from tests.test_parts_sheet import circle, rect
from tests.test_stl_export import read_stl, volume

NS = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}


def knife():
    """A 160 × 30 blade with a 100 mm tang, one 100 × 30 scale outline over the tang, a guard,
    two Ø 5 pin holes through tang and scales."""
    return DesignDocument(
        layers=[Layer(id="cut", name="Découpe", role="cut"), Layer(id="hole", name="Perçages", role="hole")],
        objects=[
            PathObject(id="blade", layer="cut", name="Lame", contours=[rect(0, 0, 260, 30)]),
            PathObject(id="scale", layer="cut", name="Plaquette", contours=[rect(0, 0, 100, 30)]),
            PathObject(id="guard", layer="cut", name="Garde", contours=[rect(100, -5, 8, 40)]),
            PathObject(id="p1", layer="hole", name="1", contours=[circle(25, 15, 2.5)]),
            PathObject(id="p2", layer="hole", name="2", contours=[circle(75, 15, 2.5)]),
        ],
    )


SPECS = [PartSpec("blade", "blade", 4), PartSpec("scale", "scales", 8), PartSpec("guard", "guard", 12)]


def test_plates_are_stacked_from_the_blade_faces():
    asm = assemble(knife(), SPECS)
    z = {s.name: (s.z0, s.z1) for s in asm.solids}
    assert z["Lame"] == (-2, 2)
    assert z["Plaquette (gauche)"] == (2, 10)
    assert z["Plaquette (droite)"] == (-10, -2)
    assert z["Garde"] == (-6, 6)


def test_pins_go_through_the_whole_stack_at_the_hole_centres():
    asm = assemble(knife(), SPECS, pin_clearance_mm=0.2)
    assert len(asm.pins) == 2
    for pin, cx in zip(asm.pins, (25, 75)):
        assert (pin.z0, pin.z1) == (-10, 10)
        c = pin.polygons[0].centroid
        assert c.x == pytest.approx(cx, abs=1e-6) and c.y == pytest.approx(15, abs=1e-6)
        minx, _, maxx, _ = pin.polygons[0].bounds
        assert maxx - minx == pytest.approx(4.8, abs=0.01)  # Ø 5 less the 0.2 mm clearance


def test_every_solid_is_closed_with_the_exact_volume():
    asm = assemble(knife(), SPECS)
    blade = next(s for s in asm.solids if s.name == "Lame")
    tris = solid_triangles(blade)
    hole = math.pi * 2.5**2
    assert volume(tris) == pytest.approx((260 * 30 - 2 * hole) * 4, rel=2e-4)
    edges = Counter()
    for a, b, c in tris:
        for p, q in ((a, b), (b, c), (c, a)):
            edges[(p, q)] += 1
    assert all(edges[(q, p)] == n for (p, q), n in edges.items())


def test_3mf_holds_one_object_per_piece_in_millimetres():
    data = to_3mf(assemble(knife(), SPECS), layout="assembled")
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        assert {"[Content_Types].xml", "_rels/.rels", "3D/3dmodel.model"} <= set(z.namelist())
        root = ET.fromstring(z.read("3D/3dmodel.model"))
    assert root.get("unit") == "millimeter"
    objects = root.findall(".//m:object", NS)
    # blade, 2 scales, guard, 2 pins
    assert len(objects) == 6
    assert len(root.findall(".//m:build/m:item", NS)) == 6
    zs = [float(v.get("z")) for v in root.findall(".//m:vertex", NS)]
    assert min(zs) == pytest.approx(-10) and max(zs) == pytest.approx(10)


def test_flat_layout_puts_every_piece_on_the_plate():
    data = to_3mf(assemble(knife(), SPECS), layout="flat")
    root = ET.fromstring(zipfile.ZipFile(io.BytesIO(data)).read("3D/3dmodel.model"))
    for obj in root.findall(".//m:object", NS):
        zs = [float(v.get("z")) for v in obj.findall(".//m:vertex", NS)]
        assert min(zs) == pytest.approx(0)


def test_stl_zip_one_file_per_piece():
    names = zipfile.ZipFile(io.BytesIO(to_stl_zip(assemble(knife(), SPECS)))).namelist()
    assert len(names) == 6 and names[0].endswith("_4mm.stl")
    data = zipfile.ZipFile(io.BytesIO(to_stl_zip(assemble(knife(), SPECS)))).read(names[1])
    assert volume(read_stl(data)) > 0


def test_tool_check_finds_tight_corners_and_small_holes():
    # an L-shaped plate: one 90° inside corner, a Ø 3 hole, a 10 × 10 square window
    doc = DesignDocument(
        layers=[Layer(id="cut", name="Découpe", role="cut"), Layer(id="hole", name="Perçages", role="hole")],
        objects=[
            PathObject(id="l", layer="cut", name="Plaque", contours=[[Node(x=0, y=0), Node(x=60, y=0), Node(x=60, y=20), Node(x=20, y=20), Node(x=20, y=50), Node(x=0, y=50)]]),
            PathObject(id="h", layer="hole", name="h", contours=[circle(10, 10, 1.5)]),
            PathObject(id="w", layer="hole", name="w", contours=[rect(35, 3, 10, 10)]),
        ],
    )
    asm = assemble(doc, [PartSpec("l", "blade", 6)])
    issues = tool_check(asm, 6)
    kinds = Counter(i.kind for i in issues)
    assert kinds == {"corner": 1, "hole_too_small": 1, "hole_corner": 4}
    corner = next(i for i in issues if i.kind == "corner")
    # a Ø 6 cutter leaves a fillet of radius 3 in a 90° corner: at most r (1 − 1/√2) = 0.88 mm
    # thick, measured square to the outline
    assert corner.size_mm == pytest.approx(3 * (1 - 1 / math.sqrt(2)), abs=0.01)
    assert corner.x == pytest.approx(21, abs=1.5) and corner.y == pytest.approx(21, abs=1.5)  # in the corner at (20, 20)
    assert not tool_check(asm, 0.5)[:1] or all(i.kind != "hole_too_small" for i in tool_check(asm, 0.5))


def test_cnc_zip_one_dxf_per_plate_and_a_report():
    data = to_cnc_zip(knife(), assemble(knife(), SPECS), SPECS, tool_diameter_mm=3)
    z = zipfile.ZipFile(io.BytesIO(data))
    dxfs = sorted(n for n in z.namelist() if n.endswith(".dxf"))
    assert dxfs == ["01_lame_ep4mm.dxf", "02_plaquette_ep8mm.dxf", "03_garde_ep12mm.dxf"]
    report = z.read("LISEZMOI.txt").decode("utf-8")
    assert "2 pièce(s)" in report and "Goupille" in report and "Ø 5.00 mm" in report


def test_validation():
    with pytest.raises(MockupError):
        assemble(knife(), [])
    with pytest.raises(MockupError):
        assemble(knife(), [PartSpec("nope", "blade", 4)])
    with pytest.raises(MockupError):
        assemble(knife(), [PartSpec("blade", "blade", 0)])


def test_mockup_api(client):
    from tests.test_designs_api import create_design

    doc = knife().model_dump(mode="json")
    design = create_design(client, document=doc)
    parts = client.get(f"/api/admin/designs/{design['id']}/mockup/parts").json()
    roles = {p["name"]: p["role"] for p in parts}
    assert roles == {"Lame": "blade", "Plaquette": "scales", "Garde": "guard"}
    body = {"parts": [{"object_id": p["object_id"], "role": p["role"], "thickness_mm": p["thickness_mm"]} for p in parts]}
    preview = client.post(f"/api/admin/designs/{design['id']}/mockup/preview", json=body).json()
    assert len(preview["meshes"]) == 6 and preview["stack_mm"] == pytest.approx(4 + 2 * 8)
    r = client.post(f"/api/admin/designs/{design['id']}/mockup", json={**body, "output": "3mf"})
    assert r.status_code == 200 and r.headers["content-type"] == "model/3mf" and r.content[:2] == b"PK"
    r = client.post(f"/api/admin/designs/{design['id']}/mockup", json={**body, "output": "cnc", "tool_diameter_mm": 6})
    assert r.status_code == 200 and "usinage-cnc" in r.headers["content-disposition"]
    cnc = client.post(f"/api/admin/designs/{design['id']}/mockup/preview", json={**body, "output": "cnc", "tool_diameter_mm": 6}).json()
    assert {i["kind"] for i in cnc["issues"]} == {"hole_too_small"}  # Ø 5 holes, Ø 6 cutter
    bad = client.post(f"/api/admin/designs/{design['id']}/mockup", json={"parts": [{"object_id": "zz", "role": "blade", "thickness_mm": 4}]})
    assert bad.status_code == 422


def test_round_holes_wider_than_the_cutter_raise_nothing():
    doc = DesignDocument(
        layers=[Layer(id="cut", name="Découpe", role="cut"), Layer(id="hole", name="Perçages", role="hole")],
        objects=[
            PathObject(id="p", layer="cut", name="Plaque", contours=[rect(0, 0, 60, 30)]),
            PathObject(id="h", layer="hole", name="h", contours=[circle(30, 15, 5)]),
        ],
    )
    assert tool_check(assemble(doc, [PartSpec("p", "blade", 4)]), 3) == []


def test_the_guard_is_slotted_for_the_tang():
    asm = assemble(knife(), SPECS, pin_clearance_mm=0.2)
    guard = next(s for s in asm.solids if s.name == "Garde")
    assert [(round(a, 3), round(b, 3)) for _, a, b in guard.slabs] == [(-6, -2.1), (-2.1, 2.1), (2.1, 6)]
    # the slot is the blade's section through the guard (30 mm high, 8 mm long), plus the clearance
    full = 8 * 40 * 12
    slot = (30 + 0.2) * 8 * 4.2
    assert volume(solid_triangles(guard)) == pytest.approx(full - slot, rel=1e-3)
    # laid flat, the slotted guard still sits on z = 0
    assert min(v[2] for t in solid_triangles(guard, flat=True) for v in t) == pytest.approx(0)
