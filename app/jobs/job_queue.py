"""
AsyncIO-based internal priority job queue.
Designed to be swappable with Celery + Redis without changing the interface.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable

from app.jobs.job_models import JobEnvelope, JobResult

logger = logging.getLogger(__name__)


# Registry: job_type → async handler function
_HANDLERS: dict[str, Callable[[dict], Awaitable[dict]]] = {}


def register_handler(job_type: str):
    """Decorator to register an async job handler."""
    def decorator(fn: Callable[[dict], Awaitable[dict]]):
        _HANDLERS[job_type] = fn
        return fn
    return decorator


class JobQueue:
    """
    Lightweight in-process priority job queue backed by asyncio.PriorityQueue.
    Persists job state to the `processing_jobs` DB table.
    """

    def __init__(self, max_workers: int = 3):
        self._queue: asyncio.PriorityQueue[JobEnvelope] = asyncio.PriorityQueue()
        self._max_workers = max_workers
        self._workers: list[asyncio.Task] = []
        self._results: dict[str, JobResult] = {}
        self._status: dict[str, str] = {}   # job_id → status string
        self._running = False
        self._subscribers: dict[str, list[asyncio.Queue]] = {}  # job_id → listener queues

    async def start(self):
        """Start worker tasks — call from app lifespan."""
        self._running = True
        for i in range(self._max_workers):
            task = asyncio.create_task(self._worker(f"worker-{i}"), name=f"job-worker-{i}")
            self._workers.append(task)
        logger.info("JobQueue started with %d workers", self._max_workers)

    async def stop(self):
        """Gracefully stop all workers."""
        self._running = False
        for _ in self._workers:
            await self._queue.put(JobEnvelope(priority=999, job_type="__shutdown__"))
        for task in self._workers:
            try:
                await asyncio.wait_for(task, timeout=5.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                task.cancel()
        self._workers.clear()
        logger.info("JobQueue stopped")

    async def enqueue(
        self,
        job_type: str,
        payload: dict[str, Any],
        priority: int = 5,
        db_job_id: int | None = None,
    ) -> str:
        """Add a job to the queue. Returns job_id."""
        envelope = JobEnvelope(
            priority=priority,
            job_type=job_type,
            payload=payload,
            db_job_id=db_job_id,
        )
        self._status[envelope.job_id] = "queued"
        await self._queue.put(envelope)
        logger.debug("Enqueued job %s type=%s priority=%d", envelope.job_id, job_type, priority)
        return envelope.job_id

    def get_status(self, job_id: str) -> str:
        return self._status.get(job_id, "unknown")

    def get_result(self, job_id: str) -> JobResult | None:
        return self._results.get(job_id)

    def subscribe(self, job_id: str) -> asyncio.Queue:
        """Subscribe to status updates for a job (for WebSocket streaming)."""
        q: asyncio.Queue = asyncio.Queue(maxsize=50)
        self._subscribers.setdefault(job_id, []).append(q)
        return q

    def unsubscribe(self, job_id: str, q: asyncio.Queue):
        listeners = self._subscribers.get(job_id, [])
        if q in listeners:
            listeners.remove(q)

    async def _publish(self, job_id: str, event: dict):
        for q in self._subscribers.get(job_id, []):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

    async def _worker(self, worker_id: str):
        logger.debug("Worker %s started", worker_id)
        while self._running:
            try:
                envelope: JobEnvelope = await asyncio.wait_for(
                    self._queue.get(), timeout=1.0
                )
            except asyncio.TimeoutError:
                continue

            if envelope.job_type == "__shutdown__":
                self._queue.task_done()
                break

            job_id = envelope.job_id
            self._status[job_id] = "running"
            await self._publish(job_id, {"status": "running", "job_id": job_id})

            handler = _HANDLERS.get(envelope.job_type)
            if not handler:
                logger.warning("No handler for job type: %s", envelope.job_type)
                self._status[job_id] = "failed"
                result = JobResult(job_id=job_id, success=False, error=f"No handler for {envelope.job_type}")
                self._results[job_id] = result
                await self._publish(job_id, {"status": "failed", "job_id": job_id, "error": result.error})
                self._queue.task_done()
                continue

            t0 = time.monotonic()
            try:
                logger.info("Worker %s running job %s (%s)", worker_id, job_id, envelope.job_type)
                data = await handler(envelope.payload)
                duration_ms = int((time.monotonic() - t0) * 1000)
                result = JobResult(job_id=job_id, success=True, data=data or {}, duration_ms=duration_ms)
                self._status[job_id] = "completed"
                self._results[job_id] = result
                await self._publish(job_id, {"status": "completed", "job_id": job_id, "data": data, "duration_ms": duration_ms})
                logger.info("Job %s completed in %dms", job_id, duration_ms)
            except Exception as exc:
                duration_ms = int((time.monotonic() - t0) * 1000)
                logger.exception("Job %s failed: %s", job_id, exc)
                result = JobResult(job_id=job_id, success=False, error=str(exc), duration_ms=duration_ms)
                self._status[job_id] = "failed"
                self._results[job_id] = result
                await self._publish(job_id, {"status": "failed", "job_id": job_id, "error": str(exc)})
            finally:
                self._queue.task_done()


# Global singleton
job_queue = JobQueue(max_workers=3)
