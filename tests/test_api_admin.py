import json

from tests.helpers import api_csrf, api_login


def _headers(client):
    return {"X-CSRF-Token": api_csrf(client)}


def _create_10k(client, box=3, slot=5):
    return client.post(
        "/api/parts",
        json={
            "name": "0603 10kΩ 厚膜电阻",
            "aliases": "10K",
            "box": box,
            "slot": slot,
            "qty_kind": "few",
        },
        headers=_headers(client),
    )


def _create_member(client, username="shifu", password="shifupass", display_name="师父"):
    return client.post(
        "/api/users",
        json={"username": username, "display_name": display_name, "password": password},
        headers=_headers(client),
    )


def test_anonymous_history_is_401(client):
    response = client.get("/api/history")
    assert response.status_code == 401
    assert response.json()["detail"] == "未登录"


def test_create_part_then_history(client):
    api_login(client)
    _create_10k(client)
    rows = client.get("/api/history").json()["rows"]
    text = json.dumps(rows, ensure_ascii=False)
    assert "10K" in text
    assert "3号盒第5格" in text
    assert "admin" in text


def test_member_cannot_open_users_or_backup(client):
    api_login(client)
    _create_member(client)
    client.post("/api/logout", headers=_headers(client))
    api_login(client, username="shifu", password="shifupass")
    users = client.get("/api/users")
    assert users.status_code == 403
    assert users.json()["detail"] == "只有管理员能管账号"
    backup = client.get("/api/backup.json")
    assert backup.status_code == 403
    assert "password_hash" not in backup.text
    assert "adminpass" not in backup.text


def test_admin_can_raise_box_count(client):
    api_login(client)
    saved = client.put(
        "/api/settings/box_count",
        json={"box_count": 15},
        headers=_headers(client),
    )
    assert saved.status_code == 204
    me = client.get("/api/me").json()
    assert me["box_count"] == 15


def test_cannot_shrink_box_count_below_used_box(client):
    api_login(client)
    _create_10k(client, box=3)
    refused = client.put(
        "/api/settings/box_count",
        json={"box_count": 2},
        headers=_headers(client),
    )
    assert refused.status_code == 400
    assert "3号盒" in refused.json()["detail"]
    me = client.get("/api/me").json()
    assert me["box_count"] == 12


def test_admin_backup_has_no_passwords(client):
    api_login(client)
    _create_10k(client)
    response = client.get("/api/backup.json")
    assert response.status_code == 200
    assert "attachment" in response.headers.get("content-disposition", "")
    payload = response.json()
    dumped = json.dumps(payload)
    assert "password_hash" not in dumped
    assert "adminpass" not in dumped
    assert any(part["aliases"] == "10K" for part in payload["parts"])
    for user in payload["users"]:
        assert "password" not in user
        assert "password_hash" not in user


def test_disabled_member_cannot_login(client):
    api_login(client)
    created = _create_member(client)
    user_id = created.json()["id"]
    stopped = client.post(f"/api/users/{user_id}/disable", headers=_headers(client))
    assert stopped.status_code == 204
    client.post("/api/logout", headers=_headers(client))
    token = api_csrf(client)
    denied = client.post(
        "/api/login",
        json={"username": "shifu", "password": "shifupass"},
        headers={"X-CSRF-Token": token},
    )
    assert denied.status_code == 400


def test_admin_reset_password(client):
    api_login(client)
    user_id = _create_member(client, password="oldpass12").json()["id"]
    reset = client.post(
        f"/api/users/{user_id}/reset-password",
        json={"password": "newpass12"},
        headers=_headers(client),
    )
    assert reset.status_code == 204
    client.post("/api/logout", headers=_headers(client))
    api_login(client, username="shifu", password="newpass12")
    me = client.get("/api/me")
    assert me.status_code == 200
    assert me.json()["username"] == "shifu"
