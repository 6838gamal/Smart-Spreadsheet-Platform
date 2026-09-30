"""
Pipeline Manager — orchestrates the full document analysis flow.
Persists results to the DB and drives the Job Queue.
"""
from __future__ import annotations

import logging
import time
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.infrastructure.database.models_intelligence import (
    DocumentAnalysis, AnalysisStatus, LayoutElement as LayoutElementModel,
    ExtractedTable, ExtractedEntity, AISuggestion, ProcessingJob
)
from app.infrastructure.database.models import File
from app.services.classification.document_classifier import DocumentClassifier
from app.services.pipeline.base_pipeline import PipelineContext
from app.services.pipeline.pipelines.generic_pipeline import GenericPipeline
from app.services.pipeline.pipelines.invoice_pipeline import InvoicePipeline
from app.services.pipeline.pipelines.contract_pipeline import ContractPipeline
from app.services.pipeline.pipelines.cv_pipeline import CVPipeline
from app.services.pipeline.pipelines.bank_statement_pipeline import BankStatementPipeline
from app.jobs.job_queue import register_handler

logger = logging.getLogger(__name__)

_classifier = DocumentClassifier()

# Pipeline registry — keyed by doc_type
_PIPELINES: dict = {
    "invoice":        InvoicePipeline(),
    "receipt":        InvoicePipeline(),      # reuse invoice pipeline
    "contract":       ContractPipeline(),
    "resume":         CVPipeline(),
    "bank_statement": BankStatementPipeline(),
}
_generic_pipeline = GenericPipeline()


def _get_pipeline(doc_type: str):
    return _PIPELINES.get(doc_type, _generic_pipeline)


# ═══════════════════════════════════════════════════════════════
# Helper — download file from storage to a local temp path
# ═══════════════════════════════════════════════════════════════

async def _download_to_temp(
    db: AsyncSession,
    file_id: int,
    owner_id: Optional[int] = None,
    fallback_path: Optional[str] = None,
) -> Optional[str]:
    """
    Download file content from storage to a local temp file.

    Returns the local path on success, None on failure.
    Caller is responsible for deleting the temp file.
    """
    try:
        from app.application.files.service import FileService
        svc = FileService(db)

        # Need owner_id for authorization inside get_file_content
        if owner_id is None:
            file_row = await db.get(File, file_id)
            if not file_row:
                logger.error(f"_download_to_temp: File {file_id} not found in DB")
                return None
            owner_id = file_row.owner_id

        content = await svc.get_file_content(file_id, owner_id)
        if not content:
            logger.error(f"_download_to_temp: no content for file {file_id}")
            return None

        # Determine suffix from format
        file_row = await db.get(File, file_id)
        fmt = (file_row.format or "").lower().lstrip(".") if file_row else ""
        suffix = f".{fmt}" if fmt else ""

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.write(content)
        tmp.close()
        logger.info(f"📥 Downloaded file {file_id} to {tmp.name} ({len(content)} bytes)")
        return tmp.name

    except Exception as exc:
        logger.error(f"_download_to_temp failed for file {file_id}: {exc}")
        return None


# ── Job handler (registered with the queue) ───────────────────────────────────

