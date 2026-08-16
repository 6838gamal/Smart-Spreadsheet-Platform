"""
Application configuration management via pydantic-settings.
All settings can be overridden via environment variables or .env file.
"""

from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    APP_NAME: str = "Smart Spreadsheet Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    PORT: int = 5000

    # Public URL — used for server-side keep-alive self-ping.
    # Set APP_URL explicitly, or leave empty to auto-detect from the host
    # environment (Replit, Render, Railway, Fly.io, Heroku, or localhost).
    APP_URL: str = ""

    @property
    def public_url(self) -> str:
        """Return the app's own public base URL, auto-detected when APP_URL is unset."""
        import os
        if self.APP_URL:
            return self.APP_URL.rstrip("/")
        # Replit (dev workspace or deployed)
        for key in ("REPLIT_DEV_DOMAIN", "REPLIT_DOMAINS"):
            val = os.environ.get(key, "").split(",")[0].strip()
            if val:
                return f"https://{val}"
        # Render
        val = os.environ.get("RENDER_EXTERNAL_URL", "").strip()
        if val:
            return val.rstrip("/")
        # Railway
        for key in ("RAILWAY_PUBLIC_DOMAIN", "RAILWAY_STATIC_URL"):
            val = os.environ.get(key, "").strip()
            if val:
                return f"https://{val}" if not val.startswith("http") else val.rstrip("/")
        # Fly.io
        val = os.environ.get("FLY_APP_NAME", "").strip()
        if val:
            return f"https://{val}.fly.dev"
        # Heroku
        val = os.environ.get("HEROKU_APP_DEFAULT_DOMAIN_NAME", "").strip()
        if val:
            return f"https://{val}"
        # Generic fallback
        for key in ("APP_URL", "PUBLIC_URL", "BASE_URL", "HOST_URL"):
            val = os.environ.get(key, "").strip()
            if val:
                return val.rstrip("/")
        # Local fallback
        return f"http://localhost:{self.PORT}"

    # Security
    SECRET_KEY: str = "a3f8d2e1c4b7e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4"
    SESSION_SECRET: str = "s3s5i0n-s3cr3t-k3y-f0r-sm4rt-spr34dsh33t-pl4tf0rm-2024"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Database — PostgreSQL only.
    # Must be set via the DATABASE_URL environment variable (or POSTGRES_URL as alias).
    # No SQLite fallback: the app will refuse to start if neither is provided.
    POSTGRES_URL: str = ""
    DATABASE_URL: str = ""

    @property
    def _raw_db_url(self) -> str:
        """Return the active PostgreSQL URL. POSTGRES_URL takes priority over DATABASE_URL.

        Only postgresql:// and postgres:// schemes are accepted.
        Raises RuntimeError on startup if the URL is missing or uses any other scheme.
        """
        url = (self.POSTGRES_URL or self.DATABASE_URL).strip()
        if not url:
            raise RuntimeError(
                "DATABASE_URL is not set. "
                "Add a PostgreSQL connection string to your environment variables. "
                "Accepted formats: postgresql://user:pass@host:5432/dbname  "
                "or postgres://user:pass@host:5432/dbname"
            )
        _lower = url.lower()
        _pg_prefixes = ("postgresql://", "postgres://", "postgresql+asyncpg://", "postgres+asyncpg://")
        if not any(_lower.startswith(p) for p in _pg_prefixes):
            raise RuntimeError(
                f"Unsupported database URL scheme. "
                f"Only PostgreSQL is supported (postgresql:// or postgres://). "
                f"Got: {url[:40]}..."
            )
        return url

    @property
    def async_database_url(self) -> str:
        """Return the DATABASE_URL normalised for SQLAlchemy asyncpg driver."""
        from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
        url = self._raw_db_url
        # Rewrite postgresql:// / postgres:// to the asyncpg dialect
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        # asyncpg does not accept sslmode query param — strip it
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        params.pop("sslmode", None)
        clean_query = urlencode({k: v[0] for k, v in params.items()})
        url = urlunparse(parsed._replace(query=clean_query))
        return url

    @property
    def use_ssl(self) -> bool:
        """Whether to use SSL for the database connection.

        Rules:
        - sslmode=disable: never (explicit opt-out).
        - All other PostgreSQL URLs: yes (Render / Supabase / Railway / Replit all support it).
        """
        url = self._raw_db_url
        if "sslmode=disable" in url:
            return False
        return True

    # File metadata is stored in PostgreSQL. Binary objects are stored in
    # Supabase Storage. Local files are only temporary processing artifacts.
    FILE_STORAGE_BACKEND: Literal["supabase"] = "supabase"
    UPLOAD_DIR: str = "uploads"
    OUTPUT_DIR: str = "outputs"
    MAX_FILE_SIZE_MB: int = 500
    MAX_FILE_SIZE_BYTES: int = 500 * 1024 * 1024

    # Supabase Storage
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_STORAGE_BUCKET: str = "files"
    SUPABASE_STORAGE_CACHE_DIR: str = ".storage-tmp"
    SUPABASE_STORAGE_TIMEOUT_SECONDS: int = 120

    # Allowed file extensions
    ALLOWED_IMPORT_EXTENSIONS: list[str] = [
        # Spreadsheets
        "xlsx", "xls", "xlsm", "xlsb", "ods",
        # Delimited / plain text
        "csv", "tsv", "txt",
        # Structured data
        "json", "xml", "yaml", "yml",
        # Columnar / binary
        "parquet", "feather",
        # Database
        "sqlite", "db", "sql",
        # Documents
        "docx", "pdf", "pptx", "html", "htm",
        # Raster images
        "jpg", "jpeg", "png", "bmp", "gif", "webp",
        # Vector images
        "svg",
    ]

    # Processing
    CHUNK_SIZE: int = 50_000       # rows per chunk for large files
    MAX_PREVIEW_ROWS: int = 1_000  # rows to show in preview
    STREAMING_THRESHOLD_MB: int = 50  # files above this use streaming

    # ── External APIs ─────────────────────────────────────────────────────────
    # Set to true to re-enable all third-party HTTP calls (Google OAuth,
    # OpenAI, Hugging Face).  While false every outbound call returns a
    # clear 503 / disabled error — the database and all local features
    # continue to work normally.
    EXTERNAL_APIS_ENABLED: bool = False

    # Google OAuth (for regular-user login)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # OpenAI — optional; enables generative answers in the chat Q&A feature.
    # Set OPENAI_API_KEY as a Replit Secret to activate LLM-powered responses.
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"   # swap to "gpt-4o" for higher quality

    # Hugging Face — optional; enables HF Inference API for Q&A, summarization, extraction.
    # Set HUGGINGFACE_TOKEN as a Replit Secret to activate HF-powered features.
    HUGGINGFACE_TOKEN: str = ""

    # Locale defaults
    DEFAULT_LANGUAGE: Literal["ar", "en"] = "ar"
    DEFAULT_THEME: Literal["dark", "light"] = "dark"
    DEFAULT_DATE_FORMAT: str = "YYYY-MM-DD"

    @property
    def effective_secret(self) -> str:
        return self.SESSION_SECRET or self.SECRET_KEY


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
