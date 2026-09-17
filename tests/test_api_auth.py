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
