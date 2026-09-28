from tests.helpers import api_csrf, api_login


def test_csrf_available_when_anonymous(client):
    page = client.get("/api/csrf")
    assert page.status_code == 200
    assert page.json()["csrf_token"]


def test_api_wrong_password(client):
    token = api_csrf(client)
    response = client.post(
        "/api/login",
        json={"username": "admin", "password": "wrong"},
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "用户名或密码不对"


def test_register_then_use_as_member(client):
    token = api_csrf(client)
    created = client.post(
        "/api/register",
        json={"username": "xin", "display_name": "新同事", "password": "xinpass12"},
        headers={"X-CSRF-Token": token},
    )
    assert created.status_code == 204
    me = client.get("/api/me")
    assert me.status_code == 200
    body = me.json()
    assert body["username"] == "xin"
    assert body["display_name"] == "新同事"
    assert body["role"] == "member"
    blocked = client.get("/api/users")
    assert blocked.status_code == 403


def test_register_rejects_short_password_and_duplicate(client):
    token = api_csrf(client)
    short = client.post(
        "/api/register",
        json={"username": "xin", "password": "short"},
        headers={"X-CSRF-Token": token},
    )
    assert short.status_code == 400
    assert short.json()["detail"] == "密码至少 8 位。"
    ok = client.post(
        "/api/register",
        json={"username": "xin", "password": "xinpass12"},
        headers={"X-CSRF-Token": token},
    )
    assert ok.status_code == 204
    again = client.post(
        "/api/register",
        json={"username": "xin", "password": "xinpass12"},
        headers={"X-CSRF-Token": api_csrf(client)},
    )
    assert again.status_code == 400
    assert again.json()["detail"] == "这个用户名已经有了。"


def test_api_login_me_and_logout(client):
    api_login(client)
    me = client.get("/api/me")
    assert me.status_code == 200
    body = me.json()
    assert body["username"] == "admin"
    assert body["role"] == "admin"
    assert body["box_count"] == 12
    client.post("/api/logout", headers={"X-CSRF-Token": body["csrf_token"]})
    assert client.get("/api/me").status_code == 401
