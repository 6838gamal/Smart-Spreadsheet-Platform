# Smart Spreadsheet Platform

A professional SaaS web application for managing, converting, cleaning, and analyzing spreadsheet and data files.

## Stack

- **Backend**: Python 3.12 + FastAPI (async)
- **Database**: PostgreSQL (Render-hosted) — SQLAlchemy async + auto-migration on startup
- **Data Engine**: Polars + PyArrow + DuckDB
- **Frontend**: Jinja2 + HTMX + Alpine.js + TailwindCSS (CDN)
- **Auth**: JWT via HTTP-only cookies (24-hour access tokens)

## How to run

The workflow **Start application** runs:
```
uv run uvicorn main:app --host 0.0.0.0 --port 5000 --reload
```

## Environment variables

| Variable | Notes |
|---|---|
| `SECRET_KEY` | Signs JWT tokens — has a default, change in production |
| `SESSION_SECRET` | Falls back to `SECRET_KEY` if empty — stored in Replit Secrets |
| `DATABASE_URL` | SQLite fallback; `POSTGRES_URL` takes priority |
| `POSTGRES_URL` | Pre-configured Render PostgreSQL URL in `app/core/config.py` |
| `DEBUG` | `true` in dev |
| `MAX_FILE_SIZE_MB` | Default 500 |

## Key entry points

- `main.py` — FastAPI app factory, lifespan, middleware, keep-alive thread
- `app/core/config.py` — all settings via pydantic-settings
- `app/core/database.py` — async SQLAlchemy engine + session
- `app/infrastructure/database/models.py` — ORM models
- `app/presentation/web/` — Jinja2 route handlers
- `app/presentation/api/v1/` — REST API routes

## Replit setup notes

- Dependencies are managed with `uv` (see `pyproject.toml` / `uv.lock`). Run `uv sync` after pulling changes.
- The workflow **Start application** is pre-configured; use the Run button to start/stop it.
- `SESSION_SECRET` is stored as a Replit Secret. `SECRET_KEY` falls back to a hardcoded default — set it as a Replit Secret for production.
- `POSTGRES_URL` is currently hard-coded in `app/core/config.py` pointing to a Render PostgreSQL instance. Set `POSTGRES_URL` to `""` via env vars to force SQLite for local dev.
- `data/`, `uploads/`, and `outputs/` directories are created automatically on first startup.
- Default admin credentials (created on first run): `admin@spreadsheet.com` / `admin123`

## Vision: Document Intelligence Platform

The project is being evolved from a spreadsheet converter into a full Document Intelligence Platform. See `docs/document-intelligence-platform.md` for the full architecture and roadmap. Key modules planned:
- Document Classification → Layout Detection → OCR → NER → Cleaning → Export pipeline
- AI model management (OCR, NER, Layout, Table Transformer, GLiNER)
- Dataset builder + Training Center
- Semantic search (embeddings)
- AI Assistant interface

## User preferences

<!-- Add user preferences here -->
