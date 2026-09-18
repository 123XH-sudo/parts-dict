from __future__ import annotations

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

from app.backup import dump_backup
from app.jsonutil import csrf_from_request, fail
from app.bom import BomError, ParsedLine, match_part, parse_bom
from app.audit import history_row, snapshot, write_audit, write_event
from app.auth import (
    box_count,
    hash_password,
    parse_box_count,
    seed_admin,
    seed_settings,
    valid_username,
    verify_password,
)
from app.db import Base, make_engine, make_session_factory
from app.models import AuditLog, Job, JobLine, Part, Setting, User
from app.search import (
    QTY_LABEL,
    aliases_norm,
    location_text,
    normalize,
    parse_aliases,
    search_parts,
)

load_dotenv()

SPA_DIR = Path(__file__).parent / "static" / "spa"


class LoginBody(BaseModel):
    username: str = ""
    password: str = ""


class PartBody(BaseModel):
    name: str = ""
    aliases: str = ""
    box: int | str = ""
    slot: int | str = ""
    qty_kind: str = "few"
    qty_count: int | str | None = None
    note: str = ""
    polarized: bool = False


class UserBody(BaseModel):
    username: str = ""
    display_name: str = ""
    password: str = ""


class PasswordBody(BaseModel):
    password: str = ""


class BoxCountBody(BaseModel):
    box_count: int | str = ""


def qty_text(part: Part) -> str:
    if part.qty_kind == "exact":
        return str(part.qty_count)
    return QTY_LABEL.get(part.qty_kind, part.qty_kind)


def part_result(part: Part) -> dict:
    return {
        "id": part.id,
        "aliases": part.aliases,
        "name": part.name,
        "box": part.box,
        "slot": part.slot,
        "location": location_text(part.box, part.slot),
        "qty_kind": part.qty_kind,
        "qty_count": part.qty_count,
        "qty_label": qty_text(part),
        "polarized": part.polarized,
        "note": part.note,
        "active": part.active,
    }


