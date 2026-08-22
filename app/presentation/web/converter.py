"""Converter web routes."""

import asyncio
import json
import time
import uuid
import logging
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, Depends, Request, Form, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, StreamingResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.templates import templates, get_texts
from app.infrastructure.database.models import User, File, OperationLog, OperationType, OperationStatus
from app.infrastructure.repositories.file_repository import FileRepository
from app.infrastructure.repositories.operation_repository import OperationRepository
from app.infrastructure.storage.local_storage import storage
from app.application.converter.service import ConverterService, EXPORT_FORMATS
from app.application.converter.engine import DataEngine, DIRECT_PAIRS
from app.application.converter.dto import ConvertRequestDTO
from app.application.files.service import FileService

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Helper functions ──────────────────────────────────────────────

def _extract_files(file_list) -> list:
    """Extract File objects from a list that may contain objects or lists."""
    result = []
    
    for item in file_list:
        if hasattr(item, 'path') and hasattr(item, 'id'):
            result.append(item)
        elif isinstance(item, list):
            for f in item:
                if hasattr(f, 'path') and hasattr(f, 'id'):
                    result.append(f)
        elif isinstance(item, tuple):
            try:
                if len(item) >= 14:
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
        elif isinstance(item, dict) and 'path' in item:
            try:
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


async def get_user_stats(db: AsyncSession, user_id: int) -> dict:
    """Get user statistics directly from database."""
    try:
        files_query = select(func.count()).select_from(File).where(File.owner_id == user_id)
        total_files = await db.scalar(files_query) or 0
        
        size_query = select(func.sum(File.size_bytes)).where(File.owner_id == user_id)
        total_bytes = await db.scalar(size_query) or 0
        
        if total_bytes < 1024:
            total_size_human = f"{total_bytes} B"
        elif total_bytes < 1024 * 1024:
            total_size_human = f"{total_bytes / 1024:.1f} KB"
        elif total_bytes < 1024 * 1024 * 1024:
            total_size_human = f"{total_bytes / (1024 * 1024):.1f} MB"
        else:
            total_size_human = f"{total_bytes / (1024 * 1024 * 1024):.2f} GB"
        
        return {
            "total_files": total_files,
            "total_size_human": total_size_human,
        }
    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        return {
            "total_files": 0,
            "total_size_human": "0 B",
        }


def _friendly_error(raw: str) -> tuple[str, str]:
    """Return (title, detail) friendly Arabic messages for common errors."""
    r = raw.lower()
    if "unsupported format" in r or "unsupported" in r:
        return "صيغة غير مدعومة", "الصيغة المطلوبة غير مدعومة للتحويل. جرّب صيغة أخرى."
    if "not found" in r or "no such file" in r:
        return "الملف غير موجود", "لم يُعثر على الملف في المخزن. ربما تم حذفه."
    if "permission" in r or "authorization" in r:
        return "ليس لديك صلاحية", "هذا الملف لا ينتمي لحسابك."
    if "corrupt" in r or "invalid file" in r:
        return "الملف تالف أو غير صالح", "الملف الأصلي يبدو تالفًا أو غير مكتمل."
    if "memory" in r or "out of memory" in r:
        return "الملف كبير جداً", "الملف يتجاوز الذاكرة المتاحة."
    if "sheet" in r:
        return "ورقة عمل غير موجودة", "اسم ورقة العمل المدخل غير صحيح."
    if "timeout" in r:
        return "انتهت المهلة الزمنية", "استغرقت العملية وقتاً طويلاً."
    return "خطأ في التحويل", raw[:200] if raw else "حدث خطأ غير متوقع."


def file_to_dict_simple(file: File) -> dict:
    """Convert File object to dictionary for JSON serialization."""
    return {
        "id": file.id,
        "original_name": file.original_name,
        "format": file.format,
        "size_bytes": file.size_bytes,
        "size_human": file.size_human if hasattr(file, 'size_human') else f"{file.size_bytes} B" if file.size_bytes else "0 B",
        "path": file.path,
    }


