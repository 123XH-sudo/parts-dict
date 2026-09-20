from __future__ import annotations

import json
import os
import re

import bcrypt

from app.models import Setting, User

DEFAULT_BOX_COLS = 8
DEFAULT_BOX_ROWS = 6

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,32}$")


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("ascii"))
    except ValueError:
        return False


def seed_admin(session) -> None:
    if session.query(User).count() > 0:
        return
    username = os.environ.get("ADMIN_USERNAME", "admin").strip()
    password = os.environ.get("ADMIN_PASSWORD", "")
    if not username or not password:
        raise RuntimeError("首次启动需要设置 ADMIN_USERNAME 和 ADMIN_PASSWORD")
    session.add(
        User(
            username=username,
            password_hash=hash_password(password),
            display_name=username,
            role="admin",
            active=True,
        )
    )
    session.commit()


def seed_settings(session) -> None:
    if session.get(Setting, "box_count") is None:
        session.add(Setting(key="box_count", value="12"))
        session.commit()


def box_count(session) -> int:
    row = session.get(Setting, "box_count")
    if row is None:
        return 12
    try:
        n = int(row.value)
    except ValueError:
        return 12
    return min(99, max(1, n))


def valid_username(name: str) -> bool:
    return bool(USERNAME_RE.fullmatch(name))


def parse_box_count(raw: str) -> int | None:
    try:
        n = int(raw)
    except ValueError:
        return None
    if n < 1 or n > 99:
        return None
    return n


def parse_layout_size(raw) -> int | None:
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return None
    if n < 1 or n > 24:
        return None
    return n


def box_layouts(session) -> dict:
    row = session.get(Setting, "box_layouts")
    if row is None or not row.value:
        return {}
    try:
        data = json.loads(row.value)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def layout_for(session, box_n: int) -> tuple[int, int]:
    item = box_layouts(session).get(str(box_n), {})
    if not isinstance(item, dict):
        return DEFAULT_BOX_COLS, DEFAULT_BOX_ROWS
    cols = parse_layout_size(item.get("cols")) or DEFAULT_BOX_COLS
    rows = parse_layout_size(item.get("rows")) or DEFAULT_BOX_ROWS
    return cols, rows


def save_box_layout(session, box_n: int, cols: int, rows: int) -> None:
    data = box_layouts(session)
    data[str(box_n)] = {"cols": cols, "rows": rows}
    row = session.get(Setting, "box_layouts")
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    if row is None:
        session.add(Setting(key="box_layouts", value=payload))
    else:
        row.value = payload
