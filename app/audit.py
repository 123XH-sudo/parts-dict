from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from app.models import AuditLog, Part
from app.search import QTY_LABEL, location_text

ACTION_LABEL = {
    "part.create": "新建",
    "part.update": "修改",
    "part.deactivate": "停用",
    "user.create": "开账号",
    "user.disable": "停用账号",
    "user.reset_password": "重置密码",
    "settings.update": "改设置",
}


def snapshot(part: Part) -> dict:
    return {
        "id": part.id,
        "name": part.name,
        "aliases": part.aliases,
        "box": part.box,
        "slot": part.slot,
        "qty_kind": part.qty_kind,
        "qty_count": part.qty_count,
        "note": part.note,
        "polarized": part.polarized,
        "active": part.active,
    }


def dumps(data: dict | None) -> str:
    if not data:
        return ""
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def location_summary(before: dict | None, after: dict) -> str:
    after_loc = location_text(after["box"], after["slot"])
    if before is None:
        return f"新建 {after['aliases']} 于 {after_loc}"
    before_loc = location_text(before["box"], before["slot"])
    changes = []
    if before_loc != after_loc:
        changes.append(f"{before_loc} → {after_loc}")
    if before.get("qty_kind") != after.get("qty_kind") or before.get("qty_count") != after.get(
        "qty_count"
    ):
        def qty(row: dict) -> str:
            if row["qty_kind"] == "exact":
                return str(row["qty_count"])
            return QTY_LABEL.get(row["qty_kind"], row["qty_kind"])

        changes.append(f"{qty(before)} → {qty(after)}")
    if before.get("aliases") != after.get("aliases"):
        changes.append("改了简称")
    if before.get("name") != after.get("name"):
        changes.append("改了详细名称")
    if before.get("polarized") != after.get("polarized"):
        changes.append("改了极性标记")
    if before.get("active") and not after.get("active"):
        changes.append("停用")
    if not changes:
        changes.append("保存了其它字段")
    return "；".join(changes)


def write_event(
    session,
    *,
    user_id: int,
    username: str,
    action: str,
    summary: str,
    part_id: int | None = None,
    before: dict | None = None,
    after: dict | None = None,
):
    session.add(
        AuditLog(
            user_id=user_id,
            username_snapshot=username,
            part_id=part_id,
            action=action,
            summary=summary,
            before_json=dumps(before),
            after_json=dumps(after),
        )
    )


def write_audit(session, *, user_id: int, username: str, action: str, part: Part, before: dict | None):
    after = snapshot(part)
    write_event(
        session,
        user_id=user_id,
        username=username,
        action=action,
        summary=location_summary(before, after),
        part_id=part.id,
        before=before,
        after=after,
    )


def format_local(dt: datetime, tz_name: str = "Asia/Shanghai") -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(ZoneInfo(tz_name)).strftime("%Y-%m-%d %H:%M")


def history_row(log: AuditLog) -> dict:
    after = json.loads(log.after_json) if log.after_json else {}
    return {
        "at": format_local(log.at),
        "who": log.username_snapshot,
        "action": ACTION_LABEL.get(log.action, log.action),
        "target": after.get("aliases") or after.get("name") or after.get("username") or "",
        "summary": log.summary,
    }
