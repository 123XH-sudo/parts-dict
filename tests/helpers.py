def api_csrf(client) -> str:
    return client.get("/api/csrf").json()["csrf_token"]


def api_login(client, username="admin", password="adminpass"):
    token = api_csrf(client)
    response = client.post(
        "/api/login",
        json={"username": username, "password": password},
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 204


login = api_login
