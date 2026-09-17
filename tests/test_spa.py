from pathlib import Path


def test_spa_dir_exists():
    assert Path("app/static/spa").is_dir()


def test_api_csrf_not_captured_by_spa(client):
    response = client.get("/api/csrf")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
