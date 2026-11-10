"""Desktop build: first-run account, local config, daily automatic backup."""

import json
import os
import time
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.core import desktop
from app.main import app
from app.services import auto_backup
from tests.test_designs_api import make_material


@pytest.fixture
def desktop_mode(tmp_path):
    """Switch the shared settings to a desktop install with no account yet, then put them back."""
    settings = get_settings()
    saved = {k: getattr(settings, k) for k in ("desktop", "data_dir", "admin_email", "admin_password_hash")}
    settings.desktop, settings.data_dir = True, str(tmp_path)
    settings.admin_email, settings.admin_password_hash = "", ""
    yield tmp_path
    for key, value in saved.items():
        setattr(settings, key, value)


def test_prepare_environment_generates_and_keeps_the_secret(tmp_path, monkeypatch):
    for key in ("DESKTOP", "DATA_DIR", "DATABASE_URL", "SECRET_KEY", "ADMIN_EMAIL", "ADMIN_PASSWORD_HASH", "REDIS_URL", "FRONTEND_DIST", "ENVIRONMENT"):
        monkeypatch.setenv(key, os.environ.get(key, ""))  # restored by monkeypatch afterwards
    first = desktop.prepare_environment(tmp_path, None)
    assert len(first["secret_key"]) == 64
    assert os.environ["DATABASE_URL"] == f"sqlite:///{(tmp_path / 'knifeforge.db').as_posix()}"
    assert os.environ["ADMIN_PASSWORD_HASH"] == ""
    again = desktop.prepare_environment(tmp_path, None)
    assert again["secret_key"] == first["secret_key"]  # sessions survive a restart


def test_docker_mode_never_offers_account_creation():
    client = TestClient(app)
    assert client.get("/api/auth/status").json() == {"needs_setup": False}
    assert client.post("/api/auth/setup", json={"email": "a@b.fr", "password": "x" * 12}).status_code == 409


def test_first_run_creates_the_account_once(desktop_mode):
    client = TestClient(app)
    assert client.get("/api/auth/status").json() == {"needs_setup": True}
    assert client.post("/api/auth/login", json={"email": "a@b.fr", "password": "whatever-123"}).status_code == 409

    assert client.post("/api/auth/setup", json={"email": "atelier@local", "password": "court"}).status_code == 422
    created = client.post("/api/auth/setup", json={"email": " atelier@local ", "password": "un-mot-de-passe"})
    assert created.status_code == 201
    token = created.json()["access_token"]
    assert client.get("/api/admin/dashboard", headers={"Authorization": f"Bearer {token}"}).status_code == 200

    stored = json.loads((desktop_mode / "config.json").read_text(encoding="utf-8"))
    assert stored["admin_email"] == "atelier@local"
    assert stored["admin_password_hash"].startswith("$2b$") and "un-mot-de-passe" not in json.dumps(stored)

    assert client.get("/api/auth/status").json() == {"needs_setup": False}
    assert client.post("/api/auth/setup", json={"email": "autre@local", "password": "x" * 12}).status_code == 409
    assert client.post("/api/auth/login", json={"email": "atelier@local", "password": "un-mot-de-passe"}).status_code == 200
    assert client.post("/api/auth/login", json={"email": "atelier@local", "password": "mauvais-mot"}).status_code == 401


def test_auto_backup_endpoints_only_exist_on_desktop(client):
    assert client.get("/api/admin/settings/auto-backup").status_code == 404


def test_auto_backup_writes_a_restorable_file_and_keeps_the_schedule(desktop_mode, client, db):
    make_material(db, name="Barre 1095")
    state = client.get("/api/admin/settings/auto-backup").json()
    assert state["enabled"] and state["directory"] == str(desktop_mode / "Sauvegardes") and state["last_at"] is None

    now = datetime(2026, 11, 10, 9, 30)
    assert auto_backup.run_if_due(now) is True
    files = list((desktop_mode / "Sauvegardes").iterdir())
    assert [f.name for f in files] == ["knifeforge-2026-11-10_0930.json"]
    content = json.loads(files[0].read_text(encoding="utf-8"))
    assert content["format"] and any(row["name"] == "Barre 1095" for row in content["tables"]["materials"])

    assert auto_backup.run_if_due(now + timedelta(hours=23)) is False  # not yet a day
    assert auto_backup.run_if_due(now + timedelta(hours=24)) is True

    restored = client.post("/api/admin/settings/restore", json=content)
    assert restored.status_code == 200, restored.text


def test_auto_backup_prunes_only_its_own_old_files(desktop_mode):
    folder = desktop_mode / "cle-usb"
    folder.mkdir()
    old = folder / "knifeforge-2026-09-01_0930.json"
    recent = folder / "knifeforge-2026-11-01_0930.json"
    foreign = folder / "photos-atelier.json"
    for f in (old, recent, foreign):
        f.write_text("{}", encoding="utf-8")
    ancient = time.time() - 60 * 86400
    for f in (old, foreign):
        os.utime(f, (ancient, ancient))

    removed = auto_backup.prune(folder, keep_days=30, now=datetime.now())
    assert removed == [old.name]
    assert recent.exists() and foreign.exists()


def test_auto_backup_settings_check_the_folder(desktop_mode, client):
    target = desktop_mode / "D" / "Sauvegardes KnifeForge"
    saved = client.put("/api/admin/settings/auto-backup", json={"enabled": False, "directory": str(target), "keep_days": 90})
    assert saved.status_code == 200 and saved.json()["keep_days"] == 90 and target.is_dir()
    assert auto_backup.run_if_due() is False  # disabled

    blocked = desktop_mode / "un-fichier"
    blocked.write_text("pas un dossier", encoding="utf-8")
    refused = client.put("/api/admin/settings/auto-backup", json={"enabled": True, "directory": str(blocked), "keep_days": 30})
    assert refused.status_code == 400
