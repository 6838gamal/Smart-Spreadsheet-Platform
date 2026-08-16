"""Converter web routes."""

import asyncio
import json
import time
import uuid
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, StreamingResponse
from app.core.templates import templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.infrastructure.database.models import User, OperationType, OperationStatus
from app.infrastructure.repositories.file_repository import FileRepository
from app.infrastructure.repositories.operation_repository import OperationRepository
from app.infrastructure.storage.local_storage import storage
from app.application.converter.service import ConverterService, EXPORT_FORMATS
from app.application.converter.engine import DataEngine, DIRECT_PAIRS
from app.application.converter.dto import ConvertRequestDTO

# ===== IMPORT Stats Service =====
from app.application.stats.service import StatsService

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Helper function to safely extract files ─────────────────────────────────

def _extract_files(file_list) -> list:
    """
    Extract File objects from a list that may contain objects or lists.
    Handles SQLAlchemy result rows safely.
    """
    result = []
    
    for item in file_list:
        # If item is a File object
        if hasattr(item, 'path') and hasattr(item, 'id'):
            result.append(item)
        # If item is a list (e.g., from SQLAlchemy row)
        elif isinstance(item, list):
            for f in item:
                if hasattr(f, 'path') and hasattr(f, 'id'):
                    result.append(f)
        # If item is a tuple (from SQLAlchemy row with selected columns)
        elif isinstance(item, tuple):
            # Try to extract File attributes from tuple
            try:
                # If tuple has 14+ elements, it's likely a File row
                if len(item) >= 14:
                    from app.infrastructure.database.models import File
                    file_obj = File(
                        id=item[0] if item[0] is not None else None,
                        name=item[1] if len(item) > 1 else None,
                        original_name=item[2] if len(item) > 2 else None,
                        path=item[3] if len(item) > 3 else None,
                        size_bytes=item[4] if len(item) > 4 else 0,
                        format=item[5] if len(item) > 5 else None,
                        mime_type=item[6] if len(item) > 6 else None,
                        status=item[7] if len(item) > 7 else None,
                        is_favorite=item[8] if len(item) > 8 else False,
                        tags=item[9] if len(item) > 9 else [],
                        meta=item[10] if len(item) > 10 else {},
                        owner_id=item[11] if len(item) > 11 else None,
                        created_at=item[12] if len(item) > 12 else None,
                        updated_at=item[13] if len(item) > 13 else None
                    )
                    result.append(file_obj)
            except Exception as e:
                logger.warning(f"Error extracting file from tuple: {e}")
        # If item is a dict
        elif isinstance(item, dict) and 'path' in item:
            try:
                from app.infrastructure.database.models import File
                file_obj = File(
                    id=item.get('id'),
                    name=item.get('name'),
                    original_name=item.get('original_name'),
                    path=item.get('path'),
                    size_bytes=item.get('size_bytes', 0),
                    format=item.get('format'),
                    mime_type=item.get('mime_type'),
                    status=item.get('status'),
                    is_favorite=item.get('is_favorite', False),
                    tags=item.get('tags', []),
                    meta=item.get('meta', {}),
                    owner_id=item.get('owner_id'),
                    created_at=item.get('created_at'),
                    updated_at=item.get('updated_at')
                )
                result.append(file_obj)
            except Exception as e:
                logger.warning(f"Error converting dict to File: {e}")
    
    return result


# ── Friendly error classifier ────────────────────────────────────────────────

def _friendly_error(raw: str) -> tuple[str, str]:
    """Return (title, detail) friendly Arabic messages for common errors."""
    r = raw.lower()
    if "unsupported format" in r or "unsupported" in r:
        return "صيغة غير مدعومة", "الصيغة المطلوبة غير مدعومة للتحويل. جرّب صيغة أخرى."
    if "not found" in r or "no such file" in r:
        return "الملف غير موجود", "لم يُعثر على الملف في المخزن. ربما تم حذفه."
    if "permission" in r or "authorization" in r:
        return "ليس لديك صلاحية", "هذا الملف لا ينتمي لحسابك."
    if "corrupt" in r or "invalid file" in r or "bad zip" in r or "zipfile" in r:
        return "الملف تالف أو غير صالح", "الملف الأصلي يبدو تالفًا أو غير مكتمل. حاول رفعه من جديد."
    if "memory" in r or "out of memory" in r:
        return "الملف كبير جداً", "الملف يتجاوز الذاكرة المتاحة. حاول بملف أصغر أو قسّمه."
    if "sheet" in r:
        return "ورقة عمل غير موجودة", "اسم ورقة العمل المدخل غير صحيح. تحقق من الاسم وأعد المحاولة."
    if "column" in r or "schema" in r or "dtype" in r:
        return "خطأ في البيانات", "البيانات لا تتوافق مع الصيغة المستهدفة. تحقق من هيكل الملف."
    if "timeout" in r:
        return "انتهت المهلة الزمنية", "استغرقت العملية وقتًا طويلاً جداً. حاول بملف أصغر."
    return "خطأ في التحويل", raw[:200] if raw else "حدث خطأ غير متوقع."


