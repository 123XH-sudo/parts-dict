from __future__ import annotations

from datetime import datetime

from app.models import AuditLog, Job, JobLine, Part, Setting, User


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


def dump_backup(session) -> dict:
    users = []
    for user in session.query(User).order_by(User.id):
        users.append(
            {
                "id": user.id,
                "username": user.username,
                "display_name": user.display_name,
                "role": user.role,
                "active": user.active,
                "created_at": iso(user.created_at),
            }
        )
    parts = []
    for part in session.query(Part).order_by(Part.id):
        parts.append(
            {
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
                "created_by": part.created_by,
                "created_at": iso(part.created_at),
                "updated_at": iso(part.updated_at),
            }
        )
    audit_logs = []
    for log in session.query(AuditLog).order_by(AuditLog.id):
        audit_logs.append(
            {
                "id": log.id,
                "at": iso(log.at),
                "user_id": log.user_id,
                "username_snapshot": log.username_snapshot,
                "part_id": log.part_id,
                "action": log.action,
                "summary": log.summary,
                "before_json": log.before_json,
                "after_json": log.after_json,
            }
        )
    settings = [
        {"key": row.key, "value": row.value}
        for row in session.query(Setting).order_by(Setting.key)
    ]
    jobs = []
    for job in session.query(Job).order_by(Job.id):
        jobs.append(
            {
                "id": job.id,
                "title": job.title,
                "source_filename": job.source_filename,
                "uploaded_by": job.uploaded_by,
                "created_at": iso(job.created_at),
                "updated_at": iso(job.updated_at),
            }
        )
    job_lines = []
    for line in session.query(JobLine).order_by(JobLine.id):
        job_lines.append(
            {
                "id": line.id,
                "job_id": line.job_id,
                "designators": line.designators,
                "name": line.name,
                "footprint": line.footprint,
                "supplier": line.supplier,
                "quantity": line.quantity,
                "part_id": line.part_id,
                "skip_bin": line.skip_bin,
                "polarized_hint": line.polarized_hint,
                "warning": line.warning,
            }
        )
    return {
        "parts": parts,
        "users": users,
        "audit_logs": audit_logs,
        "settings": settings,
        "jobs": jobs,
        "job_lines": job_lines,
    }