@register_handler("analysis")
async def handle_analysis_job(payload: dict) -> dict:
    """Entry point called by the job worker."""
    file_id: int = payload["file_id"]
    original_path: str = payload.get("file_path", "")
    file_format: str = payload.get("file_format", "")
    analysis_id: int = payload["analysis_id"]

    async with AsyncSessionLocal() as db:
        # Mark analysis as running
        analysis = await db.get(DocumentAnalysis, analysis_id)
        if not analysis:
            raise ValueError(f"DocumentAnalysis {analysis_id} not found")

        analysis.status = AnalysisStatus.RUNNING
        analysis.updated_at = datetime.now(timezone.utc)
        await db.commit()

        # ═══════════════════════════════════════════════════════════
        # Download file locally BEFORE any processing
        # ═══════════════════════════════════════════════════════════
        local_path: Optional[str] = None
        try:
            # Get owner_id from the File row (also gives us format)
            file_row = await db.get(File, file_id)
            owner_id = file_row.owner_id if file_row else None
            if not file_format and file_row and file_row.format:
                file_format = file_row.format

            local_path = await _download_to_temp(
                db, file_id, owner_id=owner_id, fallback_path=original_path
            )
            if not local_path:
                raise RuntimeError(
                    f"Could not download file {file_id} from storage"
                )
        except Exception as dl_exc:
            logger.error(f"❌ Download failed for file {file_id}: {dl_exc}")
            analysis.status = AnalysisStatus.FAILED
            analysis.error_message = f"download failed: {dl_exc}"[:500]
            analysis.updated_at = datetime.now(timezone.utc)
            await db.commit()
            raise

        # ═══════════════════════════════════════════════════════════
        # Process using the LOCAL path
        # ═══════════════════════════════════════════════════════════
        t0 = time.monotonic()
        try:
            # ── Step 1: Classify ──────────────────────────────────────────
            text_for_classify = _quick_text(local_path, file_format)
            clf_result = _classifier.classify(text_for_classify, Path(local_path).name)

            analysis.doc_type = clf_result.doc_type
            analysis.doc_type_confidence = clf_result.confidence
            analysis.language = clf_result.language
            await db.commit()

            # ── Step 2: Run pipeline (with local path) ────────────────────
            pipeline = _get_pipeline(clf_result.doc_type)
            ctx = PipelineContext(
                file_id=file_id,
                file_path=local_path,              # ← المسار المحلي
                file_format=file_format,
                analysis_id=analysis_id,
                extra={"doc_type": clf_result.doc_type, "original_path": original_path},
            )
            ctx = pipeline.run(ctx)

            # ═══════════════════════════════════════════════════════
            # Fallback: if the pipeline produced no text, use _quick_text
            # ═══════════════════════════════════════════════════════
            raw_text = (ctx.raw_text or "").strip()
            if not raw_text:
                logger.warning(
                    f"⚠️ Pipeline '{pipeline.name}' returned no text for file {file_id}. "
                    f"Falling back to _quick_text."
                )
                raw_text = _quick_text(local_path, file_format)

            # ── Step 3: Persist results ───────────────────────────────────
            analysis.raw_text = raw_text[:50000] if raw_text else None
            analysis.language = ctx.language or analysis.language
            analysis.page_count = ctx.page_count or analysis.page_count
            analysis.has_tables = ctx.has_tables
            analysis.has_images = ctx.has_images
            analysis.pipeline_used = pipeline.name
            analysis.model_versions = {"ocr": "tesseract-5", "layout": "pdfplumber-1", "ner": "regex-1"}

            # Layout elements
            for elem in ctx.layout_elements:
                db.add(LayoutElementModel(
                    analysis_id=analysis_id,
                    page_number=elem.get("page_number", 1),
                    element_type=elem.get("element_type", "other"),
                    x1=elem.get("x1"), y1=elem.get("y1"),
                    x2=elem.get("x2"), y2=elem.get("y2"),
                    confidence=elem.get("confidence"),
                    content=elem.get("content", "")[:500] if elem.get("content") else None,
                    meta=elem.get("meta", {}),
                ))

            # Extracted tables
            for tbl in ctx.tables:
                cells_json = [
                    {"row": c.row, "col": c.col, "value": c.value,
                     "rowspan": c.rowspan, "colspan": c.colspan}
                    for c in tbl.cells
                ]
                db.add(ExtractedTable(
                    analysis_id=analysis_id,
                    page_number=tbl.page_number,
                    row_count=tbl.row_count,
                    col_count=tbl.col_count,
                    has_header=tbl.has_header,
                    has_merged_cells=tbl.has_merged_cells,
                    table_data=cells_json,
                    headers=tbl.headers,
                    confidence=tbl.confidence,
                ))

            # Entities
            for ent in ctx.entities:
                db.add(ExtractedEntity(
                    analysis_id=analysis_id,
                    entity_type=ent.get("entity_type", ""),
                    value=ent.get("value", "")[:500],
                    normalized_value=ent.get("normalized_value", "")[:500] or None,
                    confidence=ent.get("confidence"),
                    context=ent.get("context", "")[:200] or None,
                    page_number=ent.get("page_number"),
                ))

            # Suggestions
            for sug in ctx.suggestions:
                db.add(AISuggestion(
                    file_id=file_id,
                    analysis_id=analysis_id,
                    suggestion_type=sug.get("suggestion_type", ""),
                    title=sug.get("title_ar") or sug.get("title"),
                    description=sug.get("description"),
                    action_params=sug.get("action_params", {}),
                    priority=sug.get("priority", 5),
                ))

            duration_ms = int((time.monotonic() - t0) * 1000)
            analysis.processing_ms = duration_ms
            analysis.status = AnalysisStatus.COMPLETED
            analysis.updated_at = datetime.now(timezone.utc)
            await db.commit()

            # ═══════════════════════════════════════════════════════════
            # ⚠️ Step 4: Auto-index REMOVED
            # ═══════════════════════════════════════════════════════════
            # Indexing is now handled SEPARATELY by analyze_and_index_background()
            # so the frontend can display a distinct "indexing" progress bar.
            # The analysis row is left with status=COMPLETED and no chunks yet,
            # which the /status endpoint reports as "indexing" (between
            # analyzed_not_indexed and ready).
            logger.info(
                f"📄 Analysis #{analysis_id} complete — awaiting separate indexing step "
                f"(file={file_id})"
            )

            logger.info("Analysis %d completed in %dms (type=%s)", analysis_id, duration_ms, clf_result.doc_type)
            return {
                "analysis_id": analysis_id,
                "doc_type": clf_result.doc_type,
                "language": ctx.language,
                "has_tables": ctx.has_tables,
                "table_count": len(ctx.tables),
                "entity_count": len(ctx.entities),
                "duration_ms": duration_ms,
            }

        except Exception as exc:
            analysis.status = AnalysisStatus.FAILED
            analysis.error_message = str(exc)[:500]
            analysis.updated_at = datetime.now(timezone.utc)
            await db.commit()
            raise

        finally:
            # ═══════════════════════════════════════════════════════════
            # Always clean up the local temp file
            # ═══════════════════════════════════════════════════════════
            if local_path:
                try:
                    Path(local_path).unlink(missing_ok=True)
                    logger.debug(f"🧹 Cleaned up temp file {local_path}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp file {local_path}: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# Background task — used by POST /api/v1/search/files/{id}/analyze
# ═══════════════════════════════════════════════════════════════════════════

async def analyze_and_index_background(file_id: int, user_id: int) -> None:
    """
    Wrapper that runs the analysis pipeline + indexing in background.

    Pipeline stages:
        1. Create (or reuse) DocumentAnalysis  → status=PENDING
        2. Call handle_analysis_job()          → status=RUNNING → COMPLETED
        3. Run index_document()                → chunks stored → status stays COMPLETED

    The frontend sees the following transitions via /status:
        pending → analyzing → indexing → ready
    """
    logger.info(f"🚀 [BG] analyze_and_index_background: file={file_id} user={user_id}")

    analysis_id: int | None = None

    try:
        # ═══════════════════════════════════════════════════════════
        # 1. Create (or reuse) a DocumentAnalysis row
        # ═══════════════════════════════════════════════════════════
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            file = await db.get(File, file_id)
            if not file:
                logger.warning(f"⚠️ [BG] File {file_id} not found")
                return

            existing = (await db.execute(
                select(DocumentAnalysis)
                .where(DocumentAnalysis.file_id == file_id)
                .order_by(DocumentAnalysis.id.desc())
                .limit(1)
            )).scalar_one_or_none()

            if existing and existing.status == AnalysisStatus.COMPLETED and existing.raw_text:
                analysis_id = existing.id
                logger.info(f"♻️ [BG] Reusing analysis #{analysis_id}")
            else:
                analysis = DocumentAnalysis(
                    file_id=file_id,
                    user_id=user_id,
                    status=AnalysisStatus.PENDING,
                )
                db.add(analysis)
                await db.commit()
                await db.refresh(analysis)
                analysis_id = analysis.id
                logger.info(f"📝 [BG] Created DocumentAnalysis #{analysis_id}")

            file_path = file.path
            file_format = file.format

        # ═══════════════════════════════════════════════════════════
        # 2. Stage 1 — Analysis (status: analyzing)
        # ═══════════════════════════════════════════════════════════
        result = await handle_analysis_job({
            "file_id": file_id,
            "file_path": file_path,
            "file_format": file_format,
            "analysis_id": analysis_id,
        })

        logger.info(f"✅ [BG] Analysis stage done for file {file_id}: {result}")

        # ═══════════════════════════════════════════════════════════
        # 3. Stage 2 — Indexing (status: indexing)
        # ═══════════════════════════════════════════════════════════
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            analysis = await db.get(DocumentAnalysis, analysis_id)
            file = await db.get(File, file_id)

            if not analysis or not file:
                logger.warning(f"⚠️ [BG] Cannot index — analysis/file missing")
                return

            # Skip if already indexed
            from sqlalchemy import func as sql_func
            from app.infrastructure.database.models_intelligence import DocumentChunk
            existing_chunks = (await db.execute(
                select(sql_func.count(DocumentChunk.id)).where(
                    DocumentChunk.file_id == file_id,
                    DocumentChunk.user_id == user_id,
                )
            )).scalar() or 0

            if existing_chunks > 0:
                logger.info(
                    f"✅ [BG] File {file_id} already indexed "
                    f"({existing_chunks} chunks) — skipping"
                )
                return

            if not analysis.raw_text or not analysis.raw_text.strip():
                logger.warning(f"⚠️ [BG] No text to index for file {file_id}")
                return

            # ═══════════════════════════════════════════════════════
            # Run the indexing — this is what the frontend sees as "indexing"
            # ═══════════════════════════════════════════════════════
            try:
                from app.services.search.search_service import search_service

                logger.info(f"📇 [BG] Indexing file {file_id}...")
                chunk_count = await search_service.index_document(
                    db,
                    file_id=file_id,
                    analysis_id=analysis_id,
                    user_id=user_id,
                    text=analysis.raw_text,
                    doc_type=getattr(analysis, "doc_type", None),
                    language=getattr(analysis, "language", None),
                    filename=file.original_name,
                )
                logger.info(
                    f"🎉 [BG] Indexed {chunk_count} chunks for file {file_id}"
                )
            except Exception as idx_exc:
                logger.exception(
                    f"❌ [BG] Indexing failed for file {file_id}: {idx_exc}"
                )
                # Store the error so the UI can display it
                try:
                    analysis.error_message = f"indexing failed: {str(idx_exc)[:400]}"
                    await db.commit()
                except Exception:
                    pass
                return

        logger.info(f"🏁 [BG] Full pipeline complete for file {file_id}")

    except Exception as e:
        logger.exception(f"❌ [BG] analyze_and_index failed for {file_id}: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# Text extraction helper — improved for PDF, Excel, DOCX, CSV, JSON, TXT
# ═══════════════════════════════════════════════════════════════════════════

def _quick_text(file_path: str, file_format: str) -> str:
    """
    Extract text from various file formats.
    Used for classification and as a fallback when pipelines return no text.
    """
    ext = (file_format or "").lower().lstrip(".")

    # ── PDF ──
    if ext == "pdf":
        # Try pdfplumber first
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                pages = pdf.pages[:20]   # up to 20 pages
                text = "\n".join(p.extract_text() or "" for p in pages)
                if len(text.strip()) > 50:
                    return text[:50000]
        except Exception as e:
            logger.debug(f"pdfplumber failed for {file_path}: {e}")

        # Fallback: pypdf
        try:
            from pypdf import PdfReader
            reader = PdfReader(file_path)
            text = "\n".join((p.extract_text() or "") for p in reader.pages[:20])
            if text.strip():
                return text[:50000]
        except Exception as e:
            logger.debug(f"pypdf failed for {file_path}: {e}")

        # Last resort: pdf2image + pytesseract (OCR) if available
        try:
            from pdf2image import convert_from_path
            import pytesseract
            images = convert_from_path(file_path, first_page=1, last_page=5)
            text = "\n".join(pytesseract.image_to_string(img, lang="ara+eng") for img in images)
            if text.strip():
                return text[:50000]
        except Exception as e:
            logger.debug(f"OCR failed for {file_path}: {e}")

        return ""

    # ── DOCX / DOC ──
    if ext in {"docx", "doc"}:
        try:
            import docx
            doc = docx.Document(file_path)
            return "\n".join(p.text for p in doc.paragraphs)[:50000]
        except Exception:
            return ""

    # ── Excel ──
    if ext in {"xlsx", "xlsm", "xls"}:
        try:
            import openpyxl
            wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
            lines = []
            for sheet_name in wb.sheetnames[:5]:
                ws = wb[sheet_name]
                lines.append(f"=== {sheet_name} ===")
                for row in ws.iter_rows(values_only=True):
                    row_text = " | ".join(str(c) for c in row if c is not None)
                    if row_text.strip():
                        lines.append(row_text)
            return "\n".join(lines)[:50000]
        except Exception as e:
            logger.debug(f"openpyxl failed for {file_path}: {e}")
            return ""

    # ── CSV / TSV / TXT / MD ──
    if ext in {"csv", "tsv", "txt", "md", "rst"}:
        try:
            for enc in ("utf-8", "utf-8-sig", "cp1256", "latin-1"):
                try:
                    return open(file_path, encoding=enc, errors="ignore").read(50000)
                except UnicodeDecodeError:
                    continue
        except Exception:
            return ""

    # ── JSON ──
    if ext == "json":
        try:
            import json
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
            return json.dumps(data, ensure_ascii=False, indent=2)[:50000]
        except Exception:
            return ""

    # ── XML / HTML ──
    if ext in {"xml", "html", "htm"}:
        try:
            text = open(file_path, encoding="utf-8", errors="ignore").read(50000)
            import re
            text = re.sub(r"<[^>]+>", " ", text)
            return re.sub(r"\s+", " ", text).strip()[:50000]
        except Exception:
            return ""

    # ── Fallback: try plain read ──
    try:
        return open(file_path, encoding="utf-8", errors="ignore").read(50000)
    except Exception:
        return ""
