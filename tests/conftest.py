"""Shared pytest fixtures. No network is needed: SQLite in a temporary folder.

Set TEST_DATABASE_URL to run tests/test_app.py against a disposable PostgreSQL
database (CI does this). WARNING: its tables are dropped before every test.
"""

import os
import secrets
import sys
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# app.main builds a module-level app on import; keep it away from real databases.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.setdefault("SECRET_KEY", secrets.token_hex(32))

from app.main import Base, create_app  # noqa: E402

STAFF_USER = "test-staff"
# Generated for each test run, so no password is stored in the repository.
STAFF_PASSWORD = secrets.token_urlsafe(18)
STAFF_HASH = generate_password_hash(STAFF_PASSWORD)


@pytest.fixture
def app_config(tmp_path):
    return {
        "TESTING": True,
        "DATABASE_URL": os.getenv("TEST_DATABASE_URL") or f"sqlite:///{tmp_path / 'test.db'}",
        "SECRET_KEY": secrets.token_hex(32),
        "STAFF_USERNAME": STAFF_USER,
        "STAFF_PASSWORD_HASH": STAFF_HASH,
        "RELEASE_SHA": "0" * 40,
        "APP_ENV": "test",
    }


@pytest.fixture
def app(app_config):
    application = create_app(app_config)
    database = application.extensions["clover_db"]
    Base.metadata.drop_all(database.engine)
    Base.metadata.create_all(database.engine)
    yield application
    database.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def staff_auth():
    return (STAFF_USER, STAFF_PASSWORD)
