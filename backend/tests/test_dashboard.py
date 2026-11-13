from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.core.security import require_admin
from app.main import app

from app.models.knife_model import KnifeModel, KnifeModelMaterial
from app.models.order import OrderStage, OrderStatus
from app.services.dashboard_service import build_dashboard
from tests.test_designs_api import make_material, make_order
from tests.test_invoicing import customer, invoice, seller

TODAY = date(2026, 11, 10)


def priced_model(db, name="Bushcraft", price=200.0, hours=2.0, steel=None, blank_mm=None):
    model = KnifeModel(name=name, sale_price=price, base_labor_hours=hours)
    if steel is not None:
        model.materials.append(KnifeModelMaterial(material_id=steel.id, blank_length_mm=blank_mm))
    db.add(model)
    db.commit()
    return model


def test_requires_admin_auth():
    app.dependency_overrides.pop(require_admin, None)
    assert TestClient(app).get("/api/admin/dashboard").status_code == 401


def test_empty_workshop(client):
    body = client.get("/api/admin/dashboard").json()
    assert body["orders"]["active"] == 0
    assert body["orders"]["by_status"] == {"draft": 0, "confirmed": 0, "completed": 0, "cancelled": 0}
    assert body["finance"]["pipeline_revenue"] == 0
    assert len(body["finance"]["monthly"]) == 6
    assert body["stock"]["materials"] == []


def test_orders_feasibility_and_due_dates(db):
    steel = make_material(db, quantity_in_stock=500, kerf_mm=0)
    small = priced_model(db, "Petit", steel=steel, blank_mm=200)  # 200 mm each
    big = priced_model(db, "Grand", steel=steel, blank_mm=400)

    ok = make_order(db, small, 2)  # 400 mm needed, 500 in stock: buildable
    short = make_order(db, big, 2)  # 800 mm: short
    confirmed = make_order(db, small, 1, status=OrderStatus.CONFIRMED)
    make_order(db, small, 1, status=OrderStatus.CANCELLED)

    ok.due_date = TODAY - timedelta(days=1)  # late
    short.due_date = TODAY + timedelta(days=3)  # this week
    confirmed.due_date = TODAY + timedelta(days=20)
    confirmed.stage = OrderStage.GRINDING
    db.commit()

    orders = build_dashboard(db, TODAY).orders
    assert orders.by_status == {"draft": 2, "confirmed": 1, "completed": 0, "cancelled": 1}
    assert orders.active == 3
    assert orders.by_stage["grinding"] == 1 and orders.by_stage["todo"] == 2
    assert (orders.drafts_feasible, orders.drafts_short) == (1, 1)
    assert (orders.late, orders.due_this_week) == (1, 1)
    assert [u.order_id for u in orders.upcoming] == [ok.id, short.id, confirmed.id]
    assert orders.upcoming[0].late and not orders.upcoming[1].late


def test_pipeline_uses_sale_price_and_full_costing(client, db):
    client.patch("/api/admin/settings/shop", json={"hourly_rate": 40})
    steel = make_material(db, quantity_in_stock=5000, kerf_mm=0, unit_cost=0.05)  # 0.05 €/mm
    model = priced_model(db, price=200.0, hours=2.0, steel=steel, blank_mm=200)  # cost 10 + 80 = 90
    free = priced_model(db, "Sans prix", price=0.0, hours=1.0)  # cost 40, no price
    make_order(db, model, 3)
    make_order(db, free, 1, status=OrderStatus.CONFIRMED)
    make_order(db, model, 5, status=OrderStatus.COMPLETED)  # finished: out of the pipeline

    finance = build_dashboard(db, TODAY).finance
    assert finance.pipeline_revenue == 600.0
    assert finance.pipeline_cost == 3 * 90 + 40
    assert finance.pipeline_margin == 600.0 - 310
    assert finance.unpriced_lines == 1


def test_invoiced_amounts_subtract_credit_notes(client, db):
    seller(client)
    buyer = customer(client)
    first = invoice(client, buyer["id"])  # 180 HT
    second = invoice(client, buyer["id"], lines=[{"description": "Affûtage", "quantity": "2", "unit_price_ht": "25.00", "vat_rate": "0"}])
    draft = invoice(client, buyer["id"])  # never issued: not counted
    for doc in (first, second):
        assert client.post(f"/api/admin/documents/{doc['id']}/issue").status_code == 200
    note = client.post(f"/api/admin/documents/{second['id']}/credit-note").json()
    assert client.post(f"/api/admin/documents/{note['id']}/issue").status_code == 200
    assert draft["status"] == "draft"

    today = date.today()  # issuing stamps the real date
    finance = build_dashboard(db, today).finance
    assert finance.invoiced_month_ht == 180.0
    assert finance.invoiced_year_ht == 180.0
    assert finance.monthly[-1].amount_ht == 180.0
    assert finance.monthly[-1].month == f"{today.year:04d}-{today.month:02d}"
    # the 50 € invoice is cancelled by its credit note: only the 180 € one is still to collect
    assert finance.unpaid_count == 1
    assert finance.unpaid_ttc == 180.0


def test_stock_levels_flag_and_sort_low_materials(db):
    make_material(db, name="Plein", quantity_in_stock=3000, low_stock_threshold=1000, unit_cost=0.01)
    make_material(db, name="Bas", quantity_in_stock=500, low_stock_threshold=1000, unit_cost=0.02)
    make_material(db, name="Sans seuil", quantity_in_stock=10)

    stock = build_dashboard(db, TODAY).stock
    assert [m.name for m in stock.materials] == ["Bas", "Plein", "Sans seuil"]
    assert stock.low_count == 1
    assert stock.total_value == 3000 * 0.01 + 500 * 0.02
