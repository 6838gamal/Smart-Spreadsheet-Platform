# Smart Spreadsheet Platform

A professional SaaS web application for managing, converting, cleaning, and analyzing spreadsheet and data files.

## Tech Stack

- **Backend**: Python 3.12 + FastAPI (async)
- **Database**: SQLite (dev) / PostgreSQL (prod) — SQLAlchemy async + auto-migration on startup
- **Data Engine**: Polars + PyArrow + DuckDB
- **Frontend**: Jinja2 + HTMX + Alpine.js + TailwindCSS
- **Auth**: JWT (HTTP-only cookies, 24-hour access tokens)

## Local Development

```bash
# Install uv (https://docs.astral.sh/uv/)
pip install uv

# Install dependencies
uv sync

# Copy and edit environment variables
cp .env.example .env

# Run the dev server
uv run uvicorn main:app --host 0.0.0.0 --port 5000 --reload
```

The app will be available at `http://localhost:5000`.

## Environment Variables

| Variable | Default | Notes |
|---|---|---|
| `SECRET_KEY` | (placeholder) | **Change in production** — signs JWT tokens |
| `SESSION_SECRET` | `""` | Falls back to `SECRET_KEY` if empty |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/app.db` | Use `postgresql://...` in prod |
| `DEBUG` | `true` | Set `false` in production |
| `PORT` | `5000` | HTTP port |
| `MAX_FILE_SIZE_MB` | `500` | Max upload size |

See `.env.example` for the full list.

## Deploy to Render

This repo includes a `render.yaml` blueprint for one-click deployment.

### Steps

1. Push this repo to GitHub.
2. Go to [dashboard.render.com](https://dashboard.render.com) → **New → Blueprint**.
3. Connect your GitHub repo — Render reads `render.yaml` and creates:
   - A **Web Service** (Docker, auto-scaled)
   - A **PostgreSQL** database (free tier)
   - All secrets auto-generated (`SECRET_KEY`, `SESSION_SECRET`)
4. Click **Apply** and wait ~3 minutes for the first build.

### Persistent File Storage

The blueprint mounts a 5 GB disk at `/app/uploads`. Processed outputs are ephemeral by default — configure an S3-compatible bucket via `OUTPUT_DIR` if you need persistence for outputs as well.

### Manual deploy (no blueprint)

If you prefer to configure manually on Render:

| Setting | Value |
|---|---|
| Runtime | Docker |
| Build Command | *(handled by Dockerfile)* |
| Start Command | *(handled by Dockerfile CMD)* |
| Port | Render injects `PORT` automatically |

Required env vars to set manually:
- `DATABASE_URL` — from your Render PostgreSQL instance (connection string)
- `SECRET_KEY` — any long random string
- `SESSION_SECRET` — any long random string
- `DEBUG` — `false`

## Docker (standalone)

```bash
docker build -t smart-spreadsheet .
docker run -p 8000:8000 \
  -e SECRET_KEY=changeme \
  -e DATABASE_URL=sqlite+aiosqlite:///./data/app.db \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/uploads:/app/uploads \
  smart-spreadsheet
```

## Supported Formats

**Import**: xlsx, xls, xlsm, xlsb, csv, tsv, txt, json, xml, yaml, parquet, feather, ods, sqlite, pdf (tables), docx (tables)

**Export**: xlsx, csv, json, xml, yaml, parquet, feather, ods, html, tsv, sqlite, docx
