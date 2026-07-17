"""
Smart Spreadsheet Platform
Entry point for the FastAPI application.
"""

import os
import asyncio
import logging
import threading
import time
import urllib.request
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

from app.core.config import settings
from app.core.database import engine, Base, AsyncSessionLocal
from app.core.exceptions import setup_exception_handlers
from app.core.logging_config import setup_logging
from app.core.security import hash_password
from app.infrastructure.database.models import User, UserRole
from app.infrastructure.repositories.user_repository import UserRepository

from app.presentation.web import auth as web_auth
from app.presentation.web import dashboard as web_dashboard
from app.presentation.web import files as web_files
from app.presentation.web import converter as web_converter
from app.presentation.web import cleaner as web_cleaner
from app.presentation.web import merger as web_merger
from app.presentation.web import logs as web_logs
from app.presentation.web import settings as web_settings
from app.presentation.web import admin as web_admin

from app.presentation.api.v1 import auth as api_auth
from app.presentation.api.v1 import files as api_files
from app.presentation.api.v1 import converter as api_converter
from app.presentation.api.v1 import cleaner as api_cleaner

setup_logging()
logger = logging.getLogger(__name__)

# ── Keep-alive global state ───────────────────────────────────────────────────
_SERVER_START = datetime.utcnow()
_keepalive_state: dict = {
    "url":         None,
    "last_ping":   None,
    "last_status": None,
    "ping_count":  0,
    "fail_count":  0,
    "history":     [],   # last 10 results
    "db_ok":       None, # None = not yet checked
}

_KEEPALIVE_INTERVAL = 7 * 60  # 7 minutes


def _detect_app_url() -> str:
    """Auto-detect the public app URL from common hosting platforms."""
    candidates = [
        os.environ.get("RENDER_EXTERNAL_URL"),
        (f"https://{os.environ['REPLIT_DEV_DOMAIN']}"
         if os.environ.get("REPLIT_DEV_DOMAIN") else None),
        (f"https://{os.environ['REPLIT_DOMAINS'].split(',')[0].strip()}"
         if os.environ.get("REPLIT_DOMAINS") else None),
        (f"https://{os.environ['RAILWAY_PUBLIC_DOMAIN']}"
         if os.environ.get("RAILWAY_PUBLIC_DOMAIN") else None),
        (f"https://{os.environ['FLY_APP_NAME']}.fly.dev"
         if os.environ.get("FLY_APP_NAME") else None),
        os.environ.get("APP_URL"),
    ]
    for url in candidates:
        if url:
            return url.rstrip("/")
    return f"http://localhost:{settings.PORT}"


def _start_keepalive() -> None:
    """Thread target: ping /health + DB every 7 min to prevent free-tier sleep."""
    time.sleep(20)  # let uvicorn finish startup first

    url = _detect_app_url() + "/health"
    _keepalive_state["url"] = url
    logger.info("Keep-alive ready — pinging every %ds → %s", _KEEPALIVE_INTERVAL, url)

    while True:
        now = datetime.utcnow()
        entry: dict = {"time": now.isoformat(), "ok": False, "status": None}

        # 1. HTTP ping
        try:
            with urllib.request.urlopen(url, timeout=15) as resp:
                entry["ok"] = True
                entry["status"] = resp.status
                _keepalive_state["ping_count"] += 1
                _keepalive_state["last_ping"] = now.isoformat()
                _keepalive_state["last_status"] = resp.status
                logger.debug("Keep-alive: server OK (HTTP %d)", resp.status)
        except Exception as exc:
            entry["error"] = str(exc)
            _keepalive_state["fail_count"] += 1
            logger.warning("Keep-alive: server ping failed: %s", exc)

        # 2. DB ping
        try:
            from sqlalchemy import text as _text
            import asyncio as _asyncio

            async def _db_ping():
                async with AsyncSessionLocal() as session:
                    await session.execute(_text("SELECT 1"))

            _asyncio.run(_db_ping())
            _keepalive_state["db_ok"] = True
            logger.debug("Keep-alive: DB OK")
        except Exception as exc:
            _keepalive_state["db_ok"] = False
            logger.warning("Keep-alive: DB ping failed: %s", exc)

        hist = _keepalive_state["history"]
        hist.append(entry)
        if len(hist) > 10:
            hist.pop(0)

        time.sleep(_KEEPALIVE_INTERVAL)