# ── Pages ────────────────────────────────────────────────────────────────────

@router.get("/converter", response_class=HTMLResponse)
async def converter_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    file_repo = FileRepository(db)
    all_files = await file_repo.get_by_owner(current_user.id, limit=100)
    
    # Safely extract File objects from the result
    extracted_files = _extract_files(all_files)
    
    # Only show files that still exist on disk; silently skip orphaned DB records
    files = []
    for f in extracted_files:
        if hasattr(f, 'path') and f.path:
            try:
                if Path(f.path).exists():
                    files.append(f)
            except Exception as e:
                logger.warning(f"Error checking file {getattr(f, 'id', 'unknown')}: {e}")
    
    # ===== FIX: Get user stats =====
    try:
        stats_service = StatsService(db)
        stats = await stats_service.get_user_stats(current_user.id)
    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        # Provide fallback empty stats
        stats = {
            "total_files": 0,
            "total_size_human": "0 B",
            "total_operations": 0,
            "favorites": [],
            "recent_files": []
        }
    
    return templates.TemplateResponse(
        request,
        "workspace/index.html",
        {
            "user": current_user,
            "files": files,
            "export_formats": EXPORT_FORMATS,
            "current_page": "converter",
            "lang": current_user.default_lang,
            "stats": stats,  # <-- ADDED: Pass stats to template
        },
    )


# ── Sheet names endpoint ─────────────────────────────────────────────────────

