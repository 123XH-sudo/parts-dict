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


def test_anonymous_boxes_is_401(client):
    listed = client.get("/api/boxes")
    assert listed.status_code == 401
    assert listed.json()["detail"] == "未登录"
    one = client.get("/api/boxes/3")
    assert one.status_code == 401
    saved = client.put("/api/boxes/3/layout", json={"cols": 6, "rows": 4})
    assert saved.status_code == 401


def test_boxes_default_to_eight_by_six(client):
    api_login(client)
    data = client.get("/api/boxes").json()
    assert len(data["boxes"]) == 12
    third = data["boxes"][2]
    assert third["n"] == 3
    assert third["cols"] == 8
    assert third["rows"] == 6
    assert third["total"] == 48
    assert third["used"] == 0


def test_box_used_counts_parts(client):
    api_login(client)
    _create(client, name="料一", aliases="AA1", box=3, slot=5)
    _create(client, name="料二", aliases="AA2", box=3, slot=6)
    third = client.get("/api/boxes").json()["boxes"][2]
    assert third["used"] == 2


def test_empty_box_has_48_null_slots(client):
    api_login(client)
    data = client.get("/api/boxes/3").json()
    assert data["n"] == 3
    assert data["cols"] == 8
    assert data["rows"] == 6
    assert len(data["slots"]) == 48
    assert all(item is None for item in data["slots"])
    assert data["overflow"] == []


def test_slot_five_lands_on_index_four(client):
    api_login(client)
    created = _create(client, name="第五格", aliases="S5", box=3, slot=5)
    assert created.status_code == 201
    data = client.get("/api/boxes/3").json()
    assert data["slots"][4]["aliases"] == "S5"
    assert data["slots"][4]["slot"] == 5
    assert data["slots"][0] is None
    assert data["overflow"] == []


def test_put_layout_changes_grid_size(client):
    api_login(client)
    saved = client.put(
        "/api/boxes/3/layout",
        json={"cols": 6, "rows": 4},
        headers=_headers(client),
    )
    assert saved.status_code == 200
    data = client.get("/api/boxes/3").json()
    assert data["cols"] == 6
    assert data["rows"] == 4
    assert len(data["slots"]) == 24
    listed = client.get("/api/boxes").json()["boxes"][2]
    assert listed["total"] == 24


def test_overflow_when_slot_exceeds_grid(client):
    api_login(client)
    _create(client, name="格外", aliases="OUT30", box=3, slot=30)
    client.put(
        "/api/boxes/3/layout",
        json={"cols": 6, "rows": 4},
        headers=_headers(client),
    )
    data = client.get("/api/boxes/3").json()
    assert len(data["slots"]) == 24
    assert all(item is None for item in data["slots"])
    assert data["overflow"][0]["aliases"] == "OUT30"
    assert data["overflow"][0]["slot"] == 30


def test_layout_rejects_bad_size(client):
    api_login(client)
    zero = client.put(
        "/api/boxes/3/layout",
        json={"cols": 0, "rows": 6},
        headers=_headers(client),
    )
    assert zero.status_code == 400
    huge = client.put(
        "/api/boxes/3/layout",
        json={"cols": 25, "rows": 6},
        headers=_headers(client),
    )
    assert huge.status_code == 400


def test_missing_box_is_404(client):
    api_login(client)
    response = client.get("/api/boxes/99")
    assert response.status_code == 404
    assert response.json()["detail"] == "没有这个盒。"
