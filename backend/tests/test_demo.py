"""Public demo: fictitious workshop, entered without a password, nothing can be changed."""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

from app.models.customer import Customer
from app.models.sales_document import SalesDocument
from app.services.demo_service import rebuild, write_allowed


def test_only_reads_and_pure_calculations_get_through():
    assert write_allowed("GET", "/api/admin/orders")
    assert write_allowed("POST", "/api/admin/nesting/run")
    assert write_allowed("POST", "/api/admin/calibration/analyse/")
    assert not write_allowed("POST", "/api/admin/orders")
    assert not write_allowed("PATCH", "/api/admin/designs/1")
    assert not write_allowed("DELETE", "/api/admin/customers/1")
    assert not write_allowed("POST", "/api/admin/settings/restore")
    assert not write_allowed("POST", "/api/auth/setup")


def test_rebuild_fills_a_complete_fictitious_workshop(db):
    rebuild(db)
    assert db.query(Customer).count() == 2
    docs = db.query(SalesDocument).all()
    assert {d.kind.value for d in docs} == {"quote", "invoice"}
    assert all(d.number for d in docs)  # issued, numbered
    rebuild(db)  # a second start gives the same workshop, not twice as much
    assert db.query(Customer).count() == 2


def test_demo_server_end_to_end(tmp_path):
    """A real demo process: its own settings, its own database, its middleware."""
    script = textwrap.dedent(
        """
        from fastapi.testclient import TestClient
        from app.main import app

        with TestClient(app) as client:
            assert client.get("/api/auth/status").json() == {"needs_setup": False, "demo": True}
            assert client.post("/api/auth/login", json={"email": "x@example.com", "password": "x"}).status_code == 403
            token = client.post("/api/auth/demo").json()["access_token"]
            h = {"Authorization": f"Bearer {token}"}
            assert client.get("/api/admin/dashboard", headers=h).status_code == 200
            assert len(client.get("/api/admin/customers", headers=h).json()) == 2
            refused = client.post("/api/admin/customers", headers=h, json={"name": "Intrus"})
            assert refused.status_code == 403 and refused.json() == {"detail": "Read-only demo"}
            assert client.post("/api/admin/settings/restore", headers=h).status_code == 403
            ok = client.post("/api/admin/calibration/analyse", headers=h, json={"kerf_used_mm": 0, "measurements": {"A": 119.8}})
            assert ok.status_code == 200
        print("demo ok")
        """
    )
    env = {
        **os.environ,
        "DEMO": "true",
        "DATABASE_URL": f"sqlite:///{(tmp_path / 'demo.db').as_posix()}",
        "SECRET_KEY": "demo-test-secret-0123456789",
        "ADMIN_EMAIL": "",
        "ADMIN_PASSWORD_HASH": "",
        "REDIS_URL": "",
    }
    result = subprocess.run([sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr[-3000:]
    assert "demo ok" in result.stdout
