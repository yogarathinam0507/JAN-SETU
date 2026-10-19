"""Test configuration: isolated SQLite database, migrations + deterministic seed, no background jobs."""
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp(prefix="jansetu-test-"))
os.environ.update({
    "DATABASE_URL": os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{TMP / 'test.db'}",
    "UPLOAD_DIR": str(TMP / "uploads"),
    "SECRET_KEY": "test-secret-key-0123456789abcdef0123456789",
    "ENABLE_BACKGROUND_JOBS": "false",
    "RATE_LIMIT_PER_MINUTE": "100000",
    "AUTH_RATE_LIMIT_PER_MINUTE": "100000",
    "APP_ENV": "development",
    "LLM_PROVIDER": "", "LLM_API_KEY": "", "LLM_MODEL": "",
    "PUBLIC_BASE_URL": "https://jansetu.example.org",
})
sys.path.insert(0, str(ROOT / "backend"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

DEMO_PASSWORD = "Demo@1234"


def _migrate_and_seed():
    from alembic import command
    from alembic.config import Config
    cfg = Config(str(ROOT / "backend" / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "backend" / "migrations"))
    command.upgrade(cfg, "head")
    from app.seed import main as seed_main
    assert seed_main([]) == 0


_migrate_and_seed()


@pytest.fixture(scope="session")
def app():
    from app.main import app as fastapi_app
    return fastapi_app


@pytest.fixture()
def client(app):
    with TestClient(app) as c:
        yield c


def login(client, username, password=DEMO_PASSWORD) -> dict:
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture()
def auth(client):
    return lambda username: login(client, username)


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(TMP, ignore_errors=True)
