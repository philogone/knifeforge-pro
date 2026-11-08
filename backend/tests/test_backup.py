from app.services.backup_service import FORMAT, export_backup

from tests.test_designs_api import create_design, make_material, make_model, make_order


def test_backup_restores_everything_exactly(client, db):
    steel = make_material(db)
    model = make_model(db)
    create_design(client, material_id=steel.id, knife_model_id=model.id)
    make_order(db, model, 2)
    client.patch("/api/admin/settings/shop", json={"workshop_name": "Atelier", "hourly_rate": 42})

    backup = client.get("/api/admin/settings/backup").json()
    assert backup["format"] == FORMAT and backup["tables"]["materials"][0]["name"] == steel.name

    # wreck the data, then restore
    client.patch("/api/admin/settings/shop", json={"workshop_name": "Autre", "hourly_rate": 1})
    client.delete(f"/api/admin/designs/{backup['tables']['designs'][0]['id']}")
    restored = client.post("/api/admin/settings/restore", json=backup)
    assert restored.status_code == 200, restored.text
    assert restored.json()["restored"]["materials"] == 1

    again = export_backup(db)
    assert again["tables"] == backup["tables"]
    assert client.get("/api/admin/settings/shop").json()["workshop_name"] == "Atelier"
    # the design document (JSON column) and enums came back intact
    design = client.get("/api/admin/designs").json()[0]
    assert design["kind"] == "blade" and design["part_count"] == 1


def test_restore_refuses_foreign_or_unknown_content(client):
    assert client.post("/api/admin/settings/restore", json={"hello": 1}).status_code == 400
    bad = {"format": FORMAT, "format_version": 1, "schema_revision": None, "tables": {"nope": []}}
    response = client.post("/api/admin/settings/restore", json=bad)
    assert response.status_code == 400 and "nope" in response.json()["detail"]
