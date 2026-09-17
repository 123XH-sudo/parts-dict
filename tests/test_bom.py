from pathlib import Path

from tests.helpers import csrf_token, login

BOM_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs/examples/BOM_无刷驱动_1_PCB1_12_2026-9-16.xlsx"
)


def _upload(client, title="无刷驱动 PCB1"):
    page = client.get("/jobs")
    with BOM_PATH.open("rb") as handle:
        return client.post(
            "/jobs",
            data={"title": title, "csrf_token": csrf_token(page.text)},
            files={
                "file": (
                    BOM_PATH.name,
                    handle,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            follow_redirects=False,
        )


def _create_part(client, name, aliases, box="3", slot="5"):
    form = client.get("/parts/new")
    client.post(
        "/parts",
        data={
            "name": name,
            "aliases": aliases,
            "box": box,
            "slot": slot,
            "qty_kind": "few",
            "csrf_token": csrf_token(form.text),
        },
        follow_redirects=False,
    )


def _section(html: str, heading: str, stop: str) -> str:
    start = html.index(f"<h2>{heading}</h2>")
    end = html.index(f"<h2>{stop}</h2>", start + 1)
    return html[start:end]


def test_anonymous_cannot_upload_bom(client):
    page = client.get("/jobs", follow_redirects=False)
    assert page.status_code in (302, 303)
    assert "/login" in page.headers["location"]
    with BOM_PATH.open("rb") as handle:
        response = client.post(
            "/jobs",
            data={"title": "无刷驱动 PCB1", "csrf_token": "nope"},
            files={"file": (BOM_PATH.name, handle, "application/octet-stream")},
            follow_redirects=False,
        )
    assert response.status_code in (302, 303)
    assert "/login" in response.headers["location"]


def test_parse_sample_bom_has_69_lines_and_10k_row(client):
    login(client)
    created = _upload(client)
    assert created.status_code in (302, 303)
    location = created.headers["location"]
    assert "/jobs/" in location
    page = client.get(location)
    assert page.status_code == 200
    assert "R251,R42,R44" in page.text
    assert "10K" in page.text
    assert "R0603" in page.text
    assert page.text.count("<tr") >= 69


def test_matched_10k_shows_location_unmatched_goes_unregistered(client):
    login(client)
    created = _upload(client, title="空字典板")
    page = client.get(created.headers["location"])
    unreg = _section(page.text, "未登记", "不用从料盒拿")
    assert "R251,R42,R44" in unreg
    assert "3号盒第5格" not in page.text

    _create_part(client, "0603 10kΩ 厚膜电阻", "10K")
    created = _upload(client, title="空字典板")
    page = client.get(created.headers["location"])
    assert "3号盒第5格" in page.text
    boxed = _section(page.text, "按盒拿料", "未登记")
    assert "R251,R42,R44" in boxed
    assert "10K" in boxed


def test_polarity_section_lists_diodes_and_ics_not_resistors(client):
    login(client)
    created = _upload(client)
    page = client.get(created.headers["location"])
    polar = _section(page.text, "有极性，别贴反", "按盒拿料")
    for name in ["1N4148WS", "BSC014N06NS", "N32G435CBL7", "LED_0603-R", "470uF/80V"]:
        assert name in polar, name
    for name in ["10K", "100nF", "NTC1", "Test-Point", "铜条", "WAFER"]:
        assert name not in polar, name
    skip = page.text[page.text.index("不用从料盒拿") :]
    assert "Test-Point" in skip
    assert "铜条" in skip


def test_registering_after_upload_updates_existing_job_without_reupload(client):
    login(client)
    created = _upload(client, title="先上传再登记")
    job_url = created.headers["location"]
    page = client.get(job_url)
    unreg = _section(page.text, "未登记", "不用从料盒拿")
    assert "R251,R42,R44" in unreg

    _create_part(client, "0603 10kΩ 厚膜电阻", "10K")
    refreshed = client.get(job_url)
    boxed = _section(refreshed.text, "按盒拿料", "未登记")
    assert "R251,R42,R44" in boxed
    assert "3号盒第5格" in boxed
    later_unreg = _section(refreshed.text, "未登记", "不用从料盒拿")
    assert "R251,R42,R44" not in later_unreg


def test_moving_part_updates_existing_job_location(client):
    login(client)
    _create_part(client, "0603 10kΩ 厚膜电阻", "10K")
    created = _upload(client, title="改格子后看清单")
    job_url = created.headers["location"]
    page = client.get(job_url)
    assert "3号盒第5格" in page.text

    form = client.get("/parts/1/edit")
    client.post(
        "/parts/1",
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
    moved = client.get(job_url)
    boxed = _section(moved.text, "按盒拿料", "未登记")
    assert "4号盒第2格" in boxed
    assert "3号盒第5格" not in boxed


def test_10k_does_not_match_10k1n(client):
    login(client)
    _create_part(client, "0603 NTC 10k", "10K1N", box="9", slot="1")
    created = _upload(client)
    page = client.get(created.headers["location"])
    unreg = _section(page.text, "未登记", "不用从料盒拿")
    assert "R251,R42,R44" in unreg
    assert "9号盒第1格" not in unreg
    assert "NTC1" in page.text
    assert "9号盒第1格" in page.text