# ============================================================
# CONVERTER PANEL (HTMX) - يستخدم داخل مساحة العمل
# ============================================================

@router.get("/workspace/panel/convert", response_class=HTMLResponse)
async def converter_panel(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    file_id: Optional[int] = Query(None),
):
    """Get converter panel partial for workspace (HTMX)."""
    try:
        logger.info(f"🔄 Converter panel requested, file_id: {file_id}")
        
        file_repo = FileRepository(db)
        all_files = await file_repo.get_by_owner(current_user.id, limit=100)
        
        extracted_files = _extract_files(all_files)
        
        # ✅ جمع الملفات بدون استبعاد أي منها
        files = []
        for f in extracted_files:
            if hasattr(f, 'path') and f.path:
                files.append(f)
                try:
                    if hasattr(storage, 'file_exists') and not storage.file_exists(f.path):
                        logger.debug(f"⚠️ File {f.id} ({f.original_name}) not found in storage")
                except Exception:
                    pass
        
        files_dict = [file_to_dict_simple(f) for f in files]
        
        selected_file = None
        selected_file_id = file_id
        
        if file_id:
            for f in files:
                if f.id == file_id:
                    selected_file = file_to_dict_simple(f)
                    selected_file_id = file_id
                    break
        
        # Get translations
        translations = get_texts(current_user.default_lang or 'ar')
        
        logger.info(f"📁 Files count: {len(files_dict)}, Selected: {selected_file_id}")
        
        return templates.TemplateResponse(
            request,
            "workspace/_panel_convert.html",
            {
                "files": files_dict,
                "export_formats": EXPORT_FORMATS,
                "lang": current_user.default_lang,
                "selected_file_id": selected_file_id,
                "selected_file": selected_file,
                "translations": translations,
                "t": lambda text, **kwargs: translations.get(text, text).format(**kwargs) if kwargs else translations.get(text, text),
            },
        )
    except Exception as e:
        logger.error(f"❌ Error in converter_panel: {e}")
        import traceback
        traceback.print_exc()
        return HTMLResponse(
            f"""
            <div class="p-4 text-center">
                <p class="text-red-500">خطأ في تحميل لوحة التحويل: {str(e)}</p>
                <p class="text-xs text-slate-400 mt-2">{traceback.format_exc()}</p>
            </div>
            """,
            status_code=500
        )


# ============================================================
# CONVERTER FILES LIST (HTMX)
# ============================================================

@router.get("/workspace/panel/convert/files", response_class=HTMLResponse)
async def converter_files_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get files list for converter panel."""
    try:
        file_repo = FileRepository(db)
        all_files = await file_repo.get_by_owner(current_user.id, limit=100)
        
        extracted_files = _extract_files(all_files)
        
        files = []
        for f in extracted_files:
            if hasattr(f, 'path') and f.path:
                files.append(f)
        
        files_dict = [file_to_dict_simple(f) for f in files]
        
        return templates.TemplateResponse(
            request,
            "workspace/_files_panel.html",
            {
                "files": files_dict,
                "total": len(files_dict),
                "lang": current_user.default_lang,
            },
        )
    except Exception as e:
        logger.error(f"❌ Error in converter_files_list: {e}")
        return HTMLResponse('<div class="text-red-500">فشل تحميل قائمة الملفات</div>', status_code=500)


# ============================================================
# OTHER ENDPOINTS (SHEETS, PREVIEW, CONVERT, DOWNLOAD)
# ============================================================

@router.get("/converter/sheets/{file_id}")
async def get_file_sheets(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the list of worksheet names for an Excel file (JSON)."""
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

    ths = "".join(
        f'<th class="px-3 py-2 text-start text-xs font-semibold text-slate-500 dark:text-slate-400 whitespace-nowrap border-b border-slate-200 dark:border-slate-700">{c}</th>'
        for c in cols
    )
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


