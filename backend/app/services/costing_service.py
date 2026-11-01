"""Material costing: landed unit cost (purchase + shipping, weighted over
time) and the material-only cost rollup for a knife model.

`Material.unit_cost` is defined as the cost of one BASE unit — EUR/mm for
a LENGTH material, EUR/mm^2 for AREA, EUR/unit for COUNT — the same unit
`quantity_in_stock` is already tracked in. That single definition is what
makes both halves of this module trivial: restocking blends a new
purchase into the existing average without any unit conversion, and
costing a knife model is just consumption (already computed by
order_service's own logic, reused here) times unit_cost, summed. No
"cost per bar" vs "cost per mm" bookkeeping to get wrong.
"""

from dataclasses import dataclass, field

from app.models.knife_model import KnifeModel
from app.models.material import DimensionType, Material
from app.models.shop_settings import ShopSettings


def apply_weighted_average_restock(
    material: Material, quantity_delta: float, purchase_price: float | None, shipping_cost: float | None
) -> None:
    """Blends a new purchase into the material's unit_cost using the
    standard weighted-average-cost inventory method, then applies the
    stock change. Mutates `material` in place; caller commits.

    If no purchase_price/shipping_cost is given, this is just a plain
    stock adjustment (a correction, a personal-project deduction, found
    forgotten stock) and unit_cost is left untouched — recomputing an
    average from a non-purchase quantity change would corrupt the cost
    history for no reason.
    """
    new_quantity = material.quantity_in_stock + quantity_delta
    if new_quantity < 0:
        raise ValueError("Resulting stock cannot be negative")

    batch_cost = (purchase_price or 0.0) + (shipping_cost or 0.0)
    if batch_cost > 0:
        if quantity_delta <= 0:
            raise ValueError("purchase_price/shipping_cost require a positive quantity_delta")
        existing_value = max(material.quantity_in_stock, 0.0) * material.unit_cost
        material.unit_cost = round((existing_value + batch_cost) / new_quantity, 6) if new_quantity > 0 else material.unit_cost

    material.quantity_in_stock = new_quantity


@dataclass
class CostLine:
    material_id: int
    material_name: str
    role: str
    consumption: float
    unit: str
    unit_cost: float
    line_cost: float


@dataclass
class CostBreakdown:
    knife_model_id: int
    knife_model_name: str
    lines: list[CostLine] = field(default_factory=list)
    total_material_cost: float = 0.0
    labor_hours: float = 0.0
    hourly_rate: float = 0.0
    labor_cost: float = 0.0
    cost_price: float = 0.0
    margin_percent: float = 0.0
    suggested_sale_price: float = 0.0
    current_sale_price: float = 0.0


_UNIT_BY_DIMENSION = {
    DimensionType.LENGTH: "mm",
    DimensionType.AREA: "mm^2",
    DimensionType.COUNT: "unit",
}


def compute_material_cost(knife_model: KnifeModel) -> CostBreakdown:
    """Material-only cost of building ONE unit of this knife model — no
    labor, no overhead, just raw materials at their current landed cost.
    Every KnifeModelMaterial line contributes, including COUNT lines with
    a fractional quantity (e.g. 0.01 of a grinding disc's life) — that is
    the mechanism for folding tool wear into the cost, see HANDOVER.md."""
    lines: list[CostLine] = []
    for kmm in knife_model.materials:
        material = kmm.material
        if material.dimension_type == DimensionType.LENGTH:
            consumption = (kmm.blank_length_mm or 0.0) + material.kerf_mm
        elif material.dimension_type == DimensionType.AREA:
            consumption = (kmm.blank_length_mm or 0.0) * (kmm.blank_width_mm or 0.0)
        else:
            consumption = kmm.quantity
        line_cost = round(consumption * material.unit_cost, 4)
        lines.append(
            CostLine(
                material_id=material.id,
                material_name=material.name,
                role=kmm.role.value,
                consumption=round(consumption, 4),
                unit=_UNIT_BY_DIMENSION[material.dimension_type],
                unit_cost=material.unit_cost,
                line_cost=line_cost,
            )
        )
    total = round(sum(line.line_cost for line in lines), 4)
    return CostBreakdown(knife_model_id=knife_model.id, knife_model_name=knife_model.name, lines=lines, total_material_cost=total)


def compute_full_costing(knife_model: KnifeModel, shop_settings: ShopSettings) -> CostBreakdown:
    """Extends compute_material_cost() with labor and a suggested sale
    price: cost_price = material_cost + (labor_hours * hourly_rate), then
    suggested_sale_price = cost_price / (1 - margin/100) — the standard
    margin-on-price (not markup-on-cost) formula, so "30% margin" means
    30% of the SALE price is profit, matching how a maker usually thinks
    about margin when pricing a product, not 30% added on top of cost.

    The knife model's own margin_percent_override wins over the shop-wide
    default when set, letting a maker price a folder or a damascus piece
    at a different margin than a simple fixed blade without changing the
    shop default for everything else.
    """
    breakdown = compute_material_cost(knife_model)
    labor_cost = round(knife_model.base_labor_hours * shop_settings.hourly_rate, 4)
    cost_price = round(breakdown.total_material_cost + labor_cost, 4)
    margin = (
        knife_model.margin_percent_override
        if knife_model.margin_percent_override is not None
        else shop_settings.default_margin_percent
    )
    margin_fraction = min(max(margin, 0.0), 99.9) / 100.0
    suggested_price = round(cost_price / (1 - margin_fraction), 2) if margin_fraction < 1 else cost_price

    breakdown.labor_hours = knife_model.base_labor_hours
    breakdown.hourly_rate = shop_settings.hourly_rate
    breakdown.labor_cost = labor_cost
    breakdown.cost_price = cost_price
    breakdown.margin_percent = margin
    breakdown.suggested_sale_price = suggested_price
    breakdown.current_sale_price = knife_model.sale_price
    return breakdown
