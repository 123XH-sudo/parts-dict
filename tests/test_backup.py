import json

from tests.helpers import csrf_token, login


def _logout(client):
    client.get("/logout", follow_redirects=False)


def test_anonymous_cannot_download_backup(client):
    response = client.get("/backup.json", follow_redirects=False)
    assert response.status_code in (302, 303)
    assert "/login" in response.headers["location"]


def test_member_cannot_download_backup(client):
    login(client)
    page = client.get("/users")
    client.post(
        "/users",
        data={
            "username": "shifu",
            "display_name": "师父",
            "password": "shifupass",
            "csrf_token": csrf_token(page.text),
        },
        follow_redirects=False,
    )
    _logout(client)
    login(client, username="shifu", password="shifupass")
    denied = client.get("/backup.json")
    assert denied.status_code == 403
    assert "password_hash" not in denied.text
    assert "adminpass" not in denied.text


def test_admin_backup_json_has_parts_users_audit_without_passwords(client):
    login(client)
    form = client.get("/parts/new")
    client.post(
        "/parts",
        data={
            "name": "0603 10kΩ 厚膜电阻",
            "aliases": "10K",
            "box": "3",
            "slot": "5",
            "qty_kind": "few",
            "csrf_token": csrf_token(form.text),
        },
        follow_redirects=False,
    )
    users = client.get("/users")
    assert "导出备份" in users.text
    assert 'href="/backup.json"' in users.text
    response = client.get("/backup.json")
    assert response.status_code == 200
    assert "attachment" in response.headers.get("content-disposition", "")
    assert "json" in response.headers.get("content-type", "")
    payload = response.json()
    assert "parts" in payload
    assert "users" in payload
    assert "audit_logs" in payload
    assert "settings" in payload
    assert any(part["aliases"] == "10K" for part in payload["parts"])
    assert any(user["username"] == "admin" for user in payload["users"])
    dumped = json.dumps(payload)
    assert "password_hash" not in dumped
    assert "adminpass" not in dumped
    for user in payload["users"]:
        assert "password" not in user
        assert "password_hash" not in user
    assert any(log.get("action") == "part.create" for log in payload["audit_logs"])
