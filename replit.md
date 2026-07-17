# Smart Spreadsheet Platform

A professional SaaS web application for managing, converting, cleaning, and analyzing Excel and data files of all formats.

## Tech Stack

- **Backend**: Python 3 + FastAPI (async)
- **Database**: SQLite (dev) / PostgreSQL (prod) via SQLAlchemy async + Alembic
- **Data Engine**: Polars (primary) + PyArrow + DuckDB
- **Frontend**: Jinja2 templates + HTMX + Alpine.js + TailwindCSS CDN
- **Architecture**: Clean Architecture (Presentation → Application → Domain → Infrastructure)

## How to Run

```bash
python main.py
```

Or via uvicorn directly:

```bash
uvicorn main:app --host 0.0.0.0 --port 5000 --reload
```

The app runs on **port 5000**.

## Project Structure

```
app/
├── core/           # Config, DB, security, exceptions, dependencies
├── domain/         # (entities reference models via infrastructure layer)
├── infrastructure/ # SQLAlchemy models, repositories, file storage
├── application/    # Use-case services per feature (auth, files, converter, cleaner, dashboard)
└── presentation/
    ├── api/v1/     # REST API endpoints
    └── web/        # Server-rendered page routes
templates/          # Jinja2 HTML templates
static/             # CSS, JS assets
uploads/            # User-uploaded files (created at runtime)
outputs/            # Processed output files (created at runtime)
data/               # SQLite database (created at runtime)
```

## Key Features (MVP)

- **Auth**: JWT-based login/register, HTTP-only cookie session
- **Dashboard**: Stats, recent files, operation history, quick actions
- **File Manager**: Upload (drag & drop / multi-file), preview, download, favorite, delete
- **Converter**: Any-format-to-any-format conversion using Polars engine
- **Data Cleaner**: Remove duplicates, trim spaces, remove empty rows/cols, fill nulls
- **Operation Logs**: Full audit trail of all operations with duration tracking

## Supported Import Formats

xlsx, xls, xlsm, xlsb, csv, tsv, txt, json, xml, yaml, parquet, feather, ods, sqlite, pdf (tables), docx (tables)

## Supported Export Formats

xlsx, csv, json, xml, yaml, parquet, feather, ods, html, tsv, sqlite, docx

## Environment Variables

See `.env.example` for all available configuration options.

## User Preferences

- Arabic RTL UI by default (configurable per user)
- Dark mode by default (toggleable)
- File uploads stored in `uploads/{user_id}/`
- Processed outputs stored in `outputs/{user_id}/`
- Do not replace external CDN/resource links with local ones — keep all external links as-is
