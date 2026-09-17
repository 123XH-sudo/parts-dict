from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="member")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(256), nullable=False)


class Part(Base):
    __tablename__ = "parts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    aliases: Mapped[str] = mapped_column(String(400), nullable=False)
    aliases_norm: Mapped[str] = mapped_column(String(400), nullable=False)
    name_norm: Mapped[str] = mapped_column(String(200), nullable=False)
    box: Mapped[int] = mapped_column(Integer, nullable=False)
    slot: Mapped[int] = mapped_column(Integer, nullable=False)
    qty_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    qty_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    polarized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    username_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    part_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    summary: Mapped[str] = mapped_column(String(400), nullable=False)
    before_json: Mapped[str] = mapped_column(Text, default="", nullable=False)
    after_json: Mapped[str] = mapped_column(Text, default="", nullable=False)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    source_filename: Mapped[str] = mapped_column(String(260), nullable=False)
    uploaded_by: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class JobLine(Base):
    __tablename__ = "job_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(Integer, nullable=False)
    designators: Mapped[str] = mapped_column(String(400), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    footprint: Mapped[str] = mapped_column(String(200), nullable=False)
    supplier: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    part_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    skip_bin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    polarized_hint: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    warning: Mapped[str] = mapped_column(String(200), default="", nullable=False)
