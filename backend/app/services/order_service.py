"""Order feasibility and stock deduction — the ERP core. Confirming an
order is all-or-nothing: either every material line has enough stock and
everything gets deducted together, or nothing is deducted and the order
stays in DRAFT. Cancelling a CONFIRMED order restocks what it consumed,
since the deduction was a reservation of real material for a build that
is no longer happening.
"""

from collections import defaultdict

from sqlalchemy.orm import Session, joinedload

from app.models.knife_model import KnifeModel, KnifeModelMaterial
from app.models.material import DimensionType, Material
from app.models.order import Order, OrderLine, OrderStatus
from app.schemas.order import FeasibilityResult, MaterialFeasibility

_UNIT_BY_DIMENSION = {
    DimensionType.LENGTH: "mm",
    DimensionType.AREA: "mm^2",
    DimensionType.COUNT: "unit",
}


def compute_material_requirements(order: Order) -> dict[int, float]:
    requirements: dict[int, float] = defaultdict(float)
    for line in order.lines:
        knife_model = line.knife_model
        for kmm in knife_model.materials:
            material: Material = kmm.material
            if material.dimension_type == DimensionType.LENGTH:
                amount = (kmm.blank_length_mm + material.kerf_mm) * line.quantity
            elif material.dimension_type == DimensionType.AREA:
                amount = (kmm.blank_length_mm * kmm.blank_width_mm) * line.quantity
            else:
                amount = kmm.quantity * line.quantity
            requirements[material.id] += amount
    return dict(requirements)


def check_feasibility(db: Session, order: Order) -> FeasibilityResult:
    requirements = compute_material_requirements(order)
    materials_by_id = {
        m.id: m for m in db.query(Material).filter(Material.id.in_(requirements.keys())).all()
    }
    results = []
    for material_id, required in requirements.items():
        material = materials_by_id[material_id]
        available = material.quantity_in_stock
        sufficient = available >= required
        results.append(
            MaterialFeasibility(
                material_id=material.id,
                material_name=material.name,
                unit=_UNIT_BY_DIMENSION[material.dimension_type],
                required=round(required, 2),
                available=round(available, 2),
                sufficient=sufficient,
                shortfall=round(max(0.0, required - available), 2),
            )
        )
    return FeasibilityResult(feasible=all(r.sufficient for r in results), materials=results)


class OrderConfirmError(Exception):
    def __init__(self, result: FeasibilityResult):
        self.result = result
        super().__init__("Order is not feasible with current stock")


def confirm_order(db: Session, order: Order) -> Order:
    if order.status != OrderStatus.DRAFT:
        raise ValueError("Only draft orders can be confirmed")

    result = check_feasibility(db, order)
    if not result.feasible:
        raise OrderConfirmError(result)

    requirements = compute_material_requirements(order)
    materials_by_id = {
        m.id: m for m in db.query(Material).filter(Material.id.in_(requirements.keys())).all()
    }
    for material_id, amount in requirements.items():
        materials_by_id[material_id].quantity_in_stock -= amount

    order.status = OrderStatus.CONFIRMED
    db.commit()
    db.refresh(order)
    return order


def cancel_order(db: Session, order: Order) -> Order:
    if order.status not in (OrderStatus.DRAFT, OrderStatus.CONFIRMED):
        raise ValueError("Only draft or confirmed orders can be cancelled")

    if order.status == OrderStatus.CONFIRMED:
        requirements = compute_material_requirements(order)
        materials_by_id = {
            m.id: m for m in db.query(Material).filter(Material.id.in_(requirements.keys())).all()
        }
        for material_id, amount in requirements.items():
            materials_by_id[material_id].quantity_in_stock += amount

    order.status = OrderStatus.CANCELLED
    db.commit()
    db.refresh(order)
    return order


def complete_order(db: Session, order: Order) -> Order:
    if order.status != OrderStatus.CONFIRMED:
        raise ValueError("Only confirmed orders can be marked completed")
    order.status = OrderStatus.COMPLETED
    db.commit()
    db.refresh(order)
    return order


def load_order_with_relations(db: Session, order_id: int) -> Order | None:
    return (
        db.query(Order)
        .options(
            joinedload(Order.lines)
            .joinedload(OrderLine.knife_model)
            .joinedload(KnifeModel.materials)
            .joinedload(KnifeModelMaterial.material)
        )
        .filter(Order.id == order_id)
        .first()
    )
