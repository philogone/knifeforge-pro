from sqlalchemy import CheckConstraint, Float
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ShopSettings(Base):
    """A single-row settings table (id is always 1) for shop-wide costing
    defaults — labor rate and target margin. Singleton via a DB check
    constraint rather than a separate "is there a row yet" dance in every
    caller; the row is created once by a data migration / first-run seed."""

    __tablename__ = "shop_settings"
    __table_args__ = (CheckConstraint("id = 1", name="shop_settings_singleton"),)

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    # Starter defaults a buyer is expected to change to their own numbers
    # on first visit to Settings — not a real recommendation.
    hourly_rate: Mapped[float] = mapped_column(Float, default=35.0)
    default_margin_percent: Mapped[float] = mapped_column(Float, default=30.0)
