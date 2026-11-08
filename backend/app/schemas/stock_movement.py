from datetime import datetime

from pydantic import BaseModel

from app.models.stock_movement import MovementReason


class StockMovementOut(BaseModel):
    id: int
    delta: float
    balance_after: float
    reason: MovementReason
    order_id: int | None
    cost: float | None
    note: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
