def csrf_token(html: str) -> str:
    marker = 'name="csrf_token" value="'
    start = html.index(marker) + len(marker)
    end = html.index('"', start)
    return html[start:end]


def login(client, username="admin", password="adminpass"):
    page = client.get("/login")
    response = client.post(
        "/login",
        data={
            "username": username,
            "password": password,
            "csrf_token": csrf_token(page.text),
        },
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)


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
