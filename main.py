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
import app.infrastructure.database.models_intelligence  # noqa: F401 — register intelligence ORM models

from app.jobs import job_queue as _job_queue
import app.services.pipeline.pipeline_manager  # noqa: F401 — registers "analysis" job handler

from app.presentation.web import intelligence as web_intelligence
from app.presentation.api.v1 import intelligence as api_intelligence
from app.presentation.web import search as web_search
from app.presentation.api.v1 import search as api_search
from app.presentation.api.v1 import hf_api as api_hf

from app.presentation.web import auth as web_auth
from app.presentation.web import dashboard as web_dashboard
from app.presentation.web import workspace as web_workspace
from app.presentation.web import files as web_files
from app.presentation.web import converter as web_converter
from app.presentation.web import cleaner as web_cleaner
from app.presentation.web import merger as web_merger
from app.presentation.web import logs as web_logs
from app.presentation.web import settings as web_settings
from app.presentation.web import admin as web_admin
from app.presentation.web import analytics as web_analytics
from app.presentation.web import models_ui as web_models_ui
from app.presentation.web import datasets as web_datasets

from app.presentation.api.v1 import config as api_config
from app.presentation.api.v1 import auth as api_auth
from app.presentation.api.v1 import admin as api_admin
from app.presentation.api.v1 import files as api_files
from app.presentation.api.v1 import converter as api_converter
from app.presentation.api.v1 import cleaner as api_cleaner
from app.presentation.api.v1 import analytics as api_analytics
from app.presentation.api.v1 import models_api as api_models
from app.presentation.api.v1 import datasets_api as api_datasets
from app.presentation.api.v1 import websocket as api_websocket

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


