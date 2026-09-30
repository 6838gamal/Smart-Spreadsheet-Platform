"""Add progress tracking fields to document_analyses.

Revision ID: add_progress_tracking_001
Revises: <REPLACE_WITH_YOUR_LAST_REVISION>
Create Date: 2026-09-30 12:45:00.000000

Adds the following columns to `document_analyses`:
    - stage             VARCHAR(50)     NULL
    - current_step      VARCHAR(100)    NULL
    - progress_current  INTEGER         NOT NULL DEFAULT 0
    - progress_total    INTEGER         NOT NULL DEFAULT 0
    - progress_percent  DOUBLE PRECISION NOT NULL DEFAULT 0.0
    - stage_started_at  TIMESTAMPTZ     NULL
    - last_heartbeat_at TIMESTAMPTZ     NULL

Also adds a partial index on `stage` for efficient queries on
running analysis/indexing jobs.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# ─── Revision identifiers ─────────────────────────────────────────────────────

revision: str = "0004"
down_revision: "0003"   # ⚠️ ضع هنا آخر revision من `alembic heads`
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ─── Upgrade ──────────────────────────────────────────────────────────────────

def upgrade() -> None:
    """Add progress tracking columns and index."""

    # ── 1. Add columns to document_analyses ──
    op.add_column(
        "document_analyses",
        sa.Column("stage", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "document_analyses",
        sa.Column("current_step", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "document_analyses",
        sa.Column(
            "progress_current",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "document_analyses",
        sa.Column(
            "progress_total",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "document_analyses",
        sa.Column(
            "progress_percent",
            sa.Float(),
            nullable=False,
            server_default="0.0",
        ),
    )
    op.add_column(
        "document_analyses",
        sa.Column(
            "stage_started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "document_analyses",
        sa.Column(
            "last_heartbeat_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # ── 2. Add partial index on stage for running jobs ──
    op.create_index(
        "ix_document_analyses_stage",
        "document_analyses",
        ["stage"],
        unique=False,
        postgresql_where=sa.text("stage IN ('analysis', 'indexing')"),
    )

    # ── 3. Backfill existing rows (optional) ──
    # For existing completed analyses, mark stage = 'done'
    op.execute("""
        UPDATE document_analyses
        SET stage = 'done',
            current_step = 'done',
            progress_percent = 100.0
        WHERE status = 'COMPLETED'
    """)
    # For existing failed analyses, mark stage = 'failed'
    op.execute("""
        UPDATE document_analyses
        SET stage = 'failed',
            current_step = 'failed'
        WHERE status = 'FAILED'
    """)
    # For existing running/pending, mark as analysis stage
    op.execute("""
        UPDATE document_analyses
        SET stage = 'analysis',
            current_step = 'preparing'
        WHERE status IN ('PENDING', 'RUNNING')
          AND stage IS NULL
    """)


# ─── Downgrade ────────────────────────────────────────────────────────────────

def downgrade() -> None:
    """Remove progress tracking columns and index."""

    # Drop index first
    op.drop_index(
        "ix_document_analyses_stage",
        table_name="document_analyses",
    )

    # Drop columns (reverse order)
    op.drop_column("document_analyses", "last_heartbeat_at")
    op.drop_column("document_analyses", "stage_started_at")
    op.drop_column("document_analyses", "progress_percent")
    op.drop_column("document_analyses", "progress_total")
    op.drop_column("document_analyses", "progress_current")
    op.drop_column("document_analyses", "current_step")
    op.drop_column("document_analyses", "stage")
