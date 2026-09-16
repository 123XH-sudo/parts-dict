from tests.helpers import csrf_token, login


def test_anonymous_cannot_create_part(client):
    response = client.post(
        "/parts",
        data={
            "name": "0603 10kΩ",
            "aliases": "10K",
            "box": "3",
            "slot": "5",
            "qty_kind": "few",
            "csrf_token": "nope",
        },
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)
    assert "/login" in response.headers["location"]


def test_empty_home_shows_box_buttons_not_parts(client):
    login(client)
    home = client.get("/")
    assert "1号盒" in home.text
    assert "12号盒" in home.text
    assert "13号盒" not in home.text
    assert 'name="q"' in home.text


def test_register_then_search_by_alias(client):
    login(client)
    form = client.get("/parts/new")
    response = client.post(
        "/parts",
        data={
            "name": "0603 10kΩ 厚膜电阻",
            "aliases": "10K,1002",
            "box": "3",
            "slot": "5",
            "qty_kind": "few",
            "csrf_token": csrf_token(form.text),
        },
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)

    found = client.get("/?q=10K")
    assert found.status_code == 200
    assert "3号盒第5格" in found.text
    assert "少量" in found.text
    assert "0603 10kΩ 厚膜电阻" in found.text


def test_search_is_case_insensitive_and_supports_and(client):
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
    )
    lower = client.get("/?q=10k")
    assert "3号盒第5格" in lower.text
    both = client.get("/?q=10k%200603")
    assert "3号盒第5格" in both.text


def test_search_by_box_label(client):
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
    )
    boxed = client.get("/?q=3号盒")
    assert "10K" in boxed.text
    assert "3号盒第5格" in boxed.text


def test_missing_search_offers_register(client):
    login(client)
    page = client.get("/?q=1N4148WS")
    assert "登记：1N4148WS" in page.text
    assert "3号盒第5格" not in page.text
