"""File manager web routes."""

import json
import logging
import uuid
import tempfile
import re
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from fastapi import APIRouter, Depends, Request, UploadFile, File, Form, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path
from typing import Optional, List
import io
import aiofiles
import httpx

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_user_optional
from app.core.templates import templates
from app.core.config import settings
from app.infrastructure.database.models import User, File as FileModel
from app.application.files.service import FileService

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def file_to_dict(file: FileModel) -> dict:
    """Convert a File object to a dictionary for JSON serialization."""
    if not file:
        return None
    
    return {
        "id": file.id,
        "name": file.name,
        "original_name": file.original_name,
        "path": file.path,
        "size_bytes": file.size_bytes,
        "format": file.format,
        "mime_type": file.mime_type,
        "status": file.status,
        "is_favorite": file.is_favorite,
        "tags": file.tags or [],
        "meta": file.meta or {},
        "owner_id": file.owner_id,
        "storage_key": getattr(file, 'storage_key', None),
        "is_locally_stored": getattr(file, 'is_locally_stored', False),
        "storage_backend": getattr(file, 'storage_backend', None),
        "storage_bucket": getattr(file, 'storage_bucket', None),
        "storage_object_key": getattr(file, 'storage_object_key', None),
        "created_at": file.created_at.isoformat() if file.created_at else None,
        "updated_at": file.updated_at.isoformat() if file.updated_at else None,
        "thumbnail_url": file.meta.get('thumbnail_url') if file.meta else None,
        "is_image": file.meta.get('is_image', False) if file.meta else False,
        "image_width": file.meta.get('image_width') if file.meta else None,
        "image_height": file.meta.get('image_height') if file.meta else None,
        "size_human": file.size_human if hasattr(file, 'size_human') else f"{file.size_bytes} B" if file.size_bytes else "0 B",
        "source_url": file.meta.get('source_url') if file.meta else None,
        "original_url": file.meta.get('original_url') if file.meta else None,
        "imported_from_url": file.meta.get('imported_from_url', False) if file.meta else None,
    }


def files_to_dict_list(files: List[FileModel]) -> List[dict]:
    """Convert a list of File objects to a list of dictionaries."""
    if not files:
        return []
    return [file_to_dict(file) for file in files]


def extract_actual_url(url: str) -> str:
    """
    Extract the actual URL from various redirect services.
    
    Supports:
    - Google Redirect (google.com/url?url=...)
    - Google Drive (drive.google.com)
    - Bitly, TinyURL, etc.
    """
    parsed = urlparse(url)
    
    # Google Redirect
    if 'google.com' in parsed.netloc and '/url?' in url:
        query_params = parse_qs(parsed.query)
        if 'url' in query_params:
            actual_url = query_params['url'][0]
            # URL decode
            actual_url = actual_url.replace('%3A', ':').replace('%2F', '/')
            actual_url = actual_url.replace('%3F', '?').replace('%3D', '=')
            actual_url = actual_url.replace('%26', '&')
            actual_url = actual_url.replace('%2C', ',')
            return actual_url
    
    # Google Drive - extract file ID and create direct download link
    if 'drive.google.com' in parsed.netloc:
        if '/file/d/' in url:
            # Extract file ID from /file/d/FILE_ID/view
            match = re.search(r'/file/d/([^/]+)', url)
            if match:
                file_id = match.group(1)
                return f"https://drive.google.com/uc?export=download&id={file_id}"
        elif 'id=' in url:
            # Extract from ?id=FILE_ID
            query_params = parse_qs(parsed.query)
            if 'id' in query_params:
                file_id = query_params['id'][0]
                return f"https://drive.google.com/uc?export=download&id={file_id}"
    
    # Dropbox - convert to direct download
    if 'dropbox.com' in parsed.netloc:
        # Change ?dl=0 to ?dl=1 for direct download
        if '?dl=0' in url:
            return url.replace('?dl=0', '?dl=1')
        elif '?dl=' not in url:
            return url + '?dl=1'
    
    # GitHub raw content
    if 'github.com' in parsed.netloc and '/blob/' in url:
        # Convert github.com/user/repo/blob/branch/file to raw.githubusercontent.com/user/repo/branch/file
        parts = url.split('/')
        # Find 'blob' index
        try:
            blob_index = parts.index('blob')
            user = parts[3]
            repo = parts[4]
            branch = parts[blob_index + 1]
            file_path = '/'.join(parts[blob_index + 2:])
            return f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/{file_path}"
        except (ValueError, IndexError):
            pass
    
    return url


