from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def database_url() -> str:
    return os.environ.get("DATABASE_URL", "sqlite:///./data/parts.db")


def make_engine(url: str | None = None):
    url = url or database_url()
    if url.startswith("sqlite:///"):
        raw = url.removeprefix("sqlite:///")
        if raw.startswith("./"):
            Path(raw).parent.mkdir(parents=True, exist_ok=True)
        elif raw.startswith("/") and "/" in raw[1:]:
            Path(raw).parent.mkdir(parents=True, exist_ok=True)
    connect_args = (
        {"check_same_thread": False, "timeout": 1.0} if url.startswith("sqlite") else {}
    )
    engine = create_engine(url, connect_args=connect_args)
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=1000")
            cursor.close()

    return engine


def make_session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)
