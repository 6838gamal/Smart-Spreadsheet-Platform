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

    # Security
    SECRET_KEY: str = "change-this-in-production-use-a-long-random-string"
    SESSION_SECRET: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Database
    # Priority: POSTGRES_URL (explicit override) > DATABASE_URL (Replit-injected or default)
    # Use POSTGRES_URL to point to an external PostgreSQL without touching the
    # Replit-managed DATABASE_URL key.
    POSTGRES_URL: str = ""
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/app.db"

    @property
    def _raw_db_url(self) -> str:
        """Return whichever database URL is active (POSTGRES_URL takes priority)."""
        return self.POSTGRES_URL or self.DATABASE_URL

    @property
    def async_database_url(self) -> str:
        """Return the active DATABASE_URL normalised for SQLAlchemy async drivers."""
        from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
        url = self._raw_db_url
        # Rewrite postgresql:// / postgres:// to the asyncpg dialect
        if url.startswith("postgresql://") or url.startswith("postgres://"):
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
        - SQLite: never.
        - sslmode=disable: never (explicit opt-out).
        - Any other PostgreSQL URL: yes (Render / Supabase / Railway all require it).
        """
        url = self._raw_db_url
        if "sqlite" in url:
            return False
        if "sslmode=disable" in url:
            return False
        return url.startswith("postgresql") or url.startswith("postgres")

    # File storage
    UPLOAD_DIR: str = "uploads"
    OUTPUT_DIR: str = "outputs"
    MAX_FILE_SIZE_MB: int = 500
    MAX_FILE_SIZE_BYTES: int = 500 * 1024 * 1024

    # Allowed file extensions
    ALLOWED_IMPORT_EXTENSIONS: list[str] = [
        "xlsx", "xls", "xlsm", "xlsb", "csv", "tsv", "txt",
        "json", "xml", "yaml", "yml", "sqlite", "db", "sql",
        "ods", "parquet", "feather", "docx", "pdf", "html",
    ]

    # Processing
    CHUNK_SIZE: int = 50_000       # rows per chunk for large files
    MAX_PREVIEW_ROWS: int = 1_000  # rows to show in preview
    STREAMING_THRESHOLD_MB: int = 50  # files above this use streaming

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
