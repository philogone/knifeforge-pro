import io
import math
import re

import pytest
from pypdf import PdfReader

from app.schemas.design import DesignDocument, Layer, Node, PathObject
from app.services.parts_sheet import PT_PER_MM, PartsSheetError, _layout, hole_centres, parts_sheet_pdf

K = 0.5522847498  # cubic Bézier circle constant


def rect(x, y, w, h):
    return [Node(x=x, y=y), Node(x=x + w, y=y), Node(x=x + w, y=y + h), Node(x=x, y=y + h)]


def circle(cx, cy, r):
    k = K * r
    return [
        Node(x=cx + r, y=cy, ix=0, iy=-k, ox=0, oy=k),
        Node(x=cx, y=cy + r, ix=k, iy=0, ox=-k, oy=0),
        Node(x=cx - r, y=cy, ix=0, iy=k, ox=0, oy=-k),
        Node(x=cx, y=cy - r, ix=-k, iy=0, ox=k, oy=0),
    ]


def doc(*objects):
    return DesignDocument(
        layers=[Layer(id="cut", name="Découpe", role="cut"), Layer(id="hole", name="Perçages", role="hole")],
        objects=list(objects),
    )


def pages(pdf: bytes):
    return PdfReader(io.BytesIO(pdf)).pages


def test_true_size_square_measures_100_mm_in_the_pdf():
    pdf = parts_sheet_pdf(doc(PathObject(id="a", layer="cut", contours=[rect(0, 0, 100, 100)])), "Carré étalon")
    (page,) = pages(pdf)
    stream = page.get_contents().get_data().decode("latin-1")
    # the square is drawn as moveTo + 3 lineTo: consecutive corners 100 mm = 283.4646 pt apart
    numbers = r"(-?\d+(?:\.\d+)?)"
    corners = [tuple(map(float, m)) for m in re.findall(rf"{numbers} {numbers} [ml]\b", stream)]
    sides = {round(math.dist(a, b), 3) for a in corners for b in corners if a != b}
    assert round(100 * PT_PER_MM, 3) in sides


def test_holes_get_a_punch_mark_at_their_centre():
    d = doc(
        PathObject(id="a", layer="cut", contours=[rect(0, 0, 120, 30)]),
        PathObject(id="h1", layer="hole", contours=[circle(20, 15, 2)]),
        PathObject(id="h2", layer="hole", contours=[circle(95.5, 15, 2.38)]),
    )
    centres = hole_centres(d)
    assert [(round(x, 4), round(y, 4)) for x, y in centres] == [(20, 15), (95.5, 15)]
    assert len(pages(parts_sheet_pdf(d, "Plaquette"))) == 1


def test_long_blade_is_tiled_with_overlap():
    blade = doc(PathObject(id="a", layer="cut", contours=[rect(0, 0, 500, 60)]))
    page_w, page_h, cols, rows = _layout(506, 66, "A4")
    assert (page_w, page_h) == (297.0, 210.0)  # landscape takes fewer pages
    assert (cols, rows) == (2, 1)
    pdf = parts_sheet_pdf(blade, "Sabre")
    assert len(pages(pdf)) == 2
    assert len(pages(parts_sheet_pdf(blade, "Sabre", paper="A3"))) == 2  # 506 mm > 400 mm usable on A3 too


def test_refuses_empty_and_absurd_designs():
    with pytest.raises(PartsSheetError):
        parts_sheet_pdf(doc(), "Vide")
    with pytest.raises(PartsSheetError):
        parts_sheet_pdf(doc(PathObject(id="a", layer="cut", contours=[rect(0, 0, 5000, 5000)])), "Hangar")


def test_parts_sheet_endpoint(client):
    from tests.test_designs_api import create_design

    design = create_design(client)
    response = client.get(f"/api/admin/designs/{design['id']}/parts.pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
