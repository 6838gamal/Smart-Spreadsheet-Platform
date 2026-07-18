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

## User preferences

<!-- Add user preferences here -->