# ============================================================
# CONVERT SSE
# ============================================================

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

        src_fmt = f.format.lower().lstrip(".")
        is_direct = (src_fmt, target_fmt) in DIRECT_PAIRS

        selected_sheets = [s for s in sheets if s]
        is_excel_src = src_fmt in {"xlsx", "xls", "xlsm", "xlsb", "ods"}
        is_pdf_src = src_fmt == "pdf"
        multi_sheet_mode = is_excel_src and len(selected_sheets) > 1
        pdf_pages_mode = is_pdf_src and target_fmt == "xlsx"

        op = await op_repo.create(
            type=OperationType.CONVERT,
            user_id=current_user.id,
            file_id=f.id,
            input_path=f.path,
            params={"file_id": file_id, "target_format": target_fmt,
                    "sheet": sheet, "sheets": selected_sheets},
        )
        t0 = time.time()

        yield _sse("progress", {"pct": 28, "step": "reading", "msg": f"جاري قراءة {f.original_name}…"})
        await asyncio.sleep(0)

        if await request.is_disconnected():
            await op_repo.mark_complete(op, OperationStatus.FAILED, error="client disconnected",
                                        duration_ms=int((time.time() - t0) * 1000))
            return

        _TIMEOUT = 300

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
                                "detail": "استغرقت قراءة الملف وقتاً طويلاً. حاول بملف أصغر."})
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

        yield _sse("progress", {"pct": 62, "step": "converting",
                                 "msg": f"جاري التحويل إلى .{target_fmt.upper()}…"})
        await asyncio.sleep(0)

        if await request.is_disconnected():
            await op_repo.mark_complete(op, OperationStatus.FAILED, error="client disconnected",
                                        duration_ms=int((time.time() - t0) * 1000))
            return

        stem = Path(f.original_name).stem
        uid = uuid.uuid4().hex[:6]

        if (multi_sheet_mode or pdf_pages_mode) and target_fmt not in {"xlsx", "pdf"}:
            out_ext = "zip"
        else:
            out_ext = target_fmt

        out_name = f"{stem}_{uid}.{out_ext}"
        out_path = storage.get_output_path(current_user.id, out_name)

        same_fmt = (src_fmt == target_fmt or
                    (src_fmt in {"xlsx", "xlsm", "xlsb", "xls"} and target_fmt == "xlsx"))

        async def _run(fn):
            try:
                return await asyncio.wait_for(
                    loop.run_in_executor(None, fn),
                    timeout=_TIMEOUT,
                )
            except asyncio.TimeoutError:
                raise TimeoutError("انتهت المهلة الزمنية أثناء التحويل")

        try:
            if same_fmt and not multi_sheet_mode:
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
                                "detail": "استغرق التحويل وقتاً طويلاً. حاول بملف أصغر."})
            return
        except Exception as exc:
            t, d = _friendly_error(str(exc))
            duration_ms = int((time.time() - t0) * 1000)
            await op_repo.mark_complete(op, OperationStatus.FAILED, error=str(exc), duration_ms=duration_ms)
            yield _sse("done", {"ok": False, "title": t, "detail": d})
            return

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


# ============================================================
# DOWNLOAD CONVERTED FILE
# ============================================================

@router.get("/converter/download/{filename}")
async def download_converted(
    filename: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.core.config import settings
    path = Path(settings.OUTPUT_DIR) / str(current_user.id) / filename
    if not path.exists():
        return RedirectResponse(url="/workspace", status_code=302)
    return FileResponse(str(path), filename=filename)


# ============================================================
# LEGACY CONVERT POST (للتوافق)
# ============================================================

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
        return RedirectResponse(url="/workspace", status_code=302)
    except Exception as e:
        if request.headers.get("HX-Request"):
            return HTMLResponse(
                f'<div class="p-4 bg-red-900/40 border border-red-500/30 rounded-xl text-red-300">خطأ: {e}</div>',
                status_code=400,
            )
        return RedirectResponse(url="/workspace", status_code=302)
