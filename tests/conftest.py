import pytest
from fastapi.testclient import TestClient
from pathlib import Path

SPA_INDEX = Path(__file__).resolve().parents[1] / "app" / "static" / "spa" / "index.html"
SPA_STUB = '<!doctype html><html><body><div id="app">料盒字典</div></body></html>\n'


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-not-for-production")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "adminpass")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    SPA_INDEX.parent.mkdir(parents=True, exist_ok=True)
    if not SPA_INDEX.exists():
        SPA_INDEX.write_text(SPA_STUB, encoding="utf-8")
    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-not-for-production")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "adminpass")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
