from sqlalchemy import Boolean, CheckConstraint, Float, String, Text, false
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
    # Who made the knife, printed in the client plan's title block.
    workshop_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    workshop_contact: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # A small PNG / JPEG / SVG as a data URL (kept with the row: one image, no file store).
    workshop_logo: Mapped[str | None] = mapped_column(Text, nullable=True)
    # first-run wizard completed (or skipped): the app stops redirecting to it
    # ---- invoicing: seller identity and legal mentions (printed and in the Factur-X XML)
    legal_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    address_line1: Mapped[str | None] = mapped_column(String(200), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str] = mapped_column(String(2), default="FR", server_default="FR")
    siren: Mapped[str | None] = mapped_column(String(9), nullable=True)
    siret: Mapped[str | None] = mapped_column(String(14), nullable=True)
    # "franchise": micro-entreprise, VAT not applicable (art. 293 B du CGI); "normal": VAT charged
    vat_regime: Mapped[str] = mapped_column(String(10), default="franchise", server_default="franchise")
    vat_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    default_vat_rate: Mapped[float] = mapped_column(Float, default=20.0, server_default="20")
    trade_register: Mapped[str | None] = mapped_column(String(120), nullable=True)  # RM / RCS mention
    iban: Mapped[str | None] = mapped_column(String(34), nullable=True)
    bic: Mapped[str | None] = mapped_column(String(11), nullable=True)
    payment_terms_days: Mapped[int] = mapped_column(default=30, server_default="30")
    late_penalty_text: Mapped[str | None] = mapped_column(String(300), nullable=True)
    quote_validity_days: Mapped[int] = mapped_column(default=30, server_default="30")
    onboarding_done: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
