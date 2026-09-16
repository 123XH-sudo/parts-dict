from __future__ import annotations

import bcrypt

from app.models import Setting, User


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
    import os

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
