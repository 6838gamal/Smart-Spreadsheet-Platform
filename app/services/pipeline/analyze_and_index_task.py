"""Background task: analyze a file via the real pipeline, then index it.

Runs as a FastAPI BackgroundTask — no Celery required.
Uses the existing pipeline_manager.handle_analysis_job() for full analysis
(classify + OCR + tables + entities) and indexing.

Pipeline stages:
    Stage 1 (analyzing): handle_analysis_job() → DocumentAnalysis.status = COMPLETED
    Stage 2 (indexing):  search_service.index_document() → DocumentChunk rows

The frontend sees via /status:
    pending → analyzing → indexing → ready

✨ تحديث:
    - Heartbeat loop أثناء Stage 1 (لتجنب كشف المهمة كمعلقة)
    - Fallback إلى _quick_text إذا فشل Stage 1
    - إصلاح _mark_analysis_failed لتغيير status إلى FAILED فعليًا
    - تحديث التقدم دوريًا عبر on_progress callback
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select, func

from app.core.database import AsyncSessionLocal
from app.infrastructure.database.models import File, utcnow
from app.infrastructure.database.models_intelligence import (
    DocumentAnalysis,
    AnalysisStatus,
    DocumentChunk,
)
from app.services.search.search_service import search_service

logger = logging.getLogger(__name__)

# ⏱️ Timeouts (seconds)
ANALYSIS_TIMEOUT = 180.0   # 3 دقائق للتحليل (خفّضناها من 300)
INDEXING_TIMEOUT = 120.0   # 2 دقيقة للفهرسة

# ✨ عدد المقاطع بين كل تحديث تقدم في قاعدة البيانات
PROGRESS_UPDATE_EVERY = 5

# ✨ كل كم ثانية نُحدّث النبضة أثناء Stage 1
HEARTBEAT_INTERVAL = 15.0

# ✨ إذا لم تُنتج Stage 1 نصًا خلال هذه المدة → fallback إلى _quick_text
FALLBACK_TO_QUICK_TEXT = True


async def analyze_and_index_background(file_id: int, user_id: int) -> None:
    """
    Full pipeline in background:
        1. Load file metadata
        2. Find or create a DocumentAnalysis record
        3. Stage 1 — Analysis via handle_analysis_job() (classify + OCR + persist)
        4. Stage 2 — Indexing via search_service.index_document()
        5. Safety net — if Stage 2 failed silently, retry indexing
    """
    logger.info(
        f"🚀 [BG] Start analyze+index for file_id={file_id} user_id={user_id}"
    )

    analysis_id: int | None = None
    heartbeat_task: asyncio.Task | None = None

    try:
        # ═══════════════════════════════════════════════════════════
        # 1. Load file + find/create analysis record
        # ═══════════════════════════════════════════════════════════
        async with AsyncSessionLocal() as db:
            file = (await db.execute(
                select(File).where(File.id == file_id, File.owner_id == user_id)
            )).scalar_one_or_none()

            if not file:
                logger.warning(f"⚠️ [BG] File {file_id} not found")
                return

            analysis = (await db.execute(
                select(DocumentAnalysis)
                .where(DocumentAnalysis.file_id == file_id)
                .order_by(DocumentAnalysis.id.desc())
                .limit(1)
            )).scalar_one_or_none()

            # ── Case A: already analyzed & indexed ──
            if (
                analysis
                and analysis.status == AnalysisStatus.COMPLETED
                and analysis.raw_text
            ):
                chunks_count = await _count_chunks(db, file_id, user_id)
                if chunks_count > 0:
                    logger.info(
                        f"✅ [BG] File {file_id} already analyzed & indexed "
                        f"({chunks_count} chunks). Skipping."
                    )
                    return
                # ── Case B: analyzed but not indexed → skip to Stage 2 ──
                logger.info(
                    f"📇 [BG] File {file_id} analyzed but not indexed. "
                    f"Skipping Stage 1, going directly to indexing..."
                )
                analysis_id = analysis.id
                file_path = file.path
                file_format = file.format
                await _run_stage_2_indexing(
                    analysis_id=analysis_id,
                    file_id=file_id,
                    user_id=user_id,
                )
                return

            # ── Case C: fresh analysis needed ──
            analysis = DocumentAnalysis(
                file_id=file_id,
                user_id=user_id,
                status=AnalysisStatus.PENDING,
                stage="analysis",
                current_step="preparing",
                progress_current=0,
                progress_total=0,
                progress_percent=0.0,
                stage_started_at=utcnow(),
                last_heartbeat_at=utcnow(),
            )
            db.add(analysis)
            await db.commit()
            await db.refresh(analysis)

            analysis_id = analysis.id
            logger.info(f"📝 [BG] Created DocumentAnalysis #{analysis_id}")

            file_path = file.path
            file_format = file.format

        # ═══════════════════════════════════════════════════════════
        # ✨ 1b. ابدأ heartbeat loop في الخلفية
        # ═══════════════════════════════════════════════════════════
        heartbeat_task = asyncio.create_task(
            _heartbeat_loop(analysis_id, interval=HEARTBEAT_INTERVAL)
        )
        logger.info(
            f"💓 [BG] Heartbeat loop started for analysis #{analysis_id} "
            f"(interval={HEARTBEAT_INTERVAL}s)"
        )

        # ═══════════════════════════════════════════════════════════
        # 2. Stage 1 — Analysis (handle_analysis_job) with timeout
        # ═══════════════════════════════════════════════════════════
        from app.services.pipeline.pipeline_manager import handle_analysis_job

        payload = {
            "file_id": file_id,
            "file_path": file_path,
            "file_format": file_format,
            "analysis_id": analysis_id,
        }

        stage_1_succeeded = False
        try:
            logger.info(
                f"🔍 [BG] Stage 1 (analysis) started for file {file_id} "
                f"(timeout={ANALYSIS_TIMEOUT}s)"
            )
            result = await asyncio.wait_for(
                handle_analysis_job(payload),
                timeout=ANALYSIS_TIMEOUT,
            )
            logger.info(
                f"🎉 [BG] Stage 1 (analysis) completed for file {file_id}: "
                f"{result}"
            )
            stage_1_succeeded = True

            # ✨ تحقق أن التحليل أنتج نصًا فعلًا
            async with AsyncSessionLocal() as check_db:
                a = await check_db.get(DocumentAnalysis, analysis_id)
                if a and (not a.raw_text or not a.raw_text.strip()):
                    logger.warning(
                        f"⚠️ [BG] Stage 1 completed but raw_text is empty "
                        f"for analysis #{analysis_id}"
                    )
                    stage_1_succeeded = False

        except asyncio.TimeoutError:
            logger.error(
                f"⏱️ [BG] Stage 1 TIMEOUT after {ANALYSIS_TIMEOUT}s "
                f"for file {file_id}"
            )
        except Exception as e:
            logger.exception(
                f"❌ [BG] Stage 1 (analysis) failed for file {file_id}: {e}"
            )

        # ═══════════════════════════════════════════════════════════
        # ✨ 2b. Fallback: إذا فشل Stage 1، جرّب _quick_text
        # ═══════════════════════════════════════════════════════════
        if not stage_1_succeeded and FALLBACK_TO_QUICK_TEXT:
            logger.info(
                f"🔄 [BG] Trying fallback _quick_text for file {file_id}"
            )
            try:
                from app.services.pipeline.pipeline_manager import _quick_text

                quick_text = _quick_text(file_path, file_format)
                if quick_text and quick_text.strip():
                    async with AsyncSessionLocal() as fb_db:
                        a = await fb_db.get(DocumentAnalysis, analysis_id)
                        if a:
                            a.raw_text = quick_text
                            a.status = AnalysisStatus.COMPLETED
                            a.stage = "indexing"
                            a.current_step = "preparing"
                            a.error_message = (
                                "Stage 1 timed out — using quick_text fallback"
                            )
                            a.last_heartbeat_at = utcnow()
                            await fb_db.commit()

                    logger.info(
                        f"✅ [BG] Fallback succeeded: extracted "
                        f"{len(quick_text)} chars"
                    )
                    stage_1_succeeded = True
                else:
                    logger.warning(f"⚠️ [BG] _quick_text returned empty")
            except Exception as fb_err:
                logger.error(f"❌ [BG] Fallback failed: {fb_err}")

        # ═══════════════════════════════════════════════════════════
        # إذا فشل كل شيء → سجّل الفشل
        # ═══════════════════════════════════════════════════════════
        if not stage_1_succeeded:
            await _mark_analysis_failed(
                analysis_id,
                "analysis failed or produced no text (both main pipeline and fallback)",
            )
            return

        # ═══════════════════════════════════════════════════════════
        # 3. Stage 2 — Indexing (search_service.index_document)
        # ═══════════════════════════════════════════════════════════
        # ✨ تحديث الحالة قبل الفهرسة
        await _update_analysis_stage(
            analysis_id,
            stage="indexing",
            step="preparing",
            heartbeat=True,
        )

        await _run_stage_2_indexing(
            analysis_id=analysis_id,
            file_id=file_id,
            user_id=user_id,
        )

        logger.info(f"🏁 [BG] Full pipeline complete for file {file_id}")

    except Exception as e:
        logger.exception(f"❌ [BG] analyze_and_index failed for {file_id}: {e}")
        if analysis_id:
            await _mark_analysis_failed(
                analysis_id,
                f"pipeline crashed: {str(e)[:400]}",
            )
    finally:
        # ✨ أوقف heartbeat loop
        if heartbeat_task:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.warning(f"⚠️ [BG] Heartbeat task cleanup error: {e}")


# ── Stage 2: Indexing ─────────────────────────────────────────────────────────

async def _run_stage_2_indexing(
    analysis_id: int,
    file_id: int,
    user_id: int,
) -> None:
    """
    Stage 2 — index the analysis text into DocumentChunk.
    """
    async with AsyncSessionLocal() as db:
        file = await db.get(File, file_id)
        analysis = await db.get(DocumentAnalysis, analysis_id)

        if not file or not analysis:
            logger.warning(
                f"⚠️ [BG] Stage 2 skipped — file or analysis missing "
                f"(file={file_id}, analysis={analysis_id})"
            )
            return

        # ── Idempotency: skip if chunks already exist ──
        chunks_count = await _count_chunks(db, file_id, user_id)
        if chunks_count > 0:
            logger.info(
                f"✅ [BG] Stage 2 skipped — {chunks_count} chunks already in DB"
            )
            await _update_analysis_stage(
                analysis_id,
                stage="done",
                step="done",
                heartbeat=True,
            )
            return

        # ── Guard: must have text ──
        if not analysis.raw_text or not analysis.raw_text.strip():
            logger.warning(
                f"⚠️ [BG] Stage 2 skipped — no raw_text for analysis #{analysis_id}"
            )
            await _update_analysis_stage(
                analysis_id,
                stage="done",
                step="done",
                heartbeat=True,
            )
            return

        # ═══════════════════════════════════════════════════════════
        # ✨ callback لتحديث التقدم في DB
        # ═══════════════════════════════════════════════════════════
        async def update_progress(current: int, total: int, step: str) -> None:
            await _update_analysis_progress(
                analysis_id=analysis_id,
                stage="indexing",
                step=step,
                current=current,
                total=total,
            )

        # ── Run indexing with timeout ──
        try:
            logger.info(
                f"📇 [BG] Stage 2 (indexing) started for file {file_id} "
                f"({len(analysis.raw_text)} chars, timeout={INDEXING_TIMEOUT}s)"
            )

            await _update_analysis_stage(
                analysis_id,
                stage="indexing",
                step="preparing",
                heartbeat=True,
            )

            chunk_count = await asyncio.wait_for(
                search_service.index_document(
                    db,
                    file_id=file_id,
                    analysis_id=analysis_id,
                    user_id=user_id,
                    text=analysis.raw_text,
                    doc_type=getattr(analysis, "doc_type", None),
                    language=getattr(analysis, "language", None),
                    filename=file.original_name,
                    on_progress=update_progress,
                    progress_every=PROGRESS_UPDATE_EVERY,
                ),
                timeout=INDEXING_TIMEOUT,
            )
            logger.info(
                f"🎉 [BG] Stage 2 (indexing) complete — "
                f"{chunk_count} chunks stored for file {file_id}"
            )

            await _update_analysis_stage(
                analysis_id,
                stage="done",
                step="done",
                heartbeat=True,
            )

        except asyncio.TimeoutError:
            logger.error(
                f"⏱️ [BG] Stage 2 TIMEOUT after {INDEXING_TIMEOUT}s "
                f"for file {file_id}"
            )
            await _mark_analysis_failed(
                analysis_id,
                f"indexing timed out after {int(INDEXING_TIMEOUT)}s",
            )
            raise

        except Exception as e:
            logger.exception(
                f"❌ [BG] Stage 2 (indexing) failed for file {file_id}: {e}"
            )
            await _mark_analysis_failed(
                analysis_id,
                f"indexing failed: {str(e)[:400]}",
            )
            raise


# ═══════════════════════════════════════════════════════════════════════════════
#  ✨ Heartbeat loop — يعمل أثناء Stage 1 لتجنب كشف المهمة كمعلقة
# ═══════════════════════════════════════════════════════════════════════════════

async def _heartbeat_loop(analysis_id: int, interval: float = 15.0) -> None:
    """يُحدّث last_heartbeat_at كل `interval` ثانية حتى يُلغى."""
    try:
        while True:
            await asyncio.sleep(interval)
            await _touch_heartbeat(analysis_id)
    except asyncio.CancelledError:
        # طبيعي عند الانتهاء
        raise


# ═══════════════════════════════════════════════════════════════════════════════
#  ✨ دوال مساعدة لتحديث التقدم في قاعدة البيانات
# ═══════════════════════════════════════════════════════════════════════════════

async def _update_analysis_progress(
    analysis_id: int,
    *,
    stage: str,
    step: str,
    current: int,
    total: int,
) -> None:
    """تحديث حقول التقدم في DocumentAnalysis بجلسة جديدة."""
    try:
        async with AsyncSessionLocal() as db:
            analysis = await db.get(DocumentAnalysis, analysis_id)
            if not analysis:
                return

            analysis.stage = stage
            analysis.current_step = step
            analysis.progress_current = current
            analysis.progress_total = total
            analysis.progress_percent = (
                round(current / total * 100, 2) if total > 0 else 0.0
            )
            analysis.last_heartbeat_at = utcnow()

            if step == "preparing" and current == 0:
                analysis.stage_started_at = utcnow()

            await db.commit()

    except Exception as e:
        logger.warning(
            f"⚠️ [BG] Could not update progress for #{analysis_id} "
            f"(step={step}, {current}/{total}): {e}"
        )


async def _update_analysis_stage(
    analysis_id: int,
    *,
    stage: str,
    step: str,
    heartbeat: bool = False,
) -> None:
    """تحديث مرحلة/خطوة DocumentAnalysis."""
    try:
        async with AsyncSessionLocal() as db:
            analysis = await db.get(DocumentAnalysis, analysis_id)
            if not analysis:
                return

            analysis.stage = stage
            analysis.current_step = step
            if heartbeat:
                analysis.last_heartbeat_at = utcnow()

            if stage == "done":
                analysis.progress_percent = 100.0
                if analysis.progress_total > 0:
                    analysis.progress_current = analysis.progress_total

            await db.commit()

    except Exception as e:
        logger.warning(
            f"⚠️ [BG] Could not update stage for #{analysis_id}: {e}"
        )


async def _touch_heartbeat(analysis_id: int) -> None:
    """تحديث نبضة فقط."""
    try:
        async with AsyncSessionLocal() as db:
            analysis = await db.get(DocumentAnalysis, analysis_id)
            if analysis:
                analysis.last_heartbeat_at = utcnow()
                await db.commit()
    except Exception as e:
        logger.warning(f"⚠️ [BG] Could not touch heartbeat for #{analysis_id}: {e}")


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _count_chunks(db, file_id: int, user_id: int) -> int:
    """Count chunks for a given file/user."""
    return (await db.execute(
        select(func.count(DocumentChunk.id)).where(
            DocumentChunk.file_id == file_id,
            DocumentChunk.user_id == user_id,
        )
    )).scalar() or 0


async def _mark_analysis_failed(analysis_id: int, error_msg: str) -> None:
    """
    Safely mark an analysis as FAILED in a fresh session.

    ✨ يُغيّر status إلى FAILED + stage إلى 'failed' + يسجّل الخطأ.
    """
    try:
        async with AsyncSessionLocal() as db:
            analysis = await db.get(DocumentAnalysis, analysis_id)
            if analysis:
                analysis.status = AnalysisStatus.FAILED
                analysis.stage = "failed"
                analysis.current_step = "failed"
                analysis.error_message = error_msg[:500]
                analysis.last_heartbeat_at = utcnow()
                await db.commit()
                logger.info(
                    f"📝 [BG] Marked analysis #{analysis_id} as FAILED: "
                    f"{error_msg[:100]}"
                )
    except Exception as e:
        logger.warning(
            f"⚠️ [BG] Could not mark analysis #{analysis_id} as failed: {e}"
        )


async def _index_only(db, file, analysis, user_id: int) -> None:
    """Legacy helper — kept for backward compatibility."""
    try:
        if not analysis.raw_text:
            logger.warning(
                f"⚠️ [BG] Analysis #{analysis.id} has no raw_text — cannot index"
            )
            return

        chunk_count = await search_service.index_document(
            db,
            file_id=file.id,
            analysis_id=analysis.id,
            user_id=user_id,
            text=analysis.raw_text,
            doc_type=getattr(analysis, "doc_type", None),
            language=getattr(analysis, "language", None),
            filename=file.original_name,
        )
        logger.info(f"✅ [BG] Indexed {chunk_count} chunks for file {file.id}")
    except Exception as e:
        logger.exception(f"❌ [BG] Indexing failed for file {file.id}: {e}")
        raise
