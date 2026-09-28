# Smart Spreadsheet Platform — Docker image
# Uses uv for fast, reproducible dependency installs.

FROM python:3.12-slim

# System libraries required at runtime + fonts for PDF generation
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libssl-dev \
    # ─── PDF / Arabic font support ────────────────────────────
    fonts-dejavu \
    fonts-dejavu-core \
    fonts-dejavu-extra \
    fonts-liberation \
    fontconfig \
    # ─── OCR (Tesseract) — if you need img2table/pytesseract ──
    tesseract-ocr \
    tesseract-ocr-ara \
    tesseract-ocr-eng \
    tesseract-ocr-equ \
    libgl1 \
    libglib2.0-0 \
    # ─── Cairo/Pango (for PyMuPDF/cairosvg/weasyprint) ────────
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -f -v

# Copy uv binary from the official image
COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /uvx /bin/

WORKDIR /app

# Install Python dependencies (cached layer — only re-runs if lockfile changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy application source
COPY . .

# Create runtime directories (uploads/outputs/data are volume-mounted in prod)
RUN mkdir -p uploads outputs data

# Render injects PORT; fall back to 8000 for local Docker runs
EXPOSE 8000
CMD uv run uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
