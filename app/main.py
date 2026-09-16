from __future__ import annotations

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.auth import box_count, seed_admin, seed_settings, verify_password
from app.db import Base, make_engine, make_session_factory
from app.models import Part, User
from app.search import (
    QTY_LABEL,
    aliases_norm,
    location_text,
    normalize,
    parse_aliases,
    search_parts,
)

load_dotenv()

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.globals["qty_label"] = QTY_LABEL
templates.env.globals["location_text"] = location_text


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

    def login_required(request: Request):
        if request.session.get("user_id"):
            return None
        return RedirectResponse("/login", status_code=303)

    @app.get("/login", response_class=HTMLResponse)
    def login_page(request: Request):
        if request.session.get("user_id"):
            return RedirectResponse("/", status_code=303)
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": None, "csrf_token": new_csrf(request)},
        )

    @app.post("/login", response_class=HTMLResponse)
    def login_submit(
        request: Request,
        username: str = Form(""),
        password: str = Form(""),
        csrf_token: str = Form(""),
    ):
        if not valid_csrf(request, csrf_token):
            return templates.TemplateResponse(
                request,
                "login.html",
                {"error": "用户名或密码不对", "csrf_token": new_csrf(request)},
            )
        with db() as session:
            user = (
                session.query(User)
                .filter(User.username == username.strip(), User.active.is_(True))
                .one_or_none()
            )
            if user is None or not verify_password(password, user.password_hash):
                return templates.TemplateResponse(
                    request,
                    "login.html",
                    {"error": "用户名或密码不对", "csrf_token": new_csrf(request)},
                )
            request.session["user_id"] = user.id
            request.session["username"] = user.username
            request.session["display_name"] = user.display_name
            request.session["role"] = user.role
        return RedirectResponse("/", status_code=303)

    @app.get("/logout")
    def logout(request: Request):
        request.session.clear()
        return RedirectResponse("/login", status_code=303)

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request, q: str = ""):
        gate = login_required(request)
        if gate:
            return gate
        query = q.strip()
        with db() as session:
            n_boxes = box_count(session)
            results = []
            if query:
                active_parts = session.query(Part).filter(Part.active.is_(True)).all()
                results = search_parts(active_parts, query)
        return templates.TemplateResponse(
            request,
            "home.html",
            {
                "username": request.session.get("username", ""),
                "display_name": request.session.get("display_name", ""),
                "q": query,
                "results": results,
                "boxes": list(range(1, n_boxes + 1)),
            },
        )

    @app.get("/parts/new", response_class=HTMLResponse)
    def new_part(request: Request, alias: str = ""):
        gate = login_required(request)
        if gate:
            return gate
        with db() as session:
            n_boxes = box_count(session)
        return templates.TemplateResponse(
            request,
            "part_form.html",
            {
                "username": request.session.get("username", ""),
                "display_name": request.session.get("display_name", ""),
                "csrf_token": new_csrf(request),
                "error": None,
                "boxes": list(range(1, n_boxes + 1)),
                "form": {
                    "name": alias,
                    "aliases": alias,
                    "box": "1",
                    "slot": "1",
                    "qty_kind": "few",
                    "qty_count": "",
                    "note": "",
                    "polarized": False,
                },
            },
        )

    @app.post("/parts", response_class=HTMLResponse)
    def create_part(
        request: Request,
        name: str = Form(""),
        aliases: str = Form(""),
        box: str = Form(""),
        slot: str = Form(""),
        qty_kind: str = Form("few"),
        qty_count: str = Form(""),
        note: str = Form(""),
        polarized: str = Form(""),
        csrf_token: str = Form(""),
    ):
        gate = login_required(request)
        if gate:
            return gate
        with db() as session:
            n_boxes = box_count(session)
            form = {
                "name": name,
                "aliases": aliases,
                "box": box,
                "slot": slot,
                "qty_kind": qty_kind,
                "qty_count": qty_count,
                "note": note,
                "polarized": polarized == "on",
            }

            def rerender(error: str):
                return templates.TemplateResponse(
                    request,
                    "part_form.html",
                    {
                        "username": request.session.get("username", ""),
                        "display_name": request.session.get("display_name", ""),
                        "csrf_token": new_csrf(request),
                        "error": error,
                        "boxes": list(range(1, n_boxes + 1)),
                        "form": form,
                    },
                )

            if not valid_csrf(request, csrf_token):
                return rerender("提交已过期，请再保存一次。")
            alias_list = parse_aliases(aliases)
            if not name.strip() or not alias_list:
                return rerender("详细名称和简称都要填。")
            try:
                box_n = int(box)
                slot_n = int(slot)
            except ValueError:
                return rerender("盒号和格号必须是数字。")
            if box_n < 1 or box_n > n_boxes or slot_n < 1:
                return rerender(f"盒号必须在 1～{n_boxes}，格号至少为 1。")
            if qty_kind not in {"empty", "few", "many", "exact"}:
                return rerender("请选择数量档位。")
            count = None
            if qty_kind == "exact":
                try:
                    count = int(qty_count)
                except ValueError:
                    return rerender("具体数量必须是整数。")
                if count < 0:
                    return rerender("具体数量不能小于 0。")
            session.add(
                Part(
                    name=name.strip(),
                    aliases=",".join(alias_list),
                    aliases_norm=aliases_norm(alias_list),
                    name_norm=normalize(name),
                    box=box_n,
                    slot=slot_n,
                    qty_kind=qty_kind,
                    qty_count=count,
                    note=note.strip(),
                    polarized=polarized == "on",
                    active=True,
                    created_by=int(request.session["user_id"]),
                )
            )
            session.commit()
        return RedirectResponse("/", status_code=303)

    return app


app = create_app()