@router.get("/converter/sheets/{file_id}")
async def get_file_sheets(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the list of worksheet names for an Excel file (JSON)."""
    from fastapi.responses import JSONResponse
    file_repo = FileRepository(db)
    f = await file_repo.get_by_id(file_id)
    if not f or f.owner_id != current_user.id:
        return JSONResponse({"sheets": []})
    fmt = f.format.lower().lstrip(".")
    engine = DataEngine()
    loop = asyncio.get_event_loop()
    try:
        sheets = await loop.run_in_executor(None, lambda: engine.get_excel_sheets(f.path, fmt))
    except Exception:
        sheets = []
    return JSONResponse({"sheets": sheets})


# ── Preview endpoint (HTMX fragment) ────────────────────────────────────────

@router.get("/converter/preview/{file_id}", response_class=HTMLResponse)
async def preview_file(
    file_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    file_repo = FileRepository(db)
    f = await file_repo.get_by_id(file_id)
    if not f or f.owner_id != current_user.id:
        return HTMLResponse("")

    fmt = f.format.lower().lstrip(".")
    # Non-tabular formats — just show metadata card
    non_tabular = {"jpg", "jpeg", "png", "bmp", "gif", "webp", "svg", "pdf"}
    if fmt in non_tabular:
        return HTMLResponse(f"""
        <div class="p-4 bg-slate-50 dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700 text-sm text-slate-500 dark:text-slate-400 flex items-center gap-3">
          <svg class="w-6 h-6 flex-shrink-0 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
          </svg>
          <div>
            <p class="font-medium text-slate-700 dark:text-slate-300">{f.original_name}</p>
            <p class="text-xs mt-0.5">{f.size_human} · صيغة {fmt.upper()} — لا تتوفر معاينة جدولية لهذا النوع</p>
          </div>
        </div>""")

    loop = asyncio.get_event_loop()
    engine = DataEngine()
    try:
        data = await loop.run_in_executor(None, lambda: engine.preview(f.path, fmt, 8))
    except Exception as exc:
        return HTMLResponse(f"""
        <div class="p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700/50 rounded-xl text-sm text-amber-700 dark:text-amber-400">
          تعذّرت المعاينة: {exc}
        </div>""")

    if data.get("error"):
        return HTMLResponse(f"""
        <div class="p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700/50 rounded-xl text-sm text-amber-700 dark:text-amber-400">
          تعذّرت المعاينة: {data['error']}
        </div>""")

    cols = data["columns"]
    rows = data["rows"]
    total_rows = data["total_rows"]
    total_cols = data["total_cols"]

    if not cols:
        return HTMLResponse("""
        <div class="p-3 text-sm text-slate-400 text-center">الملف فارغ أو لا يحتوي بيانات</div>""")

    # Build header cells
    ths = "".join(
        f'<th class="px-3 py-2 text-start text-xs font-semibold text-slate-500 dark:text-slate-400 whitespace-nowrap border-b border-slate-200 dark:border-slate-700">{c}</th>'
        for c in cols
    )
    # Build data rows
    trs = ""
    for i, row in enumerate(rows):
        bg = "bg-white dark:bg-slate-800" if i % 2 == 0 else "bg-slate-50/60 dark:bg-slate-800/40"
        tds = ""
        for c in cols:
            cell = str(row.get(c, ""))
            short = cell[:60]
            tds += (
                f'<td class="px-3 py-1.5 text-xs text-slate-600 dark:text-slate-300'
                f' whitespace-nowrap max-w-[180px] truncate" title="{cell}">{short}</td>'
            )
        trs += f'<tr class="{bg}">{tds}</tr>'

    shown = len(rows)
    more_label = f"· يُعرض {shown} من {total_rows:,} صف" if total_rows > shown else f"· {total_rows:,} صف"

    return HTMLResponse(f"""
    <div class="space-y-2">
      <div class="flex items-center justify-between text-xs text-slate-400 dark:text-slate-500 px-0.5">
        <span class="font-medium text-slate-600 dark:text-slate-300">معاينة: {f.original_name}</span>
        <span>{total_cols} عمود {more_label}</span>
      </div>
      <div class="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700 max-h-52">
        <table class="w-full text-sm border-collapse">
          <thead class="bg-slate-50 dark:bg-slate-800/80 sticky top-0"><tr>{ths}</tr></thead>
          <tbody>{trs}</tbody>
        </table>
      </div>
    </div>""")


# ── SSE conversion stream ────────────────────────────────────────────────────

@router.get("/converter/convert-sse")
async def convert_sse(
    request: Request,
    file_id: int = Query(...),
    target_format: str = Query(...),
    sheet: str = Query(""),
    sheets: list[str] = Query([]),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    def _sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    async def stream():
        loop = asyncio.get_event_loop()
        engine = DataEngine()
        file_repo = FileRepository(db)
        op_repo = OperationRepository(db)
        target_fmt = target_format.lower()

        yield _sse("progress", {"pct": 8, "step": "validation", "msg": "التحقق من البيانات…"})
        await asyncio.sleep(0)

        # --- Validate ---
        try:
            if target_fmt not in EXPORT_FORMATS:
                yield _sse("done", {"ok": False, "title": "صيغة غير مدعومة",
                                    "detail": f"الصيغة .{target_fmt} غير متاحة للتصدير."})
                return

            f = await file_repo.get_by_id(file_id)
            if not f:
                yield _sse("done", {"ok": False, "title": "الملف غير موجود",
                                    "detail": "لم يُعثر على الملف. ربما تم حذفه."})
                return
            if f.owner_id != current_user.id:
                yield _sse("done", {"ok": False, "title": "ليس لديك صلاحية",
                                    "detail": "هذا الملف لا ينتمي لحسابك."})
                return
        except Exception as exc:
            t, d = _friendly_error(str(exc))
            yield _sse("done", {"ok": False, "title": t, "detail": d})
            return

        src_fmt   = f.format.lower().lstrip(".")
        is_direct = (src_fmt, target_fmt) in DIRECT_PAIRS

        # Decide conversion mode
        selected_sheets = [s for s in sheets if s]  # non-empty strings only
        is_excel_src    = src_fmt in {"xlsx", "xls", "xlsm", "xlsb", "ods"}
        is_pdf_src      = src_fmt == "pdf"
        multi_sheet_mode = is_excel_src and len(selected_sheets) > 1
        pdf_pages_mode   = is_pdf_src and target_fmt == "xlsx"

        # --- Log operation ---
        op = await op_repo.create(
            type=OperationType.CONVERT,
            user_id=current_user.id,
            file_id=f.id,
            input_path=f.path,
            params={"file_id": file_id, "target_format": target_fmt,
                    "sheet": sheet, "sheets": selected_sheets},
        )
        t0 = time.time()

        # --- Read ---
        yield _sse("progress", {"pct": 28, "step": "reading", "msg": f"جاري قراءة {f.original_name}…"})
        await asyncio.sleep(0)

        # Abort early if the client already disconnected
        if await request.is_disconnected():
            await op_repo.mark_complete(op, OperationStatus.FAILED, error="client disconnected",
                                        duration_ms=int((time.time() - t0) * 1000))
            return

        _TIMEOUT = 300  # 5 minutes max per heavy step

        try:
            if is_direct:
                df = None
                sheets_dict = None
            elif multi_sheet_mode:
                df = None
                sheets_dict = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: engine.read_all_sheets(f.path, src_fmt, selected_sheets),
                    ),
                    timeout=_TIMEOUT,
                )
            elif pdf_pages_mode:
                df = None
                sheets_dict = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: engine.read_pdf_pages(f.path),
                    ),
                    timeout=_TIMEOUT,
                )
            else:
                sheets_dict = None
                df = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: engine.read(f.path, src_fmt,
                                            sheet=selected_sheets[0] if selected_sheets else (sheet or None)),
                    ),
                    timeout=_TIMEOUT,
                )
        except asyncio.TimeoutError:
            duration_ms = int((time.time() - t0) * 1000)
            await op_repo.mark_complete(op, OperationStatus.FAILED, error="timeout reading file",
                                        duration_ms=duration_ms)
            yield _sse("done", {"ok": False, "title": "انتهت المهلة الزمنية",
                                "detail": "استغرقت قراءة الملف وقتاً طويلاً جداً. حاول بملف أصغر."})
            return
        except Exception as exc:
            t, d = _friendly_error(str(exc))
            duration_ms = int((time.time() - t0) * 1000)
            await op_repo.mark_complete(op, OperationStatus.FAILED, error=str(exc), duration_ms=duration_ms)
            yield _sse("done", {"ok": False, "title": t, "detail": d})
            return

        if df is not None:
            rows_count, cols_count = df.shape
        elif sheets_dict:
            rows_count = sum(d.shape[0] for d in sheets_dict.values())
            cols_count = max((d.shape[1] for d in sheets_dict.values()), default=0)
        else:
            rows_count = cols_count = 0

        # --- Convert ---
        yield _sse("progress", {"pct": 62, "step": "converting",
                                 "msg": f"جاري التحويل إلى .{target_fmt.upper()}…"})
        await asyncio.sleep(0)

        # Abort if client left before the heavy conversion step
        if await request.is_disconnected():
            await op_repo.mark_complete(op, OperationStatus.FAILED, error="client disconnected",
                                        duration_ms=int((time.time() - t0) * 1000))
            return

        stem = Path(f.original_name).stem
        uid  = uuid.uuid4().hex[:6]

        # Multi-sheet → zip for non-xlsx/pdf targets
        if (multi_sheet_mode or pdf_pages_mode) and target_fmt not in {"xlsx", "pdf"}:
            out_ext  = "zip"
        else:
            out_ext  = target_fmt

        out_name = f"{stem}_{uid}.{out_ext}"
        out_path = storage.get_output_path(current_user.id, out_name)

        # Detect same-format pass-through (preserves everything: charts, formulas, macros)
        same_fmt = (src_fmt == target_fmt or
                    (src_fmt in {"xlsx", "xlsm", "xlsb", "xls"} and target_fmt == "xlsx"))

        async def _run(fn):
            """Run a synchronous callable in the thread pool with a 5-minute timeout."""
            try:
                return await asyncio.wait_for(
                    loop.run_in_executor(None, fn),
                    timeout=_TIMEOUT,
                )
            except asyncio.TimeoutError:
                raise TimeoutError("انتهت المهلة الزمنية أثناء التحويل")

        try:
            if same_fmt and not multi_sheet_mode:
                # Direct file copy — zero data loss
                await _run(lambda: engine.copy_preserve(f.path, str(out_path)))
                actual_path = str(out_path)
                actual_name = out_name
            elif is_direct:
                actual_path = await _run(
                    lambda: engine.convert_direct(f.path, src_fmt, str(out_path), target_fmt)
                )
                actual_name = Path(actual_path).name
            elif (multi_sheet_mode or pdf_pages_mode) and sheets_dict:
                if target_fmt == "xlsx":
                    await _run(lambda: engine.write_excel_multi_sheet(sheets_dict, str(out_path)))
                    actual_path = str(out_path)
                elif target_fmt == "pdf":
                    _sp, _sf = f.path, src_fmt
                    await _run(lambda: engine.write_pdf_multi_sheet_rich(
                        sheets_dict, str(out_path), _sp, _sf
                    ))
                    actual_path = str(out_path)
                else:
                    actual_path = await _run(
                        lambda: engine.write_zip_multi_sheet(sheets_dict, str(out_path), target_fmt)
                    )
                actual_name = Path(actual_path).name
            else:
                # Single-sheet: use rich write for pdf/html targets
                _sp, _sf, _sh = f.path, src_fmt, (selected_sheets[0] if selected_sheets else sheet or None)
                if target_fmt in {"pdf", "html", "htm"}:
                    await _run(lambda: engine.write_rich(
                        df, str(out_path), target_fmt,
                        src_path=_sp, src_fmt=_sf, sheet_name=_sh,
                    ))
                else:
                    await _run(lambda: engine.write(df, str(out_path), target_fmt))
                actual_path = str(out_path)
                actual_name = out_name
        except TimeoutError as exc:
            duration_ms = int((time.time() - t0) * 1000)
            await op_repo.mark_complete(op, OperationStatus.FAILED, error=str(exc), duration_ms=duration_ms)
            yield _sse("done", {"ok": False, "title": "انتهت المهلة الزمنية",
                                "detail": "استغرق التحويل وقتاً طويلاً جداً. حاول بملف أصغر أو صيغة أخرى."})
            return
        except Exception as exc:
            t, d = _friendly_error(str(exc))
            duration_ms = int((time.time() - t0) * 1000)
            await op_repo.mark_complete(op, OperationStatus.FAILED, error=str(exc), duration_ms=duration_ms)
            yield _sse("done", {"ok": False, "title": t, "detail": d})
            return

        # --- Save & finish ---
        yield _sse("progress", {"pct": 90, "step": "saving", "msg": "جاري حفظ الملف الناتج…"})
        await asyncio.sleep(0)

        duration_ms = int((time.time() - t0) * 1000)
        await op_repo.mark_complete(
            op, OperationStatus.SUCCESS,
            result={"rows": rows_count, "columns": cols_count, "output": actual_path},
            output_path=actual_path,
            duration_ms=duration_ms,
        )

        yield _sse("done", {
            "ok": True,
            "filename": actual_name,
            "rows": rows_count,
            "cols": cols_count,
            "duration_ms": duration_ms,
            "src_name": f.original_name,
            "target_fmt": target_fmt.upper(),
        })

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── Legacy POST (non-JS fallback) ────────────────────────────────────────────

@router.post("/converter/convert")
async def do_convert(
    request: Request,
    file_id: int = Form(...),
    target_format: str = Form(...),
    sheet: str = Form(""),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        svc = ConverterService(db)
        result = await svc.convert(
            ConvertRequestDTO(file_id=file_id, target_format=target_format, sheet=sheet or None),
            current_user.id,
        )
        if request.headers.get("HX-Request"):
            return HTMLResponse(f"""
            <div class="p-4 bg-green-900/40 border border-green-500/30 rounded-xl text-green-300">
                <p class="font-semibold mb-2">✓ تم التحويل بنجاح</p>
                <p class="text-sm mb-3">{result.rows:,} صف × {result.columns} عمود · {result.duration_ms}ms</p>
                <a href="/converter/download/{result.output_filename}"
                   class="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-white text-sm font-medium">
                   تحميل {result.output_filename}
                </a>
            </div>""")
        return RedirectResponse(url="/converter", status_code=302)
    except Exception as e:
        if request.headers.get("HX-Request"):
            return HTMLResponse(
                f'<div class="p-4 bg-red-900/40 border border-red-500/30 rounded-xl text-red-300">خطأ: {e}</div>',
                status_code=400,
            )
        return RedirectResponse(url="/converter", status_code=302)


# ── Download ─────────────────────────────────────────────────────────────────

@router.get("/converter/download/{filename}")
async def download_converted(
    filename: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.core.config import settings
    path = Path(settings.OUTPUT_DIR) / str(current_user.id) / filename
    if not path.exists():
        return RedirectResponse(url="/converter", status_code=302)
    return FileResponse(str(path), filename=filename)
