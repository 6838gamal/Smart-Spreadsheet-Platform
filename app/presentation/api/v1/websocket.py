"""WebSocket endpoint for real-time job status updates."""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.jobs.job_queue import job_queue

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/jobs/{job_id}")
async def job_status_ws(websocket: WebSocket, job_id: str):
    """
    Stream job status events to the client.
    Sends JSON messages: {"status": "...", "job_id": "...", ...}

    Client receives updates until the job reaches a terminal state
    (completed | failed | cancelled) or the connection closes.
    """
    await websocket.accept()
    logger.debug("WS connected for job %s", job_id)

    # Immediately send current status
    current = job_queue.get_status(job_id)
    try:
        await websocket.send_json({"status": current, "job_id": job_id})
    except Exception:
        return

    if current in ("completed", "failed", "cancelled", "unknown"):
        # Job already done — send result and close
        result = job_queue.get_result(job_id)
        if result:
            await websocket.send_json({
                "status": current,
                "job_id": job_id,
                "data": result.data if result.success else None,
                "error": result.error if not result.success else None,
                "duration_ms": result.duration_ms,
            })
        await websocket.close()
        return

    # Subscribe to live updates
    q = job_queue.subscribe(job_id)
    try:
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=30.0)
            except asyncio.TimeoutError:
                # Keep-alive ping
                try:
                    await websocket.send_json({"ping": True, "job_id": job_id})
                except Exception:
                    break
                continue

            try:
                await websocket.send_json(event)
            except Exception:
                break

            # Stop streaming on terminal states
            if event.get("status") in ("completed", "failed", "cancelled"):
                break

    except WebSocketDisconnect:
        logger.debug("WS disconnected for job %s", job_id)
    finally:
        job_queue.unsubscribe(job_id, q)
        try:
            await websocket.close()
        except Exception:
            pass
