"""
Smart Spreadsheet Platform
Entry point for the FastAPI application.
"""

import os
import logging
from contextlib import asynccontextmanager

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

    logger.info(f"Smart Spreadsheet Platform starting on port {settings.PORT}")
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info",
    )