class NoCacheMiddleware(BaseHTTPMiddleware):
    """Prevent browsers from caching authenticated pages.

    Without this, pressing the browser Back button after logout shows the
    previous page from cache without hitting the server, bypassing auth.
    Static assets are excluded so they can still be cached normally.
    """

    _SKIP_PREFIXES = ("/static",)

    async def dispatch(self, request: Request, call_next) -> StarletteResponse:
        response = await call_next(request)
        if any(request.url.path.startswith(p) for p in self._SKIP_PREFIXES):
            return response
        content_type = response.headers.get("content-type", "")
        is_html = "text/html" in content_type
        is_redirect = response.status_code in (301, 302, 303, 307, 308)
        if is_html or is_redirect:
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


async def seed_admin() -> None:
    """Create the default admin user if it does not already exist."""
    async with AsyncSessionLocal() as db:
        repo = UserRepository(db)
        if not await repo.email_exists("admin@spreadsheet.com"):
            await repo.create(
                email="admin@spreadsheet.com",
                username="admin",
                hashed_password=hash_password("Spreadsheet123"),
                role=UserRole.ADMIN,
                preferences={"theme": "dark", "language": "ar"},
            )
            await db.commit()
            logger.info("Default admin user created: admin@spreadsheet.com")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: setup on startup, teardown on shutdown."""
    # Create database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Ensure upload/data directories exist
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
    os.makedirs("data", exist_ok=True)

    # Seed default admin account
    await seed_admin()

    # Start keep-alive in a daemon thread (no asyncio task — survives event-loop pauses)
    threading.Thread(target=_start_keepalive, daemon=True, name="keepalive").start()

    logger.info("Smart Spreadsheet Platform starting on port %s", settings.PORT)
    yield
    logger.info("Application shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Professional data processing and spreadsheet management platform",
        docs_url="/api/docs" if settings.DEBUG else None,
        redoc_url="/api/redoc" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # Middleware (outermost first — NoCacheMiddleware runs last so it sees
    # the final response content-type before setting headers)
    app.add_middleware(NoCacheMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Static files
    app.mount("/static", StaticFiles(directory="static"), name="static")

    # Exception handlers
    setup_exception_handlers(app)

    # Web routes (server-rendered pages)
    app.include_router(web_auth.router, tags=["web:auth"])
    app.include_router(web_dashboard.router, tags=["web:dashboard"])
    app.include_router(web_files.router, tags=["web:files"])
    app.include_router(web_converter.router, tags=["web:converter"])
    app.include_router(web_cleaner.router, tags=["web:cleaner"])
    app.include_router(web_merger.router, tags=["web:merger"])
    app.include_router(web_logs.router, tags=["web:logs"])
    app.include_router(web_settings.router, tags=["web:settings"])
    app.include_router(web_admin.router, tags=["web:admin"])

    # API routes
    app.include_router(api_auth.router, prefix="/api/v1/auth", tags=["api:auth"])
    app.include_router(api_files.router, prefix="/api/v1/files", tags=["api:files"])
    app.include_router(api_converter.router, prefix="/api/v1/converter", tags=["api:converter"])
    app.include_router(api_cleaner.router, prefix="/api/v1/cleaner", tags=["api:cleaner"])

    return app


app = create_app()


@app.get("/health")
async def health_check():
    """Public health-check endpoint — no auth required.
    Use this URL with an external uptime monitor (e.g. UptimeRobot)
    to keep the server alive: GET /health every 5 minutes.
    """
    return JSONResponse({"ok": True, "service": "smart-spreadsheet"})


@app.get("/api/v1/system/keepalive-status")
async def keepalive_status():
    """Keep-alive metrics — read-only, no auth required."""
    now = datetime.utcnow()
    uptime_secs = int((now - _SERVER_START).total_seconds())
    hours, rem = divmod(uptime_secs, 3600)
    minutes, secs = divmod(rem, 60)

    last_ping = _keepalive_state["last_ping"]
    next_ping_in: int | None = None
    if last_ping:
        try:
            elapsed = int((now - datetime.fromisoformat(last_ping)).total_seconds())
            next_ping_in = max(0, _KEEPALIVE_INTERVAL - elapsed)
        except Exception:
            pass

    return JSONResponse({
        "server_ok":       True,
        "uptime":          f"{hours:02d}:{minutes:02d}:{secs:02d}",
        "uptime_seconds":  uptime_secs,
        "ping_url":        _keepalive_state["url"],
        "ping_count":      _keepalive_state["ping_count"],
        "fail_count":      _keepalive_state["fail_count"],
        "last_ping":       last_ping,
        "last_status":     _keepalive_state["last_status"],
        "next_ping_in_sec": next_ping_in,
        "db_ok":           _keepalive_state["db_ok"],
        "history":         _keepalive_state["history"][-10:],
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info",
    )
