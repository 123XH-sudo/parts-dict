import re

from tests.helpers import csrf_token, login


def _create_10k(client):
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


def test_anonymous_cannot_see_history(client):
    response = client.get("/history", follow_redirects=False)
    assert response.status_code in (302, 303)
    assert "/login" in response.headers["location"]


def test_create_part_writes_history(client):
    login(client)
    _create_10k(client)
    page = client.get("/history")
    assert page.status_code == 200
    assert "admin" in page.text
    assert "10K" in page.text
    assert "3号盒第5格" in page.text


def test_change_slot_shows_from_to_in_history(client):
    login(client)
    _create_10k(client)
    found = client.get("/?q=10K")
    match = re.search(r'href="/parts/(\d+)/edit"', found.text)
    assert match, found.text
    part_id = match.group(1)
    form = client.get(f"/parts/{part_id}/edit")
    client.post(
        f"/parts/{part_id}",
        data={
            "name": "0603 10kΩ 厚膜电阻",
            "aliases": "10K",
            "box": "4",
            "slot": "2",
            "qty_kind": "few",
            "csrf_token": csrf_token(form.text),
        },
        follow_redirects=False,
    )
    moved = client.get("/?q=10K")
    assert "4号盒第2格" in moved.text
    history = client.get("/history")
    assert "3号盒第5格 → 4号盒第2格" in history.text
    assert "admin" in history.text


def test_history_cannot_be_deleted(client):
    login(client)
    response = client.delete("/history", follow_redirects=False)
    assert response.status_code in (404, 405)
    response = client.post("/history", follow_redirects=False)
    assert response.status_code in (404, 405)
