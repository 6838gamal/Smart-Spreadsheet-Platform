"""Data models for the internal job queue."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(order=True)
class JobEnvelope:
    """
    Priority-queue entry. Lower priority number = processed first.
    Comparison is by (priority, queued_at) so FIFO within same priority.
    """
    priority: int
    queued_at: datetime = field(compare=True, default_factory=lambda: datetime.now(timezone.utc))
    job_id: str = field(compare=False, default_factory=lambda: str(uuid.uuid4()))
    job_type: str = field(compare=False, default="")
    payload: dict[str, Any] = field(compare=False, default_factory=dict)
    db_job_id: int | None = field(compare=False, default=None)  # ID in processing_jobs table


@dataclass
class JobResult:
    job_id: str
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_ms: int = 0
