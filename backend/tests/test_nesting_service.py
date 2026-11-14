import itertools

import pytest

from app.schemas.design import DesignDocument
from app.services import design_templates as tpl
from app.services.geometry_service import extract_parts
from app.services.nesting_service import NestItem, pack
from tests.helpers import rect_doc, simple_blade


def items_for(document: DesignDocument, count: int, design_id: int = 1):
    part = extract_parts(document)[0]
    # one shared geometry object, like the real collector produces
    return [NestItem(design_id, "d", part.name, part.geometry, i + 1) for i in range(count)]


def assert_valid_layout(sheets, sheet_l, sheet_w, spacing, margin):
    for sheet in sheets:
        for a, b in itertools.combinations(sheet.placements, 2):
            assert a.geometry.intersection(b.geometry).area < 1e-6
            assert a.geometry.distance(b.geometry) >= spacing - 1e-6
        for p in sheet.placements:
            x0, y0, x1, y1 = p.geometry.bounds
            assert x0 >= margin - 1e-6 and y0 >= margin - 1e-6
            assert x1 <= sheet_l - margin + 1e-6 and y1 <= sheet_w - margin + 1e-6


def test_rectangles_fit_on_one_sheet_without_overlap():
    sheets, unplaced = pack(items_for(rect_doc(50, 20), 12), 200, 100, spacing=2, margin=3)
    assert unplaced == []
    assert len(sheets) == 1 and len(sheets[0].placements) == 12
    assert_valid_layout(sheets, 200, 100, 2, 3)


def test_overflow_opens_additional_sheets_and_keeps_layouts_valid():
    sheets, unplaced = pack(items_for(rect_doc(50, 20), 25), 200, 100, spacing=2, margin=3)
    assert unplaced == []
    assert sum(len(s.placements) for s in sheets) == 25
    assert 2 <= len(sheets) <= 3
    assert_valid_layout(sheets, 200, 100, 2, 3)


def test_part_larger_than_sheet_is_reported_not_crashed():
    sheets, unplaced = pack(items_for(rect_doc(500, 20), 1), 200, 100, spacing=2, margin=3)
    assert sheets == []
    assert [u.reason for u in unplaced] == ["too_large"]


def test_rotation_is_used_when_needed_and_can_be_forbidden():
    long_part = items_for(rect_doc(90, 10), 1)
    sheets, unplaced = pack(long_part, 20, 100, spacing=1, margin=0)
    assert unplaced == [] and sheets[0].placements[0].rotation_deg in (90.0, 270.0)
    sheets, unplaced = pack(items_for(rect_doc(90, 10), 1), 20, 100, spacing=1, margin=0, rotations=(0.0, 180.0))
    assert sheets == [] and len(unplaced) == 1


def test_real_shapes_with_holes_nest_at_least_as_well_as_a_grid():
    scale = DesignDocument.model_validate(tpl.handle_scale(110, 25))
    sheets, unplaced = pack(items_for(scale, 30), 300, 150, spacing=2, margin=3)
    assert unplaced == []
    naive_per_sheet = int((294 + 2) // 112) * int((144 + 2) // 27)  # 2 x 5
    assert len(sheets[0].placements) >= naive_per_sheet
    assert_valid_layout(sheets, 300, 150, 2, 3)
    # holes are preserved in the placed geometry (interior rings)
    assert all(len(p.geometry.interiors) == 2 for p in sheets[0].placements)


def test_nesting_is_deterministic():
    blade = DesignDocument.model_validate(simple_blade())
    first, _ = pack(items_for(blade, 9), 1000, 100, spacing=2, margin=3)
    second, _ = pack(items_for(blade, 9), 1000, 100, spacing=2, margin=3)
    layout = lambda sheets: [[(p.x, p.y, p.rotation_deg) for p in s.placements] for s in sheets]  # noqa: E731
    assert layout(first) == layout(second)


def test_blades_on_a_narrow_bar_do_not_exceed_bar_bounds():
    blade = DesignDocument.model_validate(simple_blade())
    sheets, unplaced = pack(items_for(blade, 12), 1000, 50, spacing=2, margin=3)
    assert unplaced == []
    assert [len(s.placements) for s in sheets] == [5, 5, 2]
    assert_valid_layout(sheets, 1000, 50, 2, 3)


@pytest.mark.parametrize("spacing", [0, 0.5, 5])
def test_spacing_is_respected(spacing):
    sheets, _ = pack(items_for(rect_doc(30, 30), 6), 120, 80, spacing=spacing, margin=0)
    assert_valid_layout(sheets, 120, 80, max(spacing, 0.02), 0)