def detect_content_type(content: bytes, content_type: str) -> tuple[str, str]:
    """
    Detect the actual content type and extension from file magic bytes.
    
    Returns:
        tuple: (detected_content_type, detected_extension)
    """
    # PDF
    if content.startswith(b'%PDF'):
        return 'application/pdf', 'pdf'
    
    # PNG
    if content.startswith(b'\x89PNG'):
        return 'image/png', 'png'
    
    # JPEG
    if content.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg', 'jpg'
    
    # GIF
    if content.startswith(b'GIF8'):
        return 'image/gif', 'gif'
    
    # WebP
    if content.startswith(b'RIFF') and len(content) > 12 and content[8:12] == b'WEBP':
        return 'image/webp', 'webp'
    
    # BMP
    if content.startswith(b'BM'):
        return 'image/bmp', 'bmp'
    
    # SVG
    if content.startswith(b'<svg') or content.startswith(b'<?xml'):
        try:
            text = content[:500].decode('utf-8', errors='ignore').lower()
            if '<svg' in text:
                return 'image/svg+xml', 'svg'
        except:
            pass
    
    # ZIP-based formats (DOCX, XLSX, PPTX, JAR, etc.)
    if content.startswith(b'PK\x03\x04'):
        # Try to detect specific ZIP-based formats
        try:
            text = content[:2000].decode('utf-8', errors='ignore')
            if 'word/' in text:
                return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'docx'
            elif 'xl/' in text:
                return 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'xlsx'
            elif 'ppt/' in text:
                return 'application/vnd.openxmlformats-officedocument.presentationml.presentation', 'pptx'
        except:
            pass
        return 'application/zip', 'zip'
    
    # JSON
    if content.startswith(b'{') or content.startswith(b'['):
        try:
            json.loads(content[:1000])
            return 'application/json', 'json'
        except:
            pass
    
    # XML
    if content.startswith(b'<?xml') or content.startswith(b'<'):
        try:
            text = content[:500].decode('utf-8', errors='ignore')
            if text.strip().startswith('<'):
                return 'application/xml', 'xml'
        except:
            pass
    
    # CSV - check for comma-separated values
    try:
        text = content[:500].decode('utf-8', errors='ignore')
        if ',' in text and '\n' in text:
            lines = text.strip().split('\n')
            if len(lines) > 1 and len(lines[0].split(',')) > 1:
                return 'text/csv', 'csv'
    except:
        pass
    
    # Plain text
    try:
        content[:500].decode('utf-8')
        return 'text/plain', 'txt'
    except:
        pass
    
    # Default
    return content_type or 'application/octet-stream', 'bin'


async def _auto_analyze(file_id: int, file_path: str, file_format: str, db: AsyncSession) -> int | None:
    """Create a DocumentAnalysis record and enqueue the analysis job."""
    try:
        from app.infrastructure.database.models_intelligence import DocumentAnalysis, AnalysisStatus
        from app.jobs.job_queue import job_queue

        existing = await db.execute(
            select(DocumentAnalysis).where(
                DocumentAnalysis.file_id == file_id,
                DocumentAnalysis.status.in_([AnalysisStatus.PENDING, AnalysisStatus.RUNNING]),
            )
        )
        if existing.scalar_one_or_none():
            return None

        analysis = DocumentAnalysis(file_id=file_id, status=AnalysisStatus.PENDING)
        db.add(analysis)
        await db.flush()

        await job_queue.enqueue(
            job_type="analysis",
            payload={
                "file_id": file_id,
                "file_path": file_path,
                "file_format": file_format,
                "analysis_id": analysis.id,
            },
            priority=3,
        )
        await db.commit()
        logger.info(f"Auto-triggered analysis for file_id={file_id} (analysis_id={analysis.id})")
        return analysis.id
    except Exception as e:
        logger.error(f"Auto-analysis failed for file_id={file_id}: {e}")
        return None


