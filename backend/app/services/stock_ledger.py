"""Every change to a material's stock goes through here, so the ledger always explains the total."""

from sqlalchemy.orm import Session

from app.models.material import Material
from app.models.stock_movement import MovementReason, StockMovement


def record_movement(
    db: Session,
    material: Material,
    delta: float,
    reason: MovementReason,
    order_id: int | None = None,
    cost: float | None = None,
    note: str | None = None,
) -> None:
    """Call after `material.quantity_in_stock` has been updated; the caller commits."""
    if not delta:
        return
    db.add(
        StockMovement(
            material_id=material.id,
            delta=delta,
            balance_after=material.quantity_in_stock,
            reason=reason,
            order_id=order_id,
            cost=cost,
            note=note,
        )
    )
