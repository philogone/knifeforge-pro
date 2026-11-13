"""Trade profile, the workshop's own stages, time spent on orders."""

from datetime import date

from app.models.order import OrderStatus
from tests.test_designs_api import make_model, make_order


def test_default_stages_follow_the_trade(client):
    keys = [s["key"] for s in client.get("/api/admin/settings/stages").json()]
    assert keys[0] == "todo" and "heat_treatment" in keys and keys[-1] == "delivered"
    client.patch("/api/admin/settings/shop", json={"trade": "blacksmith"})
    keys = [s["key"] for s in client.get("/api/admin/settings/stages").json()]
    assert "install" in keys and "heat_treatment" not in keys
    assert client.patch("/api/admin/settings/shop", json={"trade": "plumber"}).status_code == 422


def test_workshop_renames_adds_and_reorders_stages(client, db):
    order = make_order(db, make_model(db), 1)
    body = {"stages": [
        {"key": "todo", "label": None},
        {"key": None, "label": "Damas"},
        {"key": "forging", "label": "Forge et découpe"},
        {"key": None, "label": "Étui en cuir"},
        {"key": "delivered", "label": None},
    ]}
    out = client.put("/api/admin/settings/stages", json=body).json()
    assert [s["key"] for s in out] == ["todo", "damas", "forging", "etui_en_cuir", "delivered"]
    assert out[2]["label"] == "Forge et découpe"
    # orders move to a new stage; an unknown stage is refused
    assert client.patch(f"/api/admin/orders/{order.id}", json={"stage": "damas"}).status_code == 200
    assert client.patch(f"/api/admin/orders/{order.id}", json={"stage": "grinding"}).status_code == 422
    # a stage still holding an active order cannot be removed
    body["stages"].pop(1)
    assert client.put("/api/admin/settings/stages", json=body).status_code == 409
    # the dashboard counts per the workshop's stages, in its order
    by_stage = client.get("/api/admin/dashboard").json()["orders"]["by_stage"]
    assert list(by_stage)[:3] == ["todo", "damas", "forging"] and by_stage["damas"] == 1
    # back to the trade's stages: the order keeps its stage, still counted
    client.delete("/api/admin/settings/stages")
    assert client.get("/api/admin/dashboard").json()["orders"]["by_stage"]["damas"] == 1


def test_time_spent_against_planned(client, db):
    model = make_model(db)
    model.base_labor_hours = 6
    order = make_order(db, model, 2)
    client.patch("/api/admin/settings/shop", json={"hourly_rate": 40})
    r = client.post(f"/api/admin/orders/{order.id}/time", json={"worked_on": str(date.today()), "minutes": 150, "stage": "forging", "note": "Forge des deux lames"})
    assert r.status_code == 201
    r = client.post(f"/api/admin/orders/{order.id}/time", json={"worked_on": str(date.today()), "minutes": 90, "stage": "grinding"}).json()
    assert r["spent_minutes"] == 240 and r["planned_minutes"] == 720 and r["spent_cost"] == 160.0
    assert r["by_stage"] == {"forging": 150, "grinding": 90}
    r = client.delete(f"/api/admin/orders/{order.id}/time/{r['entries'][0]['id']}").json()
    assert r["spent_minutes"] == 90
    assert client.post(f"/api/admin/orders/{order.id}/time", json={"worked_on": str(date.today()), "minutes": 0}).status_code == 422
