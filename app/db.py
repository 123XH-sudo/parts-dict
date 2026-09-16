from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
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
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)


def make_session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)
