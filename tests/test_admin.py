import re

from tests.helpers import csrf_token, login


def _create_10k(client, box="3", slot="5"):
    form = client.get("/parts/new")
    client.post(
        "/parts",
        data={
            "name": "0603 10kΩ 厚膜电阻",
            "aliases": "10K",
            "box": box,
            "slot": slot,
            "qty_kind": "few",
            "csrf_token": csrf_token(form.text),
        },
        follow_redirects=False,
    )


def _logout(client):
    client.get("/logout", follow_redirects=False)


def test_member_cannot_open_accounts_page(client):
    login(client)
    page = client.get("/users")
    token = csrf_token(page.text)
    client.post(
        "/users",
        data={
            "username": "shifu",
            "display_name": "师父",
            "password": "shifupass",
            "csrf_token": token,
        },
        follow_redirects=False,
    )
    _logout(client)
    login(client, username="shifu", password="shifupass")
    denied = client.get("/users")
    assert denied.status_code == 403
    assert "账号" in denied.text or "管理员" in denied.text


def test_admin_creates_member_who_can_register_parts(client):
    login(client)
    page = client.get("/users")
    assert page.status_code == 200
    assert "账号" in page.text
    created = client.post(
        "/users",
        data={
            "username": "shifu",
            "display_name": "师父",
            "password": "shifupass",
            "csrf_token": csrf_token(page.text),
        },
        follow_redirects=False,
    )
    assert created.status_code in (302, 303)
    _logout(client)
    login(client, username="shifu", password="shifupass")
    home = client.get("/")
    assert home.status_code == 200
    assert "师父" in home.text
    assert 'href="/users"' not in home.text
    _create_10k(client)
    found = client.get("/?q=10K")
    assert "3号盒第5格" in found.text


def test_deactivate_hides_part_from_search(client):
    login(client)
    _create_10k(client)
    found = client.get("/?q=10K")
    assert "3号盒第5格" in found.text
    match = re.search(r'href="/parts/(\d+)/edit"', found.text)
    assert match
    part_id = match.group(1)
    form = client.get(f"/parts/{part_id}/edit")
    stopped = client.post(
        f"/parts/{part_id}/deactivate",
        data={"csrf_token": csrf_token(form.text)},
        follow_redirects=False,
    )
    assert stopped.status_code in (302, 303)
    missing = client.get("/?q=10K")
    assert "3号盒第5格" not in missing.text
    history = client.get("/history")
    assert "停用" in history.text


def test_disabled_user_cannot_login(client):
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
    users = client.get("/users")
    client.post(
        "/users/2/disable",
        data={"csrf_token": csrf_token(users.text)},
        follow_redirects=False,
    )
    _logout(client)
    login_page = client.get("/login")
    response = client.post(
        "/login",
        data={
            "username": "shifu",
            "password": "shifupass",
            "csrf_token": csrf_token(login_page.text),
        },
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert "用户名或密码不对" in response.text


def test_admin_reset_password_lets_member_login(client):
    login(client)
    page = client.get("/users")
    client.post(
        "/users",
        data={
            "username": "shifu",
            "display_name": "师父",
            "password": "oldpass12",
            "csrf_token": csrf_token(page.text),
        },
        follow_redirects=False,
    )
    users = client.get("/users")
    client.post(
        "/users/2/reset-password",
        data={
            "password": "newpass12",
            "csrf_token": csrf_token(users.text),
        },
        follow_redirects=False,
    )
    _logout(client)
    login(client, username="shifu", password="newpass12")
    home = client.get("/")
    assert home.status_code == 200


def test_default_box_count_is_twelve(client):
    login(client)
    form = client.get("/parts/new")
    assert "12号盒" in form.text or 'value="12"' in form.text
    assert "13号盒" not in form.text and 'value="13"' not in form.text


def test_admin_can_raise_box_count_to_fifteen(client):
    login(client)
    page = client.get("/users")
    saved = client.post(
        "/settings/box_count",
        data={"box_count": "15", "csrf_token": csrf_token(page.text)},
        follow_redirects=False,
    )
    assert saved.status_code in (302, 303)
    form = client.get("/parts/new")
    assert "15号盒" in form.text or 'value="15"' in form.text
    home = client.get("/")
    assert "15号盒" in home.text
    history = client.get("/history")
    assert "15" in history.text


def test_cannot_shrink_box_count_below_used_box(client):
    login(client)
    _create_10k(client, box="3")
    page = client.get("/users")
    refused = client.post(
        "/settings/box_count",
        data={"box_count": "2", "csrf_token": csrf_token(page.text)},
        follow_redirects=False,
    )
    assert refused.status_code == 200
    assert "3号盒" in refused.text
    form = client.get("/parts/new")
    assert "12号盒" in form.text or 'value="12"' in form.text


def test_member_cannot_change_box_count(client):
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
    denied = client.post(
        "/settings/box_count",
        data={"box_count": "15", "csrf_token": "nope"},
        follow_redirects=False,
    )
    assert denied.status_code == 403
    _logout(client)
    login(client)
    form = client.get("/parts/new")
    assert "15号盒" not in form.text
    assert "12号盒" in form.text or 'value="12"' in form.text