# ============================================================
# ROUTES
# ============================================================

@router.get("/files", response_class=HTMLResponse)
async def files_page(
    request: Request,
    search: str = "",
    fmt: str = "",
    only_local: bool = False,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    page: int = 1,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Display files page with filtering, sorting, and pagination."""
    svc = FileService(db)
    limit = 20
    offset = (page - 1) * limit
    
    files, total = await svc.list_files(
        user_id=current_user.id,
        search=search or None,
        format_filter=fmt or None,
        only_local=only_local,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order
    )
    
    total_pages = max(1, (total + limit - 1) // limit)
    files_dict = files_to_dict_list(files)
    
    return templates.TemplateResponse(
        request,
        "files/index.html",
        {
            "user": current_user,
            "files": files_dict,
            "total": total,
            "page": page,
            "total_pages": total_pages,
            "search": search,
            "fmt": fmt,
            "only_local": only_local,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "current_page": "files",
            "lang": current_user.default_lang,
        },
    )


@router.post("/files/upload")
async def upload_files(
    request: Request,
    files: list[UploadFile] = File(...),
    store_locally: bool = Form(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload files to the server with support for images and thumbnails."""
    svc = FileService(db)
    uploaded_files = []
    errors = []
    
    for file in files:
        try:
            f = await svc.upload(file, current_user.id, store_locally=store_locally)
            if f.format and f.format.lower() in ['xlsx', 'xls', 'csv', 'json', 'pdf', 'txt', 'docx', 'doc']:
                await _auto_analyze(f.id, f.path, f.format, db)
            uploaded_files.append(f)
        except Exception as e:
            logger.error(f"Upload error for {file.filename}: {e}")
            errors.append(f"{file.filename}: {str(e)}")

    # HTMX response
    if request.headers.get("HX-Request"):
        if not uploaded_files:
            msg = " | ".join(errors) or "فشل الرفع"
            return HTMLResponse(f'<div class="text-red-400 text-sm text-center">{msg}</div>')

        all_files, total = await svc.list_files(
            user_id=current_user.id,
            limit=100,
            offset=0,
            sort_by="created_at",
            sort_order="desc"
        )
        all_files_dict = files_to_dict_list(all_files)
        
        selected_file_id = uploaded_files[0].id if len(uploaded_files) == 1 else None
        
        html_content = templates.TemplateResponse(
            request,
            "workspace/_files_panel.html",
            {
                "files": all_files_dict,
                "total": total,
                "lang": current_user.default_lang,
                "uploaded_count": len(uploaded_files),
                "has_errors": len(errors) > 0,
                "selected_file_id": selected_file_id,
            }
        )
        
        msg = f"✅ تم رفع {len(uploaded_files)} ملف بنجاح"
        if errors:
            msg += f" ⚠️ ({len(errors)} أخطاء)"
        
        if selected_file_id:
            return HTMLResponse(
                f'<div class="mb-2 text-sm text-emerald-400 text-center">{msg}</div>'
                f'<script>'
                f'  window.dispatchEvent(new CustomEvent("file-uploaded", {{ detail: {{ fileId: {selected_file_id} }} }}));'
                f'</script>'
                + html_content.body.decode('utf-8')
            )
        
        return HTMLResponse(
            f'<div class="mb-2 text-sm text-emerald-400 text-center">{msg}</div>'
            + html_content.body.decode('utf-8')
        )

    return RedirectResponse(url="/files", status_code=302)


# ============================================================
# URL IMPORT - سحب ملف من رابط
# ============================================================

@router.post("/files/import-url")
async def import_from_url(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import a file from a URL."""
    try:
        data = await request.json()
        url = data.get('url')
        
        if not url:
            return JSONResponse({
                "success": False,
                "error": "URL is required"
            }, status_code=400)
        
        # ✅ استخراج الرابط الفعلي من خدمات إعادة التوجيه
        actual_url = extract_actual_url(url)
        logger.info(f"🔄 Original URL: {url}")
        logger.info(f"🔄 Actual URL: {actual_url}")
        
        # Validate URL
        try:
            parsed = urlparse(actual_url)
            if parsed.scheme not in ['http', 'https']:
                return JSONResponse({
                    "success": False,
                    "error": "Only HTTP/HTTPS URLs are supported"
                }, status_code=400)
        except Exception:
            return JSONResponse({
                "success": False,
                "error": "Invalid URL format"
            }, status_code=400)
        
        # Download file from URL
        timeout_seconds = getattr(settings, 'SUPABASE_STORAGE_TIMEOUT_SECONDS', 60)
        async with httpx.AsyncClient(
            timeout=timeout_seconds, 
            follow_redirects=True,
            max_redirects=10
        ) as client:
            # ✅ إضافة User-Agent لتجنب الحظر
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            response = await client.get(actual_url, headers=headers)
            response.raise_for_status()
            
            content = response.content
            content_type = response.headers.get('content-type', 'application/octet-stream')
            final_url = str(response.url)
            
            logger.info(f"📁 Final URL after download: {final_url}")
            logger.info(f"📁 Content-Type: {content_type}")
            logger.info(f"📁 Content size: {len(content)} bytes")
            
            # ✅ التحقق من أن المحتوى ليس HTML (قد يكون صفحة تحذير)
            if 'text/html' in content_type and len(content) < 50000:
                # محاولة فك تشفير HTML
                try:
                    html_content = content.decode('utf-8', errors='ignore')
                    
                    # البحث عن روابط تحميل في HTML
                    # PDF links
                    pdf_urls = re.findall(r'https?://[^\s<>"\']+\.pdf[^\s<>"\']*', html_content)
                    # Google Drive links
                    gdrive_links = re.findall(r'https?://drive\.google\.com[^\s<>"\']+', html_content)
                    # General download links
                    download_links = re.findall(r'https?://[^\s<>"\']+/download[^\s<>"\']*', html_content)
                    
                    all_links = pdf_urls + gdrive_links + download_links
                    
                    for link in all_links:
                        try:
                            logger.info(f"📄 Found link in HTML: {link}")
                            # محاولة تحميل الرابط
                            link_response = await client.get(link, headers=headers)
                            if link_response.status_code == 200:
                                link_content_type = link_response.headers.get('content-type', '')
                                # إذا كان المحتوى ليس HTML، استخدمه
                                if 'text/html' not in link_content_type:
                                    content = link_response.content
                                    content_type = link_content_type
                                    final_url = link
                                    logger.info(f"✅ Found valid file: {link}")
                                    break
                        except Exception as e:
                            logger.warning(f"⚠️ Failed to download link {link}: {e}")
                except Exception as e:
                    logger.warning(f"⚠️ HTML parsing failed: {e}")
            
            # ✅ اكتشاف النوع الفعلي من Magic Bytes
            detected_type, detected_ext = detect_content_type(content, content_type)
            logger.info(f"🔍 Detected type: {detected_type}, extension: {detected_ext}")
            
            # ✅ استخراج اسم الملف
            filename = None
            file_extension = detected_ext
            
            # 1. من Content-Disposition
            content_disposition = response.headers.get('content-disposition')
            if content_disposition and 'filename=' in content_disposition:
                match = re.search(r'filename="?([^"]+)"?', content_disposition)
                if match:
                    filename = match.group(1)
                    filename = filename.split('?')[0]
                    filename = filename.split('#')[0]
                    if '.' in filename:
                        file_extension = filename.rsplit('.', 1)[-1].lower()
            
            # 2. من الرابط النهائي
            if not filename:
                path = urlparse(final_url).path
                filename = path.split('/')[-1]
                if filename:
                    filename = filename.split('?')[0]
                    filename = filename.split('#')[0]
                    if '.' in filename:
                        file_extension = filename.rsplit('.', 1)[-1].lower()
            
            # 3. من الرابط الأصلي
            if not filename:
                path = urlparse(actual_url).path
                filename = path.split('/')[-1]
                if filename:
                    filename = filename.split('?')[0]
                    filename = filename.split('#')[0]
                    if '.' in filename:
                        file_extension = filename.rsplit('.', 1)[-1].lower()
            
            # 4. استخدام النوع المكتشف
            if not filename or filename == '':
                if detected_ext:
                    filename = f"file_{uuid.uuid4().hex[:8]}.{detected_ext}"
                else:
                    filename = f"file_{uuid.uuid4().hex[:8]}.bin"
                    file_extension = 'bin'
            
            # ✅ إذا كان الامتداد المكتشف مختلف عن الموجود، استخدم المكتشف
            if '.' in filename:
                current_ext = filename.rsplit('.', 1)[-1].lower()
                if current_ext != file_extension and file_extension:
                    # استبدال الامتداد
                    name = filename.rsplit('.', 1)[0]
                    filename = f"{name}.{file_extension}"
            elif file_extension:
                filename = f"{filename}.{file_extension}"
            
            # ✅ تنظيف اسم الملف
            filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
            filename = filename.strip()
            if len(filename) > 200:
                name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
                filename = name[:180] + '.' + ext if ext else name[:200]
            
            logger.info(f"📁 Final filename: {filename}, extension: {file_extension}")
            
            # ✅ إنشاء UploadFile
            from tempfile import SpooledTemporaryFile
            
            temp_file = SpooledTemporaryFile(max_size=1024*1024)
            temp_file.write(content)
            temp_file.seek(0)
            
            upload_file = UploadFile(
                filename=filename,
                file=temp_file,
                headers={"content-type": detected_type}
            )
            
            # رفع إلى التخزين
            svc = FileService(db)
            db_file = await svc.upload(upload_file, current_user.id)
            
            temp_file.close()
            
            # إضافة المصدر إلى metadata
            if db_file.meta is None:
                db_file.meta = {}
            db_file.meta['source_url'] = final_url[:500]
            db_file.meta['original_url'] = url[:500]
            db_file.meta['imported_from_url'] = True
            db_file.meta['imported_at'] = datetime.utcnow().isoformat()
            db_file.meta['detected_type'] = detected_type
            db_file.meta['detected_extension'] = file_extension
            db.add(db_file)
            await db.commit()
            await db.refresh(db_file)
            
            # تحليل تلقائي
            if db_file.format and db_file.format.lower() in ['xlsx', 'xls', 'csv', 'json', 'pdf', 'txt', 'docx', 'doc']:
                await _auto_analyze(db_file.id, db_file.path, db_file.format, db)
            
            return JSONResponse({
                "success": True,
                "file_id": db_file.id,
                "filename": db_file.original_name,
                "format": db_file.format,
                "source_url": final_url,
                "message": f"File imported successfully (format: {db_file.format})"
            })
            
    except httpx.TimeoutException:
        return JSONResponse({
            "success": False,
            "error": "Connection timeout. The server took too long to respond."
        }, status_code=504)
    except httpx.HTTPStatusError as e:
        return JSONResponse({
            "success": False,
            "error": f"HTTP error: {e.response.status_code} - {e.response.text[:100]}"
        }, status_code=e.response.status_code)
    except Exception as e:
        logger.error(f"URL import error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


# ============================================================
# FILE DETAIL
# ============================================================

@router.get("/files/{file_id}", response_class=HTMLResponse)
async def file_detail(
    request: Request,
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Display file detail page with preview and analysis."""
    svc = FileService(db)
    
    try:
        f = await svc.get_file(file_id, current_user.id)
    except Exception as e:
        logger.error(f"❌ Error getting file: {e}")
        return RedirectResponse(url="/files", status_code=302)
    
    f.storage_key = getattr(f, 'storage_key', None)
    f.is_locally_stored = getattr(f, 'is_locally_stored', False)
    
    preview = None
    try:
        preview = await svc.get_preview(file_id, current_user.id, rows=200)
    except Exception as e:
        logger.warning(f"Preview not available for file {file_id}: {e}")
        preview = {"error": str(e), "available": False}

    try:
        from app.infrastructure.database.models_intelligence import DocumentAnalysis
        analysis_res = await db.execute(
            select(DocumentAnalysis)
            .where(DocumentAnalysis.file_id == file_id)
            .order_by(DocumentAnalysis.created_at.desc())
            .limit(1)
        )
        analysis = analysis_res.scalar_one_or_none()
    except Exception:
        analysis = None

    # ✅ التحقق من وجود الملف بدون التسبب في حلقة
    file_exists_on_server = False
    try:
        if hasattr(svc.storage, 'file_exists'):
            file_exists_on_server = svc.storage.file_exists(f.path)
    except Exception:
        file_exists_on_server = False

    file_dict = file_to_dict(f)

    return templates.TemplateResponse(
        request,
        "files/detail.html",
        {
            "user": current_user,
            "file": file_dict,
            "file_obj": f,
            "preview": preview,
            "analysis": analysis,
            "file_exists_on_server": file_exists_on_server,
            "current_page": "files",
            "lang": current_user.default_lang,
        },
    )


@router.get("/files/{file_id}/download")
async def download_file(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download file from server with support for large files."""
    svc = FileService(db)
    
    try:
        f = await svc.get_file(file_id, current_user.id)
    except Exception as e:
        logger.error(f"❌ Error getting file: {e}")
        return RedirectResponse(url="/files", status_code=302)
    
    # ✅ محاولة الحصول على المحتوى
    content = await svc.get_file_content(file_id, current_user.id)
    if content:
        logger.info(f"✅ Serving file {file_id} from cache/content ({len(content)} bytes)")
        return StreamingResponse(
            io.BytesIO(content),
            media_type=f.mime_type or "application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{f.original_name}"',
                "Content-Length": str(len(content)),
                "Cache-Control": "private, max-age=3600"
            }
        )
    
    # ✅ محاولة التدفق من التخزين - بدون Content-Length
    try:
        logger.info(f"🔄 Streaming file {file_id} from storage")
        return StreamingResponse(
            svc.stream_file(file_id, current_user.id),
            media_type=f.mime_type or "application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{f.original_name}"',
                # ✅ لا نضيف Content-Length هنا
                "Cache-Control": "private, max-age=3600"
            }
        )
    except NotFoundError:
        logger.warning(f"⚠️ File {file_id} not found in storage")
        return RedirectResponse(url="/files", status_code=302)
    except Exception as e:
        logger.error(f"❌ Download error: {e}")
        return RedirectResponse(url="/files", status_code=302)


@router.get("/files/{file_id}/thumbnail")
async def get_thumbnail(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get file thumbnail (for images)."""
    from PIL import Image
    import io
    
    svc = FileService(db)
    f = await svc.get_file(file_id, current_user.id)
    
    if not f.meta or not f.meta.get('is_image'):
        raise HTTPException(status_code=404, detail="Not an image file")
    
    thumbnail_url = f.meta.get('thumbnail_url')
    if thumbnail_url:
        try:
            if '/thumbnails/' in thumbnail_url:
                path_parts = thumbnail_url.split('/thumbnails/')
                if len(path_parts) > 1:
                    possible_paths = [
                        f"thumbnails/{path_parts[1]}",
                        f"thumbnails/{current_user.id}/{path_parts[1].split('/')[-1]}",
                    ]
                    for thumb_path in possible_paths:
                        if hasattr(svc.storage, 'file_exists') and svc.storage.file_exists(thumb_path):
                            read_path = await svc.storage.get_read_path(thumb_path, current_user.id)
                            if Path(read_path).exists():
                                return FileResponse(
                                    read_path,
                                    media_type="image/webp",
                                    headers={"Cache-Control": "public, max-age=31536000"}
                                )
        except Exception as e:
            logger.warning(f"Failed to get thumbnail: {e}")
    
    try:
        content = await svc.get_file_content(file_id, current_user.id)
        if content:
            img = Image.open(io.BytesIO(content))
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            img.thumbnail((200, 200), Image.Resampling.LANCZOS)
            thumbnail_buffer = io.BytesIO()
            img.save(thumbnail_buffer, format='WEBP', quality=80)
            thumbnail_buffer.seek(0)
            
            return StreamingResponse(
                thumbnail_buffer,
                media_type="image/webp",
                headers={"Cache-Control": "public, max-age=31536000"}
            )
    except Exception as e:
        logger.error(f"Thumbnail generation failed: {e}")
    
    raise HTTPException(status_code=404, detail="Thumbnail not found")


@router.delete("/files/{file_id}")
async def delete_file_api(
    request: Request,
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete file from server - API endpoint."""
    svc = FileService(db)
    
    try:
        await svc.delete_file(file_id, current_user.id)
        return JSONResponse({
            "success": True,
            "message": "File deleted successfully"
        })
    except Exception as e:
        logger.error(f"Delete error: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@router.post("/files/{file_id}/delete")
async def delete_file_web(
    request: Request,
    file_id: int,
    delete_local: bool = Form(True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete file from server - Web endpoint."""
    svc = FileService(db)
    await svc.delete_file(file_id, current_user.id, delete_local=delete_local)
    
    if request.headers.get("HX-Request"):
        all_files, total = await svc.list_files(
            user_id=current_user.id,
            limit=50,
            offset=0,
            sort_by="created_at",
            sort_order="desc"
        )
        all_files_dict = files_to_dict_list(all_files)
        
        return templates.TemplateResponse(
            request,
            "workspace/_files_panel.html",
            {
                "files": all_files_dict,
                "total": total,
                "lang": current_user.default_lang,
            }
        )
    
    return RedirectResponse(url="/files", status_code=302)


@router.post("/files/{file_id}/favorite")
async def toggle_favorite(
    request: Request,
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Toggle favorite status of a file."""
    svc = FileService(db)
    f = await svc.toggle_favorite(file_id, current_user.id)
    
    if request.headers.get("HX-Request"):
        icon = "★" if f.is_favorite else "☆"
        cls = "text-yellow-400" if f.is_favorite else "text-slate-200 dark:text-slate-600 hover:text-yellow-300"
        return HTMLResponse(f'<span class="{cls}">{icon}</span>')
    
    return RedirectResponse(url=f"/files/{file_id}", status_code=302)


@router.post("/files/sync-local")
async def sync_local_files(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sync local files status with server."""
    try:
        body = await request.json()
        local_files = body.get("files", [])
        
        svc = FileService(db)
        result = await svc.sync_local_files(current_user.id, local_files)
        
        return JSONResponse({
            "success": True,
            "result": result
        })
    except Exception as e:
        logger.error(f"Sync error: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@router.get("/files/storage-stats")
async def get_storage_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get storage statistics for current user."""
    svc = FileService(db)
    stats = await svc.get_storage_stats(current_user.id)
    return JSONResponse(stats)


@router.get("/files/{file_id}/preview")
async def preview_file(
    file_id: int,
    rows: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get file preview as JSON."""
    svc = FileService(db)
    preview = await svc.get_preview(file_id, current_user.id, rows=rows)
    return JSONResponse({
        "success": True,
        "data": preview
    })


@router.post("/files/{file_id}/rename")
async def rename_file(
    request: Request,
    file_id: int,
    new_name: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rename a file."""
    from app.application.files.dto import RenameFileDTO
    
    svc = FileService(db)
    dto = RenameFileDTO(new_name=new_name)
    f = await svc.rename_file(file_id, current_user.id, dto)
    
    if request.headers.get("HX-Request"):
        return HTMLResponse(f'<span class="text-sm font-medium">{f.original_name}</span>')
    
    return RedirectResponse(url=f"/files/{file_id}", status_code=302)


# ============================================================
# API ENDPOINTS FOR ALPINE.JS
# ============================================================

@router.get("/api/files/list")
async def api_list_files(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = 50,
    offset: int = 0,
):
    """API endpoint for Alpine.js to get file list as JSON."""
    svc = FileService(db)
    
    files, total = await svc.list_files(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        sort_by="created_at",
        sort_order="desc"
    )
    
    files_dict = files_to_dict_list(files)
    
    return JSONResponse({
        "success": True,
        "files": files_dict,
        "total": total,
        "limit": limit,
        "offset": offset,
    })


@router.get("/api/files/{file_id}")
async def api_get_file(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """API endpoint to get a single file by ID."""
    svc = FileService(db)
    
    try:
        f = await svc.get_file(file_id, current_user.id)
        file_dict = file_to_dict(f)
        return JSONResponse({
            "success": True,
            "file": file_dict
        })
    except Exception as e:
        logger.error(f"Error getting file: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=404)


@router.delete("/api/files/{file_id}")
async def api_delete_file(
    request: Request,
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """API endpoint for Alpine.js to delete a file."""
    svc = FileService(db)
    
    try:
        await svc.delete_file(file_id, current_user.id)
        return JSONResponse({
            "success": True,
            "message": "File deleted successfully"
        })
    except Exception as e:
        logger.error(f"Delete error: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)
