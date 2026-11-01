import bcrypt
import pytest

from app.routers import auth


@pytest.fixture
def local_admin(monkeypatch):
    password = "s3cret-pass"
    monkeypatch.setattr(auth.settings, "admin_email", "admin@test.local")
    monkeypatch.setattr(auth.settings, "admin_password_hash", bcrypt.hashpw(password.encode(), bcrypt.gensalt(4)).decode())
    return password


def test_login_accepts_reserved_domain_admin_email(client, local_admin):
    response = client.post("/api/auth/login", json={"email": "admin@test.local", "password": local_admin})
    assert response.status_code == 200
    assert response.json()["access_token"]


def test_login_wrong_password_is_401_not_422(client, local_admin):
    response = client.post("/api/auth/login", json={"email": "admin@test.local", "password": "wrong"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_login_unknown_email_is_401(client, local_admin):
    response = client.post("/api/auth/login", json={"email": "someone@test.local", "password": local_admin})
    assert response.status_code == 401
