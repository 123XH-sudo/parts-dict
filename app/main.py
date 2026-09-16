from __future__ import annotations

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.auth import seed_admin, verify_password
from app.db import Base, make_engine, make_session_factory
from app.models import User

load_dotenv()

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def create_app() -> FastAPI:
    secret = os.environ.get("SECRET_KEY", "")
    if not secret:
        raise RuntimeError("必须设置 SECRET_KEY")

    engine = make_engine()
    Base.metadata.create_all(engine)
    SessionLocal = make_session_factory(engine)
    with SessionLocal() as session:
        seed_admin(session)

    app = FastAPI(title="料盒字典")
    app.add_middleware(SessionMiddleware, secret_key=secret, same_site="lax")

    def db():
        return SessionLocal()

    @app.get("/login", response_class=HTMLResponse)
    def login_page(request: Request, error: str | None = None):
        if request.session.get("user_id"):
            return RedirectResponse("/", status_code=303)
        token = secrets.token_hex(16)
        request.session["csrf_token"] = token
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": error, "csrf_token": token},
        )

    @app.post("/login", response_class=HTMLResponse)
    def login_submit(
        request: Request,
        username: str = Form(""),
        password: str = Form(""),
        csrf_token: str = Form(""),
    ):
        expected = request.session.get("csrf_token", "")
        if not expected or csrf_token != expected:
            token = secrets.token_hex(16)
            request.session["csrf_token"] = token
            return templates.TemplateResponse(
                request,
                "login.html",
                {"error": "用户名或密码不对", "csrf_token": token},
                status_code=200,
            )
        with db() as session:
            user = (
                session.query(User)
                .filter(User.username == username.strip(), User.active.is_(True))
                .one_or_none()
            )
            if user is None or not verify_password(password, user.password_hash):
                token = secrets.token_hex(16)
                request.session["csrf_token"] = token
                return templates.TemplateResponse(
                    request,
                    "login.html",
                    {"error": "用户名或密码不对", "csrf_token": token},
                    status_code=200,
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
    def home(request: Request):
        if not request.session.get("user_id"):
            return RedirectResponse("/login", status_code=303)
        return templates.TemplateResponse(
            request,
            "home.html",
            {
                "username": request.session.get("username", ""),
                "display_name": request.session.get("display_name", ""),
            },
        )

    return app


app = create_app()
