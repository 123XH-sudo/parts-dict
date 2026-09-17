from pathlib import Path

from tests.helpers import api_csrf, api_login

BOM = Path("docs/examples/BOM_无刷驱动_1_PCB1_12_2026-9-16.xlsx")


def _headers(client):
    return {"X-CSRF-Token": api_csrf(client)}


def _upload(client, title="先上传"):
    return client.post(
        "/api/jobs",
        data={"title": title, "csrf_token": api_csrf(client)},
        files={
            "file": (
                BOM.name,
                BOM.read_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )


def test_anonymous_cannot_upload(client):
    response = client.post(
        "/api/jobs",
        files={"file": (BOM.name, BOM.read_bytes(), "application/octet-stream")},
    )
    assert response.status_code == 401


def test_upload_then_register_refreshes_job(client):
    api_login(client)
    created = _upload(client)
    assert created.status_code == 201
    job_id = created.json()["id"]
    page = client.get(f"/api/jobs/{job_id}").json()
    assert any(line["designators"] == "R251,R42,R44" for line in page["unreg"])
    client.post(
        "/api/parts",
        json={
            "name": "0603 10kΩ 厚膜电阻",
            "aliases": "10K",
            "box": 3,
            "slot": 5,
            "qty_kind": "few",
        },
        headers=_headers(client),
    )
    again = client.get(f"/api/jobs/{job_id}").json()
    boxed = [row for _, rows in again["box_groups"] for row in rows]
    assert any(
        row["line"]["designators"] == "R251,R42,R44" and row["location"] == "3号盒第5格"
        for row in boxed
    )


def test_sample_bom_has_69_lines(client):
    api_login(client)
    job_id = _upload(client, title="无刷驱动 PCB1").json()["id"]
    page = client.get(f"/api/jobs/{job_id}").json()
    unique = set()
    for row in page["polar"]:
        unique.add(row["line"]["designators"])
    for _, rows in page["box_groups"]:
        for row in rows:
            unique.add(row["line"]["designators"])
    for line in page["unreg"] + page["skip"]:
        unique.add(line["designators"])
    assert len(unique) == 69
    listed = client.get("/api/jobs").json()["jobs"]
    assert any(job["id"] == job_id for job in listed)


def test_polarity_lists_diodes_not_resistors(client):
    api_login(client)
    job_id = _upload(client).json()["id"]
    page = client.get(f"/api/jobs/{job_id}").json()
    polar_names = [row["line"]["name"] for row in page["polar"]]
    for name in ["1N4148WS", "BSC014N06NS", "N32G435CBL7", "LED_0603-R", "470uF/80V"]:
        assert name in polar_names, name
    for name in ["10K", "100nF", "NTC1", "Test-Point", "铜条", "WAFER"]:
        assert name not in polar_names, name
    skip_names = [line["name"] for line in page["skip"]]
    assert "Test-Point" in skip_names
    assert "铜条" in skip_names


def test_10k_does_not_match_10k1n(client):
    api_login(client)
    client.post(
        "/api/parts",
        json={
            "name": "0603 NTC 10k",
            "aliases": "10K1N",
            "box": 9,
            "slot": 1,
            "qty_kind": "few",
        },
        headers=_headers(client),
    )
    job_id = _upload(client).json()["id"]
    page = client.get(f"/api/jobs/{job_id}").json()
    unreg = page["unreg"]
    assert any(line["designators"] == "R251,R42,R44" for line in unreg)
    boxed = [row for _, rows in page["box_groups"] for row in rows]
    assert not any(row["location"] == "9号盒第1格" and "R251" in row["line"]["designators"] for row in boxed)
    assert any(row["location"] == "9号盒第1格" for row in boxed)
    names = [row["line"]["name"] + row["line"]["designators"] for row in boxed]
    names += [row["line"]["name"] + row["line"]["designators"] for row in page["polar"]]
    names += [line["name"] + line["designators"] for line in page["unreg"] + page["skip"]]
    assert any("NTC1" in name for name in names)
