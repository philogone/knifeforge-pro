import os

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@db:5432/test")
os.environ.setdefault("ADMIN_EMAIL", "admin@example.com")
os.environ.setdefault("ADMIN_PASSWORD_HASH", "$2b$12$abcdefghijklmnopqrstuv")

import pytest  # noqa: E402

from app.models.material import DimensionType, Material, MaterialCategory  # noqa: E402
from app.services.yield_service import compute_yield  # noqa: E402


def _length_material(**overrides):
    defaults = dict(
        name="Test Bar",
        category=MaterialCategory.BLADE_STEEL,
        dimension_type=DimensionType.LENGTH,
        standard_length_mm=1000,
        kerf_mm=2,
    )
    defaults.update(overrides)
    return Material(**defaults)


def test_length_yield_accounts_for_kerf():
    material = _length_material(standard_length_mm=1000, kerf_mm=2)
    result = compute_yield(material, blank_length_mm=98, blank_width_mm=None, quantity_needed=1)
    # pitch = 98 + 2 = 100mm -> exactly 10 pieces per 1000mm bar, no waste
    assert result.pieces_per_stock_unit == 10
    assert result.waste_per_stock_unit == 0
    assert result.stock_units_needed == 1


def test_length_yield_computes_waste_and_bars_needed():
    material = _length_material(standard_length_mm=1000, kerf_mm=2)
    result = compute_yield(material, blank_length_mm=180, blank_width_mm=None, quantity_needed=12)
    # pitch = 182mm -> floor(1000/182) = 5 pieces per bar, waste = 1000 - 5*182 = 90mm
    assert result.pieces_per_stock_unit == 5
    assert result.waste_per_stock_unit == 90
    assert result.stock_units_needed == 3  # ceil(12/5)


def test_length_yield_rejects_blank_longer_than_bar():
    material = _length_material(standard_length_mm=100, kerf_mm=2)
    with pytest.raises(ValueError):
        compute_yield(material, blank_length_mm=500, blank_width_mm=None, quantity_needed=1)


def test_area_yield_basic():
    material = Material(
        name="Test Sheet",
        category=MaterialCategory.HANDLE_MATERIAL,
        dimension_type=DimensionType.AREA,
        standard_length_mm=300,
        standard_width_mm=150,
    )
    result = compute_yield(material, blank_length_mm=100, blank_width_mm=50, quantity_needed=10)
    # sheet area = 45000mm^2, blank area = 5000mm^2 -> 9 pieces per sheet
    assert result.pieces_per_stock_unit == 9
    assert result.stock_units_needed == 2  # ceil(10/9)


def test_count_yield_is_one_to_one():
    material = Material(
        name="Test Pins",
        category=MaterialCategory.HARDWARE,
        dimension_type=DimensionType.COUNT,
    )
    result = compute_yield(material, blank_length_mm=1, blank_width_mm=None, quantity_needed=7)
    assert result.pieces_per_stock_unit == 1
    assert result.stock_units_needed == 7
    assert result.waste_percentage == 0
