import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MovementReason(str, enum.Enum):
    RESTOCK = "restock"  # a purchase (cost recorded)
    CORRECTION = "correction"  # manual adjustment, no cost
    ORDER_CONFIRMED = "order_confirmed"  # deducted for an order
    ORDER_CANCELLED = "order_cancelled"  # given back when a confirmed order is cancelled
    INITIAL = "initial"  # stock entered when the material was created


class StockMovement(Base):
    """Append-only ledger of every stock change: what, how much, why, when, for which order.
    `quantity_in_stock` on the material is the running total; this explains it."""

    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id", ondelete="CASCADE"), nullable=False, index=True)
    delta: Mapped[float] = mapped_column(Float, nullable=False)
    balance_after: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[MovementReason] = mapped_column(
        Enum(MovementReason, name="movement_reason", values_callable=lambda e: [x.value for x in e]), nullable=False
    )
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
