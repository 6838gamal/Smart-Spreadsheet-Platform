# Smart Spreadsheet Platform — Docker image
# Uses uv for fast, reproducible dependency installs.

FROM python:3.12-slim

# System libraries required at runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

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
