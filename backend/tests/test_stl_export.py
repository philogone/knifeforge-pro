import struct
from collections import Counter

import pytest

from app.services.stl_export import design_to_stl
from tests.test_parts_sheet import circle, doc, rect
from app.schemas.design import PathObject


def read_stl(data: bytes):
    (count,) = struct.unpack_from("<I", data, 80)
    assert len(data) == 84 + 50 * count
    tris = []
    for i in range(count):
        v = struct.unpack_from("<12f", data, 84 + 50 * i)
        tris.append((v[3:6], v[6:9], v[9:12]))
    return tris


def volume(tris) -> float:
    """Divergence theorem: positive only if every face points outward."""
    total = 0.0
    for a, b, c in tris:
        total += (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0]) + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6
    return total


def test_plate_with_holes_is_a_closed_solid_of_the_right_volume():
    plate = doc(
        PathObject(id="a", layer="cut", contours=[rect(0, 0, 100, 30)]),
        PathObject(id="h", layer="hole", contours=[circle(20, 15, 2.5)]),
        PathObject(id="h2", layer="hole", contours=[circle(80, 15, 2.5)]),
    )
    tris = read_stl(design_to_stl(plate, thickness_mm=4))
    import math

    # circles flattened at 0.01 mm: area within 0.02 % of π r²
    expected = (100 * 30 - 2 * math.pi * 2.5**2) * 4
    assert volume(tris) == pytest.approx(expected, rel=2e-4)
    # watertight: every edge is shared by exactly two triangles, once in each direction
    edges = Counter()
    for a, b, c in tris:
        for p, q in ((a, b), (b, c), (c, a)):
            edges[(p, q)] += 1
    assert all(edges[(q, p)] == n for (p, q), n in edges.items())


def test_concave_outline_is_followed_exactly():
    # an L shape: a plain Delaunay would bridge the inner corner
    from app.schemas.design import Node

    nodes = [Node(x=0, y=0), Node(x=60, y=0), Node(x=60, y=10), Node(x=10, y=10), Node(x=10, y=50), Node(x=0, y=50)]
    l_shape = doc(PathObject(id="l", layer="cut", contours=[nodes]))
    tris = read_stl(design_to_stl(l_shape, thickness_mm=2))
    assert volume(tris) == pytest.approx((60 * 10 + 10 * 40) * 2, rel=1e-9)


def test_thickness_bounds():
    plate = doc(PathObject(id="a", layer="cut", contours=[rect(0, 0, 10, 10)]))
    with pytest.raises(ValueError):
        design_to_stl(plate, thickness_mm=0)
    with pytest.raises(ValueError):
        design_to_stl(doc(), thickness_mm=3)


def test_stl_endpoint(client):
    from tests.test_designs_api import create_design

    design = create_design(client)
    response = client.get(f"/api/admin/designs/{design['id']}/export.stl?thickness=4")
    assert response.status_code == 200
    assert response.headers["content-type"] == "model/stl"
    assert volume(read_stl(response.content)) > 0
    assert client.get(f"/api/admin/designs/{design['id']}/export.stl?thickness=0").status_code == 422
