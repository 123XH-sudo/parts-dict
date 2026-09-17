from tests.helpers import api_csrf, api_login


def _headers(client):
    return {"X-CSRF-Token": api_csrf(client)}


def _create(client, **fields):
    body = {
        "name": "0603 10kΩ 厚膜电阻",
        "aliases": "10K,1002",
        "box": 3,
        "slot": 5,
        "qty_kind": "few",
        "polarized": False,
        "note": "",
    }
    body.update(fields)
    return client.post("/api/parts", json=body, headers=_headers(client))


def test_anonymous_create_is_401(client):
    response = client.post(
        "/api/parts",
        json={"name": "x", "aliases": "10K", "box": 3, "slot": 5, "qty_kind": "few"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "未登录"


def test_register_then_search(client):
    api_login(client)
    created = _create(client)
    assert created.status_code == 201
    found = client.get("/api/parts", params={"q": "10K"})
    row = found.json()["results"][0]
    assert row["location"] == "3号盒第5格"
    assert row["qty_label"] == "少量"


def test_empty_query_returns_boxes_not_parts(client):
    api_login(client)
    data = client.get("/api/parts").json()
    assert data["results"] == []
    assert data["boxes"] == list(range(1, 13))


def test_slot_conflict(client):
    api_login(client)
    first = _create(client, name="a", aliases="10K")
    assert first.status_code == 201
    clash = _create(client, name="b", aliases="100nF")
    assert clash.status_code == 400
    assert "3号盒第5格" in clash.json()["detail"]


def test_search_is_case_insensitive_and_supports_and(client):
    api_login(client)
    _create(client)
    lower = client.get("/api/parts", params={"q": "10k"}).json()["results"]
    assert lower[0]["location"] == "3号盒第5格"
    both = client.get("/api/parts", params={"q": "10k 0603"}).json()["results"]
    assert both[0]["location"] == "3号盒第5格"


def test_search_by_box_label(client):
    api_login(client)
    _create(client)
    boxed = client.get("/api/parts", params={"q": "3号盒"}).json()["results"]
    assert boxed[0]["aliases"] == "10K,1002"
    assert boxed[0]["location"] == "3号盒第5格"


def test_put_changes_location(client):
    api_login(client)
    part_id = _create(client).json()["id"]
    updated = client.put(
        f"/api/parts/{part_id}",
        json={
            "name": "0603 10kΩ 厚膜电阻",
            "aliases": "10K,1002",
            "box": 4,
            "slot": 2,
            "qty_kind": "few",
            "polarized": False,
            "note": "",
        },
        headers=_headers(client),
    )
    assert updated.status_code == 200
    row = client.get("/api/parts", params={"q": "10K"}).json()["results"][0]
    assert row["location"] == "4号盒第2格"


def test_deactivate_hides_from_search(client):
    api_login(client)
    part_id = _create(client).json()["id"]
    stopped = client.post(f"/api/parts/{part_id}/deactivate", headers=_headers(client))
    assert stopped.status_code == 204
    found = client.get("/api/parts", params={"q": "10K"}).json()["results"]
    assert found == []


def test_missing_part_is_404(client):
    api_login(client)
    response = client.get("/api/parts/99")
    assert response.status_code == 404
    assert response.json()["detail"] == "没有这条料。"
