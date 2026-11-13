"""Public demo (DEMO=true): a fictitious workshop anyone can open, that nobody can change.

- Visitors enter without a password (`POST /api/auth/demo`); there is no real account.
- Every write is refused (middleware in app/main.py), except the calculations that write
  nothing: nesting, offset, calibration analysis, exports.
- The database is rebuilt from scratch at each start: a nightly restart (see
  docker-compose.demo.yml) brings it back to the same state, whatever happened.

Only invented data: names, addresses and numbers below belong to nobody.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.order import Order
from app.models.sales_document import DocumentKind, DocumentStatus, OperationNature, SalesDocument, SalesDocumentLine
from app.services import billing_service as billing
from app.services.seed_service import seed_mock_data, seed_mock_designs
from app.services.shop_settings_service import get_shop_settings

from app.config import DEMO_EMAIL  # noqa: F401 - re-exported

# POST requests that compute and return a result without writing anything
READ_ONLY_POSTS = (
    "/api/auth/demo",
    "/api/admin/designs/geometry/offset",
    "/api/admin/nesting/run",
    "/api/admin/nesting/export",
    "/api/admin/calibration/analyse",
)


def write_allowed(method: str, path: str) -> bool:
    if method in ("GET", "HEAD", "OPTIONS"):
        return True
    return method == "POST" and path.rstrip("/") in READ_ONLY_POSTS


def rebuild(db: Session) -> None:
    """Empty every table, then fill the demo workshop."""
    from app.database import Base

    engine = db.get_bind()
    db.close()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    seed_mock_data(db)
    seed_mock_designs(db)

    shop = get_shop_settings(db)
    shop.workshop_name = "Atelier de démonstration"
    shop.legal_name = "Atelier de démonstration"
    shop.address_line1 = "1 rue de l'Exemple"
    shop.postal_code = "00000"
    shop.city = "Démoville"
    shop.siren = "000000000"
    shop.iban = "FR7630006000011234567890189"  # the standard sample IBAN of the specification
    shop.vat_regime = "franchise"
    shop.onboarding_done = True
    db.commit()

    sam = Customer(name="Sam Exemple", email="sam@example.com", address_line1="2 place du Modèle", postal_code="00000", city="Démoville")
    pro = Customer(
        is_business=True,
        name="Dominique Essai",
        company_name="Coutellerie Fictive SARL",
        email="contact@example.com",
        address_line1="3 avenue du Test",
        postal_code="00000",
        city="Démoville",
        siren="000000001",
    )
    db.add_all([sam, pro])
    db.commit()

    # the seeded orders become the customers' orders
    orders = db.query(Order).order_by(Order.id).all()
    if orders:
        orders[0].customer_id, orders[0].customer_name, orders[0].customer_email = sam.id, sam.name, sam.email
        orders[0].due_date = date.today() + timedelta(days=12)
    if len(orders) > 1:
        orders[1].customer_id, orders[1].customer_name, orders[1].customer_email = pro.id, pro.company_name, pro.email
        orders[1].due_date = date.today() + timedelta(days=4)
    db.commit()

    settings = get_shop_settings(db)
    if len(orders) > 1:
        quote = billing.draft_from_order(db, orders[0], DocumentKind.QUOTE, settings)
        billing.issue(db, quote, settings)
        invoice = billing.draft_from_order(db, orders[1], DocumentKind.INVOICE, settings)
        billing.issue(db, invoice, settings)

    paid = SalesDocument(kind=DocumentKind.INVOICE, customer_id=pro.id, nature=OperationNature.SERVICES)
    paid.lines.append(
        SalesDocumentLine(position=0, description="Affûtage et remise en état (lot de 6)", quantity=Decimal(6), unit="C62", unit_price_ht=Decimal("18.00"), vat_rate=Decimal(0))
    )
    billing.compute_totals(paid)
    db.add(paid)
    db.commit()
    billing.issue(db, paid, settings)
    paid.status = DocumentStatus.PAID
    paid.paid_at = date.today()
    db.commit()
