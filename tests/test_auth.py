def test_login_page_shows_title(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert "料盒字典" in response.text
    assert 'name="username"' in response.text
    assert 'name="password"' in response.text


def test_home_redirects_to_login_when_anonymous(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (302, 303)
    assert "/login" in response.headers["location"]


def test_wrong_password_stays_on_login(client):
    page = client.get("/login")
    csrf = _csrf(page.text)
    response = client.post(
        "/login",
        data={"username": "admin", "password": "wrong", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert "用户名或密码不对" in response.text


def test_correct_password_enters_home(client):
    page = client.get("/login")
    csrf = _csrf(page.text)
    response = client.post(
        "/login",
        data={"username": "admin", "password": "adminpass", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)
    assert response.headers["location"] in ("/", "http://testserver/")
    home = client.get("/")
    assert home.status_code == 200
    assert "料盒字典" in home.text
    assert "admin" in home.text


def _csrf(html: str) -> str:
    marker = 'name="csrf_token" value="'
    start = html.index(marker) + len(marker)
    end = html.index('"', start)
    return html[start:end]
