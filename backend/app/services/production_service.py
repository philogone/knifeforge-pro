"""Backlog analysis: compare all draft orders against current stock so a
maker can see, at a glance, which orders are buildable right now, which
are short, and where the material crunch is overall — a starting point for
deciding which orders to prioritize when stock is tight.

Each order's "feasible" flag is computed independently (as if it were the
only order being confirmed) — it does NOT account for two draft orders
competing for the same limited stock. If two feasible orders both need the
last bar of a steel, confirming one will make the other infeasible; this
view doesn't pre-resolve that contention, it surfaces the raw numbers so
the maker can decide the priority themselves.
"""

from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.material import Material
from app.models.order import Order, OrderStatus
from app.services.order_service import (
    _UNIT_BY_DIMENSION,
    check_feasibility,
    compute_material_requirements,
    load_order_with_relations,
)


@dataclass
class MaterialDemand:
    material_id: int
    material_name: str
    unit: str
    available: float
    demand: float
    shortfall: float


@dataclass
class OrderSummary:
    order_id: int
    customer_name: str
    feasible: bool
    lines: list[str] = field(default_factory=list)


@dataclass
class ProductionOverview:
    materials: list[MaterialDemand]
    orders: list[OrderSummary]


def build_overview(db: Session) -> ProductionOverview:
    draft_orders = db.query(Order).filter(Order.status == OrderStatus.DRAFT).order_by(Order.created_at).all()
    full_orders = [load_order_with_relations(db, o.id) for o in draft_orders]

    total_demand: dict[int, float] = defaultdict(float)
    order_summaries: list[OrderSummary] = []

    for order in full_orders:
        for material_id, amount in compute_material_requirements(order).items():
            total_demand[material_id] += amount
        result = check_feasibility(db, order) if order.lines else None
        order_summaries.append(
            OrderSummary(
                order_id=order.id,
                customer_name=order.customer_name,
                feasible=result.feasible if result else True,
                lines=[f"{line.quantity}x {line.knife_model.name}" for line in order.lines],
            )
        )

    materials_by_id = {m.id: m for m in db.query(Material).filter(Material.id.in_(total_demand.keys())).all()}

    material_demands = [
        MaterialDemand(
            material_id=material_id,
            material_name=materials_by_id[material_id].name,
            unit=_UNIT_BY_DIMENSION[materials_by_id[material_id].dimension_type],
            available=round(materials_by_id[material_id].quantity_in_stock, 2),
            demand=round(demand, 2),
            shortfall=round(max(0.0, demand - materials_by_id[material_id].quantity_in_stock), 2),
        )
        for material_id, demand in total_demand.items()
    ]
    material_demands.sort(key=lambda m: m.shortfall, reverse=True)

    return ProductionOverview(materials=material_demands, orders=order_summaries)
