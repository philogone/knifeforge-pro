"""Shared test setup: every test runs against a throw-away in-memory SQLite
database (never the real Postgres), with admin auth bypassed for API tests."""

import os

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ["DATABASE_URL"] = "sqlite://"
os.environ.setdefault("ADMIN_EMAIL", "admin@example.com")
os.environ.setdefault("ADMIN_PASSWORD_HASH", "$2b$12$abcdefghijklmnopqrstuv")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.database as database  # noqa: E402
from app.core.security import require_admin  # noqa: E402
from app.main import app  # noqa: E402

test_engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


@event.listens_for(test_engine, "connect")
def _enforce_foreign_keys(dbapi_connection, _record):
    # SQLite ignores ON DELETE SET NULL / RESTRICT unless asked — Postgres enforces them.
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


database.SessionLocal.configure(bind=test_engine)


@pytest.fixture(autouse=True)
def _fresh_database():
    database.Base.metadata.create_all(test_engine)
    yield
    database.Base.metadata.drop_all(test_engine)


@pytest.fixture
def db():
    session = database.SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    app.dependency_overrides[require_admin] = lambda: "admin@example.com"
    # No `with`: skip the lifespan so demo data isn't seeded into every test.
    yield TestClient(app)
    app.dependency_overrides.pop(require_admin, None)
