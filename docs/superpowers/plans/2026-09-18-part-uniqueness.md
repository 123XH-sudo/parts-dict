# 元件唯一性 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 启用中的元件按详细名或简称完全相同判定为同一颗时，只能占一个格子；重复保存返回 400 并写出已有位置。

**Architecture:** 在 `app/main.py` 现有 `occupied(box, slot)` 旁增加 `same_part(session, name_norm, aliases_norm, exclude_id)`。`POST /api/parts` 与 `PUT /api/parts/{id}` 在格子占用检查之前调用它。命中则 400，文案 `这颗料已在 {位置}，不能重复登记。` 不改表结构、不加唯一索引、不改前端提交逻辑。

**Tech Stack:** Python 3.12, FastAPI, SQLite, pytest, TestClient。

## Global Constraints

- Spec: `docs/superpowers/specs/2026-09-18-part-uniqueness-design.md`
- 只检查 `active=true`；停用后可重新登记。
- 比较用现有 `normalize()`：去空格、`Ω`/`ω`，转小写；简称按 `aliases_norm` 逗号拆开后整段相等，不做包含匹配。
- 检查顺序：字段校验 → 元件已存在 → 格子占用 → 写入。
- 多条命中时取 `id` 最小的那条写位置。
- 用户可见文案用中文；API 校验失败 400 `{"detail":"..."}`。
- 不改 `parts` 表，不加唯一索引，不做实时查重，不给已存在记录做跳转。
- 测试：pytest + TestClient，改 `tests/test_api_parts.py`。
- 本任务不提交 git，除非用户明确要求。

## File structure

| Path | Responsibility |
|---|---|
| `tests/test_api_parts.py` | 元件唯一性 API 测试 |
| `app/main.py` | `same_part()`；创建/更新时在 `occupied()` 之前拦截 |

---

### Task 1: 元件名称/简称唯一性

**Files:**
- Modify: `tests/test_api_parts.py`
- Modify: `app/main.py`（`occupied` 之后、`POST /api/parts` 与 `PUT /api/parts/{id}` 的写入前）

**Interfaces:**
- Consumes: 现有 `_create(client, **fields)`、`occupied(session, box, slot, exclude_id)`、`location_text`、`parse_part_fields`
- Produces: `same_part(session, name_norm: str, aliases_norm: str, exclude_id: int | None = None) -> Part | None`；冲突时 `fail(400, f"这颗料已在 {location_text(part.box, part.slot)}，不能重复登记。")`

- [ ] **Step 1: Write failing tests**

在 `tests/test_api_parts.py` 末尾追加：

```python
def test_duplicate_name_is_rejected(client):
    api_login(client)
    first = _create(client, name="0603 10kΩ 厚膜电阻", aliases="10K")
    assert first.status_code == 201
    clash = _create(
        client,
        name="0603 10kΩ 厚膜电阻",
        aliases="1002",
        box=3,
        slot=6,
    )
    assert clash.status_code == 400
    assert clash.json()["detail"] == "这颗料已在 3号盒第5格，不能重复登记。"


def test_duplicate_alias_is_rejected(client):
    api_login(client)
    first = _create(client, name="普通 10KR", aliases="10KR", box=3, slot=5)
    assert first.status_code == 201
    clash = _create(
        client,
        name="另一颗 10KR",
        aliases="10KR,1002",
        box=4,
        slot=1,
    )
    assert clash.status_code == 400
    assert clash.json()["detail"] == "这颗料已在 3号盒第5格，不能重复登记。"


def test_similar_aliases_are_not_duplicates(client):
    api_login(client)
    first = _create(
        client,
        name="10KR(0.1%)高精度电阻 R0603",
        aliases="10KR高精度电阻",
        box=3,
        slot=5,
    )
    assert first.status_code == 201
    second = _create(
        client,
        name="10KR电阻0603",
        aliases="10KR",
        box=3,
        slot=6,
    )
    assert second.status_code == 201


def test_deactivated_part_name_can_be_reused(client):
    api_login(client)
    part_id = _create(client, name="可停用", aliases="STOP1", box=3, slot=5).json()["id"]
    stopped = client.post(f"/api/parts/{part_id}/deactivate", headers=_headers(client))
    assert stopped.status_code == 204
    again = _create(client, name="可停用", aliases="STOP1", box=3, slot=5)
    assert again.status_code == 201


def test_update_to_another_part_name_is_rejected(client):
    api_login(client)
    first = _create(client, name="料A", aliases="AA", box=3, slot=5)
    second = _create(client, name="料B", aliases="BB", box=4, slot=2)
    assert first.status_code == 201
    assert second.status_code == 201
    clash = client.put(
        f"/api/parts/{second.json()['id']}",
        json={
            "name": "料A",
            "aliases": "BB",
            "box": 4,
            "slot": 2,
            "qty_kind": "few",
            "polarized": False,
            "note": "",
        },
        headers=_headers(client),
    )
    assert clash.status_code == 400
    assert clash.json()["detail"] == "这颗料已在 3号盒第5格，不能重复登记。"


def test_update_qty_without_name_change_is_ok(client):
    api_login(client)
    part_id = _create(client).json()["id"]
    updated = client.put(
        f"/api/parts/{part_id}",
        json={
            "name": "0603 10kΩ 厚膜电阻",
            "aliases": "10K,1002",
            "box": 3,
            "slot": 5,
            "qty_kind": "exact",
            "qty_count": 20,
            "polarized": False,
            "note": "",
        },
        headers=_headers(client),
    )
    assert updated.status_code == 200
    assert updated.json()["id"] == part_id
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_api_parts.py -v`

Expected: 新测试 FAIL。`test_duplicate_name_is_rejected` 与 `test_duplicate_alias_is_rejected` 实际 201 而非 400。`test_similar_aliases_are_not_duplicates`、`test_deactivated_part_name_can_be_reused`、`test_update_qty_without_name_change_is_ok` 在实现前就应 PASS（现有行为已允许）。若后三条 FAIL，先修测试再实现。

- [ ] **Step 3: Implement `same_part` and call it before `occupied`**

在 `app/main.py` 的 `occupied` 后面增加：

```python
    def same_part(session, name_norm: str, aliases_norm: str, exclude_id: int | None = None):
        query = session.query(Part).filter(Part.active.is_(True))
        if exclude_id is not None:
            query = query.filter(Part.id != exclude_id)
        incoming = {item for item in aliases_norm.split(",") if item}
        for part in query.order_by(Part.id):
            if part.name_norm == name_norm:
                return part
            existing = {item for item in part.aliases_norm.split(",") if item}
            if incoming & existing:
                return part
        return None
```

`POST /api/parts` 在 `taken = occupied(...)` 之前：

```python
            existing = same_part(session, fields["name_norm"], fields["aliases_norm"])
            if existing:
                return fail(
                    400,
                    f"这颗料已在 {location_text(existing.box, existing.slot)}，不能重复登记。",
                )
```

`PUT /api/parts/{part_id}` 在 `taken = occupied(..., exclude_id=part.id)` 之前：

```python
            existing = same_part(
                session,
                fields["name_norm"],
                fields["aliases_norm"],
                exclude_id=part.id,
            )
            if existing:
                return fail(
                    400,
                    f"这颗料已在 {location_text(existing.box, existing.slot)}，不能重复登记。",
                )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_api_parts.py -v`

Expected: 全部 PASS，包括原有 `test_slot_conflict`。

- [ ] **Step 5: Run full suite**

Run: `.venv/bin/pytest -v`

Expected: 全部 PASS。

- [ ] **Step 6: Commit only if the user asks**

Do not commit in this task unless explicitly requested.