def create_app() -> FastAPI:
    secret = os.environ.get("SECRET_KEY", "")
    if not secret:
        raise RuntimeError("必须设置 SECRET_KEY")

    engine = make_engine()
    Base.metadata.create_all(engine)
    SessionLocal = make_session_factory(engine)
    with SessionLocal() as session:
        seed_admin(session)
        seed_settings(session)

    app = FastAPI(title="料盒字典")
    app.add_middleware(SessionMiddleware, secret_key=secret, same_site="lax")

    def db():
        return SessionLocal()

    def new_csrf(request: Request) -> str:
        token = secrets.token_hex(16)
        request.session["csrf_token"] = token
        return token

    def valid_csrf(request: Request, token: str) -> bool:
        expected = request.session.get("csrf_token", "")
        return bool(expected) and token == expected

    def check_csrf(request: Request, form_token: str = "") -> bool:
        return valid_csrf(request, csrf_from_request(request) or form_token)

    def api_login_required(request: Request):
        if request.session.get("user_id"):
            return None
        return fail(401, "未登录")

    def api_admin_required(request: Request):
        gate = api_login_required(request)
        if gate:
            return gate
        if request.session.get("role") != "admin":
            return fail(403, "只有管理员能管账号")
        return None

    @app.get("/api/csrf")
    def api_csrf(request: Request):
        return {"csrf_token": new_csrf(request)}

    @app.post("/api/login")
    def api_login(request: Request, body: LoginBody):
        if not check_csrf(request):
            return fail(400, "用户名或密码不对")
        with db() as session:
            user = (
                session.query(User)
                .filter(User.username == body.username.strip(), User.active.is_(True))
                .one_or_none()
            )
            if user is None or not verify_password(body.password, user.password_hash):
                return fail(400, "用户名或密码不对")
            request.session["user_id"] = user.id
            request.session["username"] = user.username
            request.session["display_name"] = user.display_name
            request.session["role"] = user.role
        return Response(status_code=204)

    @app.post("/api/logout")
    def api_logout(request: Request):
        if not check_csrf(request):
            return fail(400, "提交已过期，请再保存一次。")
        request.session.clear()
        return Response(status_code=204)

    @app.get("/api/me")
    def api_me(request: Request):
        gate = api_login_required(request)
        if gate:
            return gate
        with db() as session:
            n_boxes = box_count(session)
        return {
            "username": request.session.get("username", ""),
            "display_name": request.session.get("display_name", ""),
            "role": request.session.get("role", ""),
            "box_count": n_boxes,
            "csrf_token": new_csrf(request),
        }

    def occupied(session, box_n: int, slot_n: int, exclude_id: int | None = None):
        query = session.query(Part).filter(
            Part.active.is_(True), Part.box == box_n, Part.slot == slot_n
        )
        if exclude_id is not None:
            query = query.filter(Part.id != exclude_id)
        return query.order_by(Part.id).first()

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

    def actor(request: Request) -> tuple[int, str]:
        return int(request.session["user_id"]), str(request.session.get("username", ""))

    def parse_part_fields(n_boxes: int, name, aliases, box, slot, qty_kind, qty_count, note, polarized):
        alias_list = parse_aliases(aliases or "")
        if not str(name).strip() or not alias_list:
            return "详细名称和简称都要填。", None
        try:
            box_n = int(box)
            slot_n = int(slot)
        except (TypeError, ValueError):
            return "盒号和格号必须是数字。", None
        if box_n < 1 or box_n > n_boxes or slot_n < 1:
            return f"盒号必须在 1～{n_boxes}，格号至少为 1。", None
        if qty_kind not in {"empty", "few", "many", "exact"}:
            return "请选择数量档位。", None
        count = None
        if qty_kind == "exact":
            try:
                count = int(qty_count)
            except (TypeError, ValueError):
                return "具体数量必须是整数。", None
            if count < 0:
                return "具体数量不能小于 0。", None
        polar = polarized if isinstance(polarized, bool) else str(polarized).lower() in {"on", "true", "1"}
        return None, {
            "name": str(name).strip(),
            "aliases": ",".join(alias_list),
            "aliases_norm": aliases_norm(alias_list),
            "name_norm": normalize(str(name)),
            "box": box_n,
            "slot": slot_n,
            "qty_kind": qty_kind,
            "qty_count": count,
            "note": str(note or "").strip(),
            "polarized": polar,
        }

    @app.get("/api/parts")
    def api_list_parts(request: Request, q: str = ""):
        gate = api_login_required(request)
        if gate:
            return gate
        query = q.strip()
        with db() as session:
            n_boxes = box_count(session)
            if not query:
                return {"results": [], "boxes": list(range(1, n_boxes + 1))}
            active_parts = session.query(Part).filter(Part.active.is_(True)).all()
            results = search_parts(active_parts, query)
            return {"results": [part_result(part) for part in results], "boxes": []}

    @app.post("/api/parts")
    def api_create_part(request: Request, body: PartBody):
        gate = api_login_required(request)
        if gate:
            return gate
        if not check_csrf(request):
            return fail(400, "提交已过期，请再保存一次。")
        with db() as session:
            n_boxes = box_count(session)
            error, fields = parse_part_fields(
                n_boxes,
                body.name,
                body.aliases,
                body.box,
                body.slot,
                body.qty_kind,
                body.qty_count,
                body.note,
                body.polarized,
            )
            if error:
                return fail(400, error)
            existing = same_part(session, fields["name_norm"], fields["aliases_norm"])
            if existing:
                return fail(
                    400,
                    f"这颗料已在 {location_text(existing.box, existing.slot)}，不能重复登记。",
                )
            taken = occupied(session, fields["box"], fields["slot"])
            if taken:
                return fail(
                    400,
                    f"{location_text(fields['box'], fields['slot'])}已经有 {taken.aliases}，一格只能放一种料。",
                )
            part = Part(
                name=fields["name"],
                aliases=fields["aliases"],
                aliases_norm=fields["aliases_norm"],
                name_norm=fields["name_norm"],
                box=fields["box"],
                slot=fields["slot"],
                qty_kind=fields["qty_kind"],
                qty_count=fields["qty_count"],
                note=fields["note"],
                polarized=fields["polarized"],
                active=True,
                created_by=int(request.session["user_id"]),
            )
            session.add(part)
            session.flush()
            write_audit(
                session,
                user_id=int(request.session["user_id"]),
                username=str(request.session.get("username", "")),
                action="part.create",
                part=part,
                before=None,
            )
            session.commit()
            return JSONResponse({"id": part.id}, status_code=201)

    @app.get("/api/parts/{part_id}")
    def api_get_part(request: Request, part_id: int):
        gate = api_login_required(request)
        if gate:
            return gate
        with db() as session:
            part = session.get(Part, part_id)
            if part is None:
                return fail(404, "没有这条料。")
            return part_result(part)

    @app.put("/api/parts/{part_id}")
    def api_update_part(request: Request, part_id: int, body: PartBody):
        gate = api_login_required(request)
        if gate:
            return gate
        if not check_csrf(request):
            return fail(400, "提交已过期，请再保存一次。")
        with db() as session:
            n_boxes = box_count(session)
            part = session.get(Part, part_id)
            if part is None:
                return fail(404, "没有这条料。")
            error, fields = parse_part_fields(
                n_boxes,
                body.name,
                body.aliases,
                body.box,
                body.slot,
                body.qty_kind,
                body.qty_count,
                body.note,
                body.polarized,
            )
            if error:
                return fail(400, error)
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
            taken = occupied(session, fields["box"], fields["slot"], exclude_id=part.id)
            if taken:
                return fail(
                    400,
                    f"{location_text(fields['box'], fields['slot'])}已经有 {taken.aliases}，一格只能放一种料。",
                )
            before = snapshot(part)
            part.name = fields["name"]
            part.aliases = fields["aliases"]
            part.aliases_norm = fields["aliases_norm"]
            part.name_norm = fields["name_norm"]
            part.box = fields["box"]
            part.slot = fields["slot"]
            part.qty_kind = fields["qty_kind"]
            part.qty_count = fields["qty_count"]
            part.note = fields["note"]
            part.polarized = fields["polarized"]
            write_audit(
                session,
                user_id=int(request.session["user_id"]),
                username=str(request.session.get("username", "")),
                action="part.update",
                part=part,
                before=before,
            )
            session.commit()
            return {"id": part.id}

    @app.post("/api/parts/{part_id}/deactivate")
    def api_deactivate_part(request: Request, part_id: int):
        gate = api_login_required(request)
        if gate:
            return gate
        if not check_csrf(request):
            return fail(400, "提交已过期，请再保存一次。")
        with db() as session:
            part = session.get(Part, part_id)
            if part is None:
                return fail(404, "没有这条料。")
            before = snapshot(part)
            part.active = False
            user_id, who = actor(request)
            write_audit(
                session,
                user_id=user_id,
                username=who,
                action="part.deactivate",
                part=part,
                before=before,
            )
            session.commit()
        return Response(status_code=204)

    @app.get("/api/history")
    def api_history(request: Request, part_id: str = ""):
        gate = api_login_required(request)
        if gate:
            return gate
        with db() as session:
            query = session.query(AuditLog).order_by(AuditLog.at.desc(), AuditLog.id.desc())
            if part_id.strip().isdigit():
                query = query.filter(AuditLog.part_id == int(part_id))
            logs = query.limit(200).all()
            return {"rows": [history_row(log) for log in logs]}

    @app.get("/api/users")
    def api_users(request: Request):
        gate = api_admin_required(request)
        if gate:
            return gate
        with db() as session:
            users = session.query(User).order_by(User.id).all()
            return {
                "users": [
                    {
                        "id": user.id,
                        "username": user.username,
                        "display_name": user.display_name,
                        "role": user.role,
                        "active": user.active,
                    }
                    for user in users
                ],
                "box_count": box_count(session),
                "current_user_id": int(request.session["user_id"]),
            }

    @app.post("/api/users")
    def api_create_user(request: Request, body: UserBody):
        gate = api_admin_required(request)
        if gate:
            return gate
        if not check_csrf(request):
            return fail(400, "提交已过期，请再保存一次。")
        with db() as session:
            name = body.username.strip()
            shown = body.display_name.strip() or name
            if not valid_username(name):
                return fail(400, "用户名要 3～32 个字母、数字或下划线。")
            if len(body.password) < 8:
                return fail(400, "初始密码至少 8 位。")
            if session.query(User).filter(User.username == name).one_or_none():
                return fail(400, "这个用户名已经有了。")
            user = User(
                username=name,
                password_hash=hash_password(body.password),
                display_name=shown,
                role="member",
                active=True,
            )
            session.add(user)
            session.flush()
            user_id, who = actor(request)
            write_event(
                session,
                user_id=user_id,
                username=who,
                action="user.create",
                summary=f"开了账号 {name}",
                after={"username": name, "role": "member"},
            )
            session.commit()
            return JSONResponse({"id": user.id}, status_code=201)

    @app.post("/api/users/{user_id}/disable")
    def api_disable_user(request: Request, user_id: int):
        gate = api_admin_required(request)
        if gate:
            return gate
        if not check_csrf(request):
            return fail(400, "提交已过期，请再保存一次。")
        with db() as session:
            user = session.get(User, user_id)
            if user is None:
                return fail(404, "没有这个账号。")
            if user.id == int(request.session["user_id"]):
                return fail(400, "不能停用自己正在用的账号。")
            user.active = False
            admin_id, who = actor(request)
            write_event(
                session,
                user_id=admin_id,
                username=who,
                action="user.disable",
                summary=f"停用账号 {user.username}",
                after={"username": user.username},
            )
            session.commit()
        return Response(status_code=204)

    @app.post("/api/users/{user_id}/reset-password")
    def api_reset_password(request: Request, user_id: int, body: PasswordBody):
        gate = api_admin_required(request)
        if gate:
            return gate
        if not check_csrf(request):
            return fail(400, "提交已过期，请再保存一次。")
        with db() as session:
            user = session.get(User, user_id)
            if user is None:
                return fail(404, "没有这个账号。")
            if len(body.password) < 8:
                return fail(400, "新密码至少 8 位。")
            user.password_hash = hash_password(body.password)
            admin_id, who = actor(request)
            write_event(
                session,
                user_id=admin_id,
                username=who,
                action="user.reset_password",
                summary=f"重置了 {user.username} 的密码",
                after={"username": user.username},
            )
            session.commit()
        return Response(status_code=204)

    @app.put("/api/settings/box_count")
    def api_update_box_count(request: Request, body: BoxCountBody):
        gate = api_admin_required(request)
        if gate:
            return gate
        if not check_csrf(request):
            return fail(400, "提交已过期，请再保存一次。")
        with db() as session:
            n = parse_box_count(str(body.box_count).strip())
            if n is None:
                return fail(400, "盒数必须是 1～99 的整数。")
            old = box_count(session)
            if n < old:
                blockers = (
                    session.query(Part)
                    .filter(Part.active.is_(True), Part.box > n)
                    .order_by(Part.box, Part.slot)
                    .all()
                )
                if blockers:
                    used = "、".join(sorted({f"{p.box}号盒" for p in blockers}))
                    names = "、".join(p.aliases for p in blockers[:8])
                    return fail(
                        400,
                        f"还有启用中的料在 {used}（{names}），必须先改到合法盒号或停用再减盒。",
                    )
            row = session.get(Setting, "box_count")
            if row is None:
                row = Setting(key="box_count", value=str(n))
                session.add(row)
            else:
                row.value = str(n)
            admin_id, who = actor(request)
            write_event(
                session,
                user_id=admin_id,
                username=who,
                action="settings.update",
                summary=f"盒数 {old} → {n}",
                before={"box_count": old},
                after={"box_count": n},
            )
            session.commit()
        return Response(status_code=204)

    @app.get("/api/backup.json")
    def api_backup_json(request: Request):
        gate = api_admin_required(request)
        if gate:
            return gate
        with db() as session:
            payload = dump_backup(session)
        return JSONResponse(
            content=payload,
            headers={"Content-Disposition": 'attachment; filename="parts-dict-backup.json"'},
        )

    def persist_job(session, request: Request, title: str, filename: str, content: bytes):
        parsed = parse_bom(content, filename)
        board_title = title.strip() or Path(filename).stem[:80]
        if not board_title:
            return None, "请填一个短名称。"
        parts = session.query(Part).filter(Part.active.is_(True)).all()
        job = session.query(Job).filter(Job.title == board_title).one_or_none()
        if job is None:
            job = Job(
                title=board_title,
                source_filename=filename,
                uploaded_by=int(request.session["user_id"]),
            )
            session.add(job)
            session.flush()
        else:
            session.query(JobLine).filter(JobLine.job_id == job.id).delete(
                synchronize_session=False
            )
            job.source_filename = filename
        for line in parsed:
            part = match_part(line, parts)
            session.add(
                JobLine(
                    job_id=job.id,
                    designators=line.designators,
                    name=line.name,
                    footprint=line.footprint,
                    supplier=line.supplier,
                    quantity=line.quantity,
                    part_id=part.id if part else None,
                    skip_bin=line.skip_bin,
                    polarized_hint=line.polarized_hint,
                    warning=line.warning,
                )
            )
        user_id, who = actor(request)
        write_event(
            session,
            user_id=user_id,
            username=who,
            action="job.upload",
            summary=f"上传 {board_title}（{len(parsed)} 行）",
            after={"title": board_title, "filename": filename},
        )
        session.commit()
        return job, None

    def rematch_job_lines(session, job: Job) -> list[JobLine]:
        catalog = session.query(Part).filter(Part.active.is_(True)).all()
        lines = (
            session.query(JobLine)
            .filter(JobLine.job_id == job.id)
            .order_by(JobLine.id)
            .all()
        )
        changed = False
        for line in lines:
            parsed = ParsedLine(
                designators=line.designators,
                name=line.name,
                footprint=line.footprint,
                supplier=line.supplier,
                quantity=line.quantity,
                skip_bin=line.skip_bin,
                polarized_hint=line.polarized_hint,
                warning=line.warning,
            )
            part = match_part(parsed, catalog)
            new_id = part.id if part else None
            if line.part_id != new_id:
                line.part_id = new_id
                changed = True
        if changed:
            session.commit()
        return lines

    def job_json(session, job: Job) -> dict:
        lines = rematch_job_lines(session, job)
        part_ids = [line.part_id for line in lines if line.part_id]
        parts = {}
        if part_ids:
            parts = {
                part.id: part
                for part in session.query(Part).filter(Part.id.in_(part_ids)).all()
            }

        def public_line(line: JobLine) -> dict:
            return {
                "designators": line.designators,
                "name": line.name,
                "footprint": line.footprint,
                "warning": line.warning,
            }

        def pack(line: JobLine) -> dict:
            part = parts.get(line.part_id) if line.part_id else None
            return {
                "line": public_line(line),
                "location": location_text(part.box, part.slot) if part else "",
                "qty": qty_text(part) if part else "",
            }

        polar = [pack(line) for line in lines if line.polarized_hint and not line.skip_bin]
        grouped: dict[int, list] = {}
        for line in lines:
            if line.skip_bin or not line.part_id:
                continue
            part = parts[line.part_id]
            grouped.setdefault(part.box, []).append((part.slot, line.id, pack(line)))
        box_groups = [
            [box, [row for _, _, row in sorted(grouped[box])]] for box in sorted(grouped)
        ]
        unreg = [public_line(line) for line in lines if not line.part_id and not line.skip_bin]
        skip = [public_line(line) for line in lines if line.skip_bin]
        return {
            "job": {"id": job.id, "title": job.title, "source_filename": job.source_filename},
            "polar": polar,
            "box_groups": box_groups,
            "unreg": unreg,
            "skip": skip,
        }

    @app.get("/api/jobs")
    def api_list_jobs(request: Request):
        gate = api_login_required(request)
        if gate:
            return gate
        with db() as session:
            jobs = session.query(Job).order_by(Job.updated_at.desc(), Job.id.desc()).all()
            return {
                "jobs": [
                    {"id": job.id, "title": job.title, "source_filename": job.source_filename}
                    for job in jobs
                ]
            }

    @app.post("/api/jobs")
    async def api_upload_job(
        request: Request,
        title: str = Form(""),
        csrf_token: str = Form(""),
        file: UploadFile = File(None),
    ):
        gate = api_login_required(request)
        if gate:
            return gate
        if not check_csrf(request, csrf_token):
            return fail(400, "提交已过期，请再保存一次。")
        if file is None or not file.filename:
            return fail(400, "请用嘉立创导出的 BOM")
        content = await file.read()
        with db() as session:
            try:
                job, error = persist_job(session, request, title, file.filename, content)
            except BomError as exc:
                return fail(400, str(exc))
            if error:
                return fail(400, error)
            return JSONResponse({"id": job.id}, status_code=201)

    @app.get("/api/jobs/{job_id}")
    def api_get_job(request: Request, job_id: int):
        gate = api_login_required(request)
        if gate:
            return gate
        with db() as session:
            job = session.get(Job, job_id)
            if job is None:
                return fail(404, "没有这块板。")
            return job_json(session, job)

    assets = SPA_DIR / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="spa-assets")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        index = SPA_DIR / "index.html"
        if index.exists():
            return FileResponse(index)
        return JSONResponse({"detail": "前端未构建"}, status_code=503)

    return app


app = create_app()