def _build_allowed_origins() -> list[str]:
    """Build the CORS allowed-origins list from the current hosting environment.

    When allow_credentials=True, browsers reject the wildcard '*' origin.
    This function collects every known public URL for this deployment so
    CORS works correctly for both the web frontend and the Flutter mobile app.
    """
    origins: set[str] = set()

    # Replit dev workspace (e.g. https://<id>.replit.dev)
    dev_domain = os.environ.get("REPLIT_DEV_DOMAIN", "").strip()
    if dev_domain:
        origins.add(f"https://{dev_domain}")

    # Replit deployed domains (comma-separated list)
    replit_domains = os.environ.get("REPLIT_DOMAINS", "").strip()
    for domain in replit_domains.split(","):
        domain = domain.strip()
        if domain:
            origins.add(f"https://{domain}")

    # Render
    render_url = os.environ.get("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
    if render_url:
        origins.add(render_url)

    # Railway
    for key in ("RAILWAY_PUBLIC_DOMAIN", "RAILWAY_STATIC_URL"):
        val = os.environ.get(key, "").strip()
        if val:
            origins.add(f"https://{val}" if not val.startswith("http") else val.rstrip("/"))

    # Fly.io
    fly_app = os.environ.get("FLY_APP_NAME", "").strip()
    if fly_app:
        origins.add(f"https://{fly_app}.fly.dev")

    # Explicit extra origins — comma-separated list (e.g. Netlify / Vercel frontends)
    # Set ALLOWED_ORIGINS="https://spreadsheet-mob1.netlify.app,https://app.example.com"
    # in your Render / Railway / Fly.io environment variables.
    extra = os.environ.get("ALLOWED_ORIGINS", "").strip()
    for origin in extra.split(","):
        origin = origin.strip().rstrip("/")
        if origin:
            origins.add(origin)

    # Explicit override (APP_URL / PUBLIC_URL / BASE_URL)
    for key in ("APP_URL", "PUBLIC_URL", "BASE_URL", "HOST_URL"):
        val = os.environ.get(key, "").strip().rstrip("/")
        if val:
            origins.add(val)

    # Known frontend deployments
    origins.add("https://spreadsheet-mob1.netlify.app")

    # Always include localhost for local development
    origins.add(f"http://localhost:{settings.PORT}")
    origins.add("http://localhost:3000")   # common Flutter web dev port
    origins.add("http://127.0.0.1:5000")

    result = sorted(origins)
    logger.info("CORS allowed origins: %s", result)
    return result


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

        # 2. DB ping — run asyncpg in a fresh event loop (thread-safe, no pool sharing)
        try:
            from app.core.config import settings as _cfg
            _raw_url = _cfg._raw_db_url
            import asyncpg as _asyncpg
            # Strip driver prefix for asyncpg's own DSN parser
            _dsn = _raw_url.replace("postgresql+asyncpg://", "postgresql://").replace("postgres+asyncpg://", "postgresql://")

            async def _pg_ping():
                _use_ssl = "sslmode=disable" not in _raw_url
                _conn = await _asyncpg.connect(
                    _dsn, timeout=10,
                    ssl="require" if _use_ssl else False,
                )
                await _conn.execute("SELECT 1")
                await _conn.close()

            _loop = asyncio.new_event_loop()
            try:
                _loop.run_until_complete(_pg_ping())
            finally:
                _loop.close()
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

    Also sets Cross-Origin-Opener-Policy: unsafe-none on all HTML pages so
    that the Google OAuth popup can communicate back with window.closed /
    window.opener without being blocked by the browser's COOP enforcement.
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
            # Allow Google OAuth popup to read window.closed on the opener.
            # Without this, COOP same-origin (injected by some hosting proxies)
            # blocks the popup ↔ opener channel and breaks the sign-in flow.
            response.headers["Cross-Origin-Opener-Policy"] = "unsafe-none"
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


async def apply_column_migrations() -> None:
    """Apply column migrations to existing tables."""
    try:
        async with engine.begin() as conn:
            # 1. تعديلات ai_model_registry
            await conn.execute(__import__("sqlalchemy").text(
                "ALTER TABLE ai_model_registry "
                "ADD COLUMN IF NOT EXISTS task_type VARCHAR(50);"
            ))
            await conn.execute(__import__("sqlalchemy").text(
                "ALTER TABLE ai_model_registry "
                "ADD COLUMN IF NOT EXISTS visible_to_users BOOLEAN DEFAULT TRUE;"
            ))
            await conn.execute(__import__("sqlalchemy").text(
                "ALTER TABLE ai_model_registry "
                "ADD COLUMN IF NOT EXISTS hf_model_id VARCHAR(200);"
            ))
            
            # 2. ✅ أعمدة التخزين إلى جدول files (الإصلاح الرئيسي)
            storage_columns = [
                ("storage_key", "VARCHAR"),
                ("is_locally_stored", "BOOLEAN DEFAULT TRUE"),
                ("last_synced_at", "TIMESTAMP"),
                ("storage_backend", "VARCHAR"),
                ("storage_bucket", "VARCHAR"),
                ("storage_object_key", "VARCHAR"),
            ]
            
            for col_name, col_type in storage_columns:
                await conn.execute(__import__("sqlalchemy").text(
                    f"ALTER TABLE files "
                    f"ADD COLUMN IF NOT EXISTS {col_name} {col_type};"
                ))
                logger.info(f"✅ Column '{col_name}' added to files")
                
            # إنشاء فهرس على storage_key لتحسين الأداء
            await conn.execute(__import__("sqlalchemy").text(
                "CREATE INDEX IF NOT EXISTS ix_files_storage_key "
                "ON files (storage_key);"
            ))
            logger.info("✅ Index created on files.storage_key")
            
            # 3. ✅ إصلاح extracted_tables - إضافة table_index
            try:
                await conn.execute(__import__("sqlalchemy").text(
                    "ALTER TABLE extracted_tables "
                    "ADD COLUMN IF NOT EXISTS table_index INTEGER;"
                ))
                logger.info("✅ Column 'table_index' added to extracted_tables")
            except Exception as e:
                logger.warning(f"⚠️ Could not add table_index column: {e}")
            
            # 4. إضافة عمود لـ speech-to-text support
            try:
                await conn.execute(__import__("sqlalchemy").text(
                    "ALTER TABLE ai_model_registry "
                    "ADD COLUMN IF NOT EXISTS languages JSONB DEFAULT '[]'::jsonb;"
                ))
                logger.info("✅ Column 'languages' added to ai_model_registry")
            except Exception as e:
                logger.warning(f"⚠️ Could not add languages column: {e}")
            
            # 5. إنشاء فهارس للعمود الجديد
            try:
                await conn.execute(__import__("sqlalchemy").text(
                    "CREATE INDEX IF NOT EXISTS ix_ai_model_registry_task_type "
                    "ON ai_model_registry (task_type);"
                ))
                logger.info("✅ Index created on ai_model_registry.task_type")
            except Exception as e:
                logger.warning(f"⚠️ Could not create index on task_type: {e}")
                
            # 6. إضافة بعض النماذج الافتراضية إذا لم تكن موجودة
            try:
                # Check if models exist
                result = await conn.execute(
                    __import__("sqlalchemy").text(
                        "SELECT COUNT(*) FROM ai_model_registry WHERE source = 'huggingface'"
                    )
                )
                count = result.scalar()
                
                if count == 0:
                    # Insert default models
                    default_models = [
                        {
                            "name": "🧠 Qwen 2.5 72B",
                            "source": "huggingface",
                            "task_type": "text2text-generation",
                            "hf_model_id": "Qwen/Qwen2.5-72B-Instruct",
                            "model_type": "chat",
                            "is_active": True,
                            "visible_to_users": True,
                            "is_default": True,
                            "languages": ["ar", "en", "fr"],
                            "description": "نموذج متقدم للدردشة والأسئلة والأجوبة"
                        },
                        {
                            "name": "🎤 Whisper Large v3",
                            "source": "huggingface",
                            "task_type": "speech-to-text",
                            "hf_model_id": "openai/whisper-large-v3",
                            "model_type": "asr",
                            "is_active": True,
                            "visible_to_users": True,
                            "is_default": True,
                            "languages": ["ar", "en", "fr", "es", "de"],
                            "description": "نموذج تحويل الصوت إلى نص متقدم"
                        },
                        {
                            "name": "📊 BM25 (بحث تقليدي)",
                            "source": "system",
                            "task_type": "search",
                            "hf_model_id": "bm25",
                            "model_type": "search",
                            "is_active": True,
                            "visible_to_users": True,
                            "is_default": False,
                            "languages": ["ar", "en"],
                            "description": "بحث تقليدي باستخدام BM25"
                        },
                        {
                            "name": "📝 Meta Llama 3 70B",
                            "source": "huggingface",
                            "task_type": "text2text-generation",
                            "hf_model_id": "meta-llama/Llama-3-70B-Instruct",
                            "model_type": "chat",
                            "is_active": True,
                            "visible_to_users": True,
                            "is_default": False,
                            "languages": ["ar", "en"],
                            "description": "نموذج Llama 3 المتقدم"
                        },
                    ]
                    
                    for model in default_models:
                        await conn.execute(
                            __import__("sqlalchemy").text("""
                                INSERT INTO ai_model_registry 
                                (name, source, task_type, hf_model_id, model_type, 
                                 is_active, visible_to_users, is_default, languages, description)
                                VALUES 
                                (:name, :source, :task_type, :hf_model_id, :model_type,
                                 :is_active, :visible_to_users, :is_default, :languages, :description)
                            """),
                            model
                        )
                    logger.info("✅ Default Hugging Face models inserted")
            except Exception as e:
                logger.warning(f"⚠️ Could not insert default models: {e}")
                
        logger.info("✅ All column migrations applied successfully")
    except Exception as exc:
        logger.warning(f"⚠️ Column migration skipped: {exc}")


def _check_storage_backend():
    """Check and log storage backend status."""
    from app.infrastructure.storage.local_storage import storage
    
    logger.info("=" * 60)
    logger.info(f"📁 STORAGE BACKEND: {storage.backend_name.upper()}")
    logger.info("=" * 60)
    
    if storage.backend_name == "local":
        logger.error("=" * 60)
        logger.error("⚠️⚠️⚠️  WARNING: USING LOCAL STORAGE  ⚠️⚠️⚠️")
        logger.error("=" * 60)
        logger.error("Files are stored on the local filesystem.")
        logger.error("ALL FILES WILL BE LOST ON SERVER RESTART!")
        logger.error("")
        logger.error("To use persistent storage, add these environment variables:")
        logger.error("  SUPABASE_URL=https://your-project.supabase.co")
        logger.error("  SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIs...")
        logger.error("  SUPABASE_STORAGE_BUCKET=files")
        logger.error("  FILE_STORAGE_BACKEND=supabase")
        logger.error("=" * 60)
    else:
        logger.info("=" * 60)
        logger.info("✅✅✅ USING SUPABASE STORAGE ✅✅✅")
        logger.info("=" * 60)
        logger.info("Files are stored in Supabase Storage.")
        logger.info("Files will survive server restarts!")
        logger.info("=" * 60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: setup on startup, teardown on shutdown."""
    # Create database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Apply column migrations
    await apply_column_migrations()

    # Ensure upload/output directories exist
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
    
    # ✅ إنشاء مجلد التخزين المحلي
    storage_dir = getattr(settings, 'STORAGE_DIR', './storage')
    os.makedirs(storage_dir, exist_ok=True)
    
    # ✅ إنشاء مجلدات المستخدمين
    try:
        for user_id in [2]:  # admin user ID
            user_dir = os.path.join(storage_dir, "uploads", str(user_id))
            os.makedirs(user_dir, exist_ok=True)
        logger.info("✅ Upload directories created")
    except Exception as e:
        logger.warning(f"⚠️ Could not create user directories: {e}")

    # Seed default admin account
    await seed_admin()

    # ✅ CHECK STORAGE BACKEND
    _check_storage_backend()

    # Start keep-alive in a daemon thread (no asyncio task — survives event-loop pauses)
    threading.Thread(target=_start_keepalive, daemon=True, name="keepalive").start()

    # Start intelligence job queue workers
    await _job_queue.start()
    logger.info("🚀 Smart Spreadsheet Platform starting on port %s", settings.PORT)
    yield
    await _job_queue.stop()
    logger.info("👋 Application shutting down")


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
        allow_origins=_build_allowed_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Static files
    app.mount("/static", StaticFiles(directory="static"), name="static")

    # Exception handlers
    setup_exception_handlers(app)

    # ── Web routes (server-rendered pages) ──────────────────────────────────────
    app.include_router(web_auth.router, tags=["web:auth"])
    app.include_router(web_workspace.router, tags=["web:workspace"])
    app.include_router(web_dashboard.router, tags=["web:dashboard"])
    app.include_router(web_intelligence.router, tags=["web:intelligence"])
    app.include_router(web_files.router, tags=["web:files"])
    app.include_router(web_converter.router, tags=["web:converter"])
    app.include_router(web_cleaner.router, tags=["web:cleaner"])
    app.include_router(web_merger.router, tags=["web:merger"])
    app.include_router(web_logs.router, tags=["web:logs"])
    app.include_router(web_settings.router, tags=["web:settings"])
    app.include_router(web_admin.router, tags=["web:admin"])
    app.include_router(web_analytics.router, tags=["web:analytics"])
    app.include_router(web_models_ui.router, tags=["web:models"])
    app.include_router(web_datasets.router, tags=["web:datasets"])
    app.include_router(web_search.router, tags=["web:search"])

    # ── API routes ──────────────────────────────────────────────────────────────
    app.include_router(api_intelligence.router, prefix="/api/v1/intelligence", tags=["api:intelligence"])
    app.include_router(api_auth.router, prefix="/api/v1/auth", tags=["api:auth"])
    app.include_router(api_files.router, prefix="/api/v1/files", tags=["api:files"])
    app.include_router(api_converter.router, prefix="/api/v1/converter", tags=["api:converter"])
    app.include_router(api_cleaner.router, prefix="/api/v1/cleaner", tags=["api:cleaner"])
    app.include_router(api_analytics.router, prefix="/api/v1/analytics", tags=["api:analytics"])
    app.include_router(api_models.router, prefix="/api/v1/models", tags=["api:models"])
    app.include_router(api_datasets.router, prefix="/api/v1/datasets", tags=["api:datasets"])
    app.include_router(api_admin.router, prefix="/api/v1/admin", tags=["api:admin"])
    app.include_router(api_config.router, tags=["api:config"])
    app.include_router(api_search.router, prefix="/api/v1/search", tags=["api:search"])
    app.include_router(api_hf.router, prefix="/api/v1/hf", tags=["api:hf"])
    app.include_router(api_websocket.router, tags=["api:websocket"])

    # ── Additional convenience endpoints ──────────────────────────────────────
    
    @app.get("/api/v1/models/available")
    async def models_available():
        """
        Alias for /api/v1/hf/models - returns available Hugging Face models.
        This makes it easier for the frontend to discover models.
        """
        try:
            # Call the HF models endpoint
            from app.presentation.api.v1.hf_api import list_hf_models
            from app.core.database import AsyncSessionLocal
            
            # We need to call it with dependencies
            async with AsyncSessionLocal() as db:
                # Get current user (or None for public access)
                result = await list_hf_models(db=db, current_user=None)
                return result
        except Exception as e:
            logger.error(f"Error in models_available: {e}")
            # Fallback: return static list
            return {
                "models": [
                    {"id": 1, "name": "🧠 Qwen 2.5 72B", "task_type": "text2text-generation", "hf_model_id": "Qwen/Qwen2.5-72B-Instruct"},
                    {"id": 2, "name": "🎤 Whisper Large v3", "task_type": "speech-to-text", "hf_model_id": "openai/whisper-large-v3"},
                    {"id": 3, "name": "📊 BM25 (بحث)", "task_type": "search", "hf_model_id": "bm25"},
                ],
                "default_model_id": 1
            }

    return app


app = create_app()


# ── Health and status endpoints ───────────────────────────────────────────────

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


@app.get("/api/v1/system/info")
async def system_info():
    """General system information."""
    from app.infrastructure.storage.local_storage import storage
    
    return JSONResponse({
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "debug": settings.DEBUG,
        "environment": os.environ.get("ENVIRONMENT", "development"),
        "storage_backend": storage.backend_name,
        "storage_backend_configured": storage.backend_name == "supabase",
        "hf_configured": bool(settings.HUGGINGFACE_TOKEN),
        "external_apis_enabled": settings.EXTERNAL_APIS_ENABLED,
        "upload_dir": settings.UPLOAD_DIR,
        "output_dir": settings.OUTPUT_DIR,
        "storage_dir": getattr(settings, 'STORAGE_DIR', './storage'),
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
