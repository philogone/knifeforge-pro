import json

import pytest

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


def _as_version_007(backup):
    """A backup as KnifeForge 0.9 (schema 007) wrote it: no payments, no history, none of the
    lot 10 columns."""
    old = json.loads(json.dumps(backup))
    old["schema_revision"] = "007"
    for table in ("payments", "document_events"):
        old["tables"].pop(table, None)
    for row in old["tables"].get("sales_documents", []):
        for col in ("is_deposit", "prepaid_amount", "prepaid_refs"):
            row.pop(col, None)
    for row in old["tables"].get("shop_settings", []):
        for col in ("account_customers", "account_sales_goods", "account_sales_services", "account_vat", "account_deposits",
                    "account_bank", "email_send_template", "reminder_templates", "last_backup_at"):
            row.pop(col, None)
    return old


def test_backup_from_an_earlier_version_is_upgraded_then_restored(client):
    from app.services.backup_service import inspect_backup, upgrade_backup
    from tests.test_invoicing import customer, invoice, seller

    seller(client)
    doc = invoice(client, customer(client)["id"])
    client.post(f"/api/admin/documents/{doc['id']}/issue")
    client.post(f"/api/admin/documents/{doc['id']}/status?status=paid&paid_at=2026-10-01")
    old = _as_version_007(client.get("/api/admin/settings/backup").json())

    info = inspect_backup(old)
    assert info["compatibility"] == "older" and info["counts"]["customers"] == 1 and info["counts"]["documents"] == 1

    upgraded = upgrade_backup(old)
    assert upgraded["upgraded_from"] == "007" and upgraded["schema_revision"] != "007"
    # the 0.9 "paid" invoice gets its payment, as an installed update would give it
    assert [(p["amount"], p["paid_on"]) for p in upgraded["tables"]["payments"]] == [("180.00", "2026-10-01")]
    assert upgraded["tables"]["shop_settings"][0]["account_customers"] == "411000"

    assert client.post("/api/admin/settings/restore", json=upgraded).status_code == 200
    restored = client.get(f"/api/admin/documents/{doc['id']}").json()
    assert restored["status"] == "paid" and restored["balance_due"] == "0.00"


def test_backup_from_a_newer_version_is_refused(client):
    from app.services.backup_service import BackupError, inspect_backup, upgrade_backup

    newer = client.get("/api/admin/settings/backup").json()
    newer["schema_revision"] = "999"
    assert inspect_backup(newer)["compatibility"] == "newer"
    with pytest.raises(BackupError, match="newer version"):
        upgrade_backup(newer)
    assert client.post("/api/admin/settings/backup/inspect", json={"format": "autre"}).status_code == 400


def test_backup_status_remembers_the_last_download(client):
    assert client.get("/api/admin/settings/backup/status").json()["last_manual_at"] is None
    client.get("/api/admin/settings/backup")
    assert client.get("/api/admin/settings/backup/status").json()["last_manual_at"] is not None
