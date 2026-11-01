import os

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@db:5432/test")
os.environ.setdefault("ADMIN_EMAIL", "admin@example.com")
os.environ.setdefault("ADMIN_PASSWORD_HASH", "$2b$12$abcdefghijklmnopqrstuv")

import pytest  # noqa: E402

from app.models.knife_model import KnifeModel, KnifeModelMaterial, MaterialRole  # noqa: E402
from app.models.material import DimensionType, Material, MaterialCategory  # noqa: E402
from app.models.shop_settings import ShopSettings  # noqa: E402
from app.services.costing_service import (  # noqa: E402
    apply_weighted_average_restock,
    compute_full_costing,
    compute_material_cost,
)


def _material(**overrides):
    defaults = dict(
        name="Test Material",
        category=MaterialCategory.BLADE_STEEL,
        dimension_type=DimensionType.LENGTH,
        kerf_mm=2.0,
        quantity_in_stock=0.0,
        unit_cost=0.0,
    )
    defaults.update(overrides)
    return Material(**defaults)


def test_restock_without_purchase_price_leaves_unit_cost_unchanged():
    material = _material(quantity_in_stock=1000, unit_cost=0.05)
    apply_weighted_average_restock(material, quantity_delta=500, purchase_price=None, shipping_cost=None)
    assert material.quantity_in_stock == 1500
    assert material.unit_cost == 0.05


def test_restock_blends_weighted_average_cost():
    # 1000mm already in stock at 0.05 EUR/mm (value = 50 EUR). Buying
    # 1000mm more for 60 EUR + 5 EUR shipping -> new blended average.
    material = _material(quantity_in_stock=1000, unit_cost=0.05)
    apply_weighted_average_restock(material, quantity_delta=1000, purchase_price=60, shipping_cost=5)
    # (50 + 65) / 2000 = 0.0575
    assert material.quantity_in_stock == 2000
    assert material.unit_cost == pytest.approx(0.0575)


def test_restock_from_empty_stock_sets_cost_directly():
    material = _material(quantity_in_stock=0, unit_cost=0.0)
    apply_weighted_average_restock(material, quantity_delta=1, purchase_price=15, shipping_cost=1)
    assert material.quantity_in_stock == 1
    assert material.unit_cost == pytest.approx(16.0)


def test_restock_rejects_purchase_price_with_non_positive_quantity_delta():
    material = _material(quantity_in_stock=100, unit_cost=1.0)
    with pytest.raises(ValueError):
        apply_weighted_average_restock(material, quantity_delta=-10, purchase_price=5, shipping_cost=0)


def test_restock_rejects_negative_resulting_stock():
    material = _material(quantity_in_stock=10, unit_cost=1.0)
    with pytest.raises(ValueError):
        apply_weighted_average_restock(material, quantity_delta=-20, purchase_price=None, shipping_cost=None)


def test_cost_breakdown_sums_length_area_and_count_lines():
    steel = _material(name="Steel", dimension_type=DimensionType.LENGTH, kerf_mm=2.0, unit_cost=0.05)
    g10 = _material(name="G10", category=MaterialCategory.HANDLE_MATERIAL, dimension_type=DimensionType.AREA, unit_cost=0.001)
    disc = _material(name="Grinding disc", category=MaterialCategory.CONSUMABLE, dimension_type=DimensionType.COUNT, unit_cost=16.0)

    model = KnifeModel(id=1, name="Test Knife")
    model.materials = [
        KnifeModelMaterial(material=steel, material_id=1, role=MaterialRole.BLADE, blank_length_mm=180),
        KnifeModelMaterial(material=g10, material_id=2, role=MaterialRole.HANDLE, blank_length_mm=110, blank_width_mm=25),
        KnifeModelMaterial(material=disc, material_id=3, role=MaterialRole.OTHER, quantity=0.01),
    ]

    breakdown = compute_material_cost(model)

    # steel: (180 + 2) * 0.05 = 9.1
    # g10: (110 * 25) * 0.001 = 2.75
    # disc: 0.01 * 16.0 = 0.16
    assert len(breakdown.lines) == 3
    assert breakdown.lines[0].line_cost == pytest.approx(9.1)
    assert breakdown.lines[1].line_cost == pytest.approx(2.75)
    assert breakdown.lines[2].line_cost == pytest.approx(0.16)
    assert breakdown.total_material_cost == pytest.approx(9.1 + 2.75 + 0.16)


def _simple_knife_model(**overrides):
    steel = _material(name="Steel", dimension_type=DimensionType.LENGTH, kerf_mm=0.0, unit_cost=0.05)
    defaults = dict(id=1, name="Test Knife", base_labor_hours=2.0, sale_price=0.0, margin_percent_override=None)
    defaults.update(overrides)
    model = KnifeModel(**defaults)
    model.materials = [KnifeModelMaterial(material=steel, material_id=1, role=MaterialRole.BLADE, blank_length_mm=100)]
    return model


def test_suggested_price_uses_shop_default_margin():
    model = _simple_knife_model()
    shop = ShopSettings(hourly_rate=20.0, default_margin_percent=50.0)

    result = compute_full_costing(model, shop)

    # material: 100 * 0.05 = 5.0; labor: 2h * 20 EUR/h = 40.0; cost_price = 45.0
    # margin-on-price 50% -> suggested = cost_price / (1 - 0.5) = 90.0
    assert result.total_material_cost == pytest.approx(5.0)
    assert result.labor_cost == pytest.approx(40.0)
    assert result.cost_price == pytest.approx(45.0)
    assert result.margin_percent == pytest.approx(50.0)
    assert result.suggested_sale_price == pytest.approx(90.0)


def test_suggested_price_prefers_per_model_margin_override():
    model = _simple_knife_model(margin_percent_override=20.0)
    shop = ShopSettings(hourly_rate=20.0, default_margin_percent=50.0)

    result = compute_full_costing(model, shop)

    # cost_price = 45.0 as above; margin 20% -> 45 / 0.8 = 56.25
    assert result.margin_percent == pytest.approx(20.0)
    assert result.suggested_sale_price == pytest.approx(56.25)


def test_suggested_price_with_zero_margin_equals_cost_price():
    model = _simple_knife_model(margin_percent_override=0.0)
    shop = ShopSettings(hourly_rate=10.0, default_margin_percent=50.0)

    result = compute_full_costing(model, shop)

    assert result.suggested_sale_price == pytest.approx(result.cost_price)
