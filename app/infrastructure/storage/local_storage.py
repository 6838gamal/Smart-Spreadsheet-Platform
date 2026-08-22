"""
File storage services.

PostgreSQL stores file metadata in the ``files`` table while the binary file
content is delegated to a storage backend.  Local storage remains available for
processing, but uploaded and generated file bytes are persisted only in
Supabase Storage. PostgreSQL keeps the file metadata and object keys.
"""

import uuid
import logging
import shutil
import json
from pathlib import Path
from typing import Optional, Dict, Any
import aiofiles
import httpx
from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import FileTooLargeError, UnsupportedFormatError

logger = logging.getLogger(__name__)


class LocalStorageService:
    """Local filesystem storage for development/testing."""
    
    backend_name = "local"

    def __init__(self):
        self.output_dir = Path(settings.OUTPUT_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        storage_dir_path = getattr(settings, 'STORAGE_DIR', './storage')
        self.storage_dir = Path(storage_dir_path)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        logger.warning(f"📁 LOCAL STORAGE: {self.storage_dir.absolute()}")
        logger.warning("⚠️ Files stored locally will be LOST on server restart!")

    def _safe_extension(self, filename: str) -> str:
        """Extract and validate file extension."""
        ext = Path(filename).suffix.lstrip(".").lower()
        if not ext:
            raise UnsupportedFormatError("unknown")
        if ext not in settings.ALLOWED_IMPORT_EXTENSIONS:
            raise UnsupportedFormatError(ext)
        return ext

    def _unique_filename(self, original: str) -> tuple[str, str]:
        """Return (unique_name, extension)."""
        ext = self._safe_extension(original)
        unique = f"{uuid.uuid4().hex}.{ext}"
        return unique, ext

    async def save_upload(self, file: UploadFile, user_id: int) -> dict:
        """Save uploaded file to local storage."""
        unique_name, ext = self._unique_filename(file.filename or "upload")
        user_dir = self.storage_dir / str(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)
        file_path = user_dir / unique_name

        size = 0
        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(1024 * 256):
                size += len(chunk)
                if size > settings.MAX_FILE_SIZE_BYTES:
                    await f.close()
                    file_path.unlink(missing_ok=True)
                    raise FileTooLargeError(size / (1024 * 1024), settings.MAX_FILE_SIZE_MB)
                await f.write(chunk)

        absolute_path = str(file_path.absolute())
        logger.info(f"✅ File saved locally: {absolute_path}")

        return self._metadata(
            path=absolute_path,
            name=unique_name,
            original_name=file.filename or unique_name,
            size_bytes=size,
            format=ext,
            mime_type=file.content_type or "application/octet-stream",
        )

    async def save_bytes(self, path: str, content: bytes, content_type: str = None) -> Dict[str, Any]:
        """Save bytes directly to storage."""
        file_path = self.storage_dir / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)
        
        absolute_path = str(file_path.absolute())
        
        return self._metadata(
            path=absolute_path,
            name=file_path.name,
            original_name=file_path.name,
            size_bytes=len(content),
            format=path.split('.')[-1].lower() if '.' in path else 'bin',
            mime_type=content_type or "application/octet-stream",
        )

    async def save_output(self, path: str | Path, user_id: int, mime_type: str = "application/octet-stream") -> dict:
        """Save output file to local storage."""
        p = Path(path)
        user_dir = self.storage_dir / str(user_id) / "outputs"
        user_dir.mkdir(parents=True, exist_ok=True)
        dest_path = user_dir / p.name
        
        if p.exists():
            shutil.copy2(p, dest_path)
        
        absolute_path = str(dest_path.absolute())
        
        return self._metadata(
            path=absolute_path,
            name=p.name,
            original_name=p.name,
            size_bytes=dest_path.stat().st_size if dest_path.exists() else 0,
            format=p.suffix.lstrip(".").lower(),
            mime_type=mime_type,
        )

    def get_output_path(self, user_id: int, filename: str) -> Path:
        """Return a temporary/output path for a user."""
        out_dir = self.output_dir / str(user_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir / filename

    async def get_read_path(self, path: str, user_id: int | None = None) -> str:
        """Return a local readable path for processors."""
        path_obj = Path(path)
        if not path_obj.is_absolute():
            possible_path = self.storage_dir / path
            if possible_path.exists():
                return str(possible_path.absolute())
            if path.startswith("storage/"):
                possible_path = self.storage_dir / path[8:]
                if possible_path.exists():
                    return str(possible_path.absolute())
        return str(path_obj.absolute()) if path_obj.exists() else path

    def delete_file(self, path: str) -> bool:
        """Delete a file from storage."""
        p = Path(path)
        if p.exists():
            p.unlink()
            return True
        
        alt_path = self.storage_dir / path
        if alt_path.exists():
            alt_path.unlink()
            return True
        
        if path.startswith("storage/"):
            alt_path = self.storage_dir / path[8:]
            if alt_path.exists():
                alt_path.unlink()
                return True
        
        return False

    def file_exists(self, path: str) -> bool:
        """Check if file exists."""
        p = Path(path)
        if p.exists():
            return True
        
        alt_path = self.storage_dir / path
        if alt_path.exists():
            return True
        
        if path.startswith("storage/"):
            alt_path = self.storage_dir / path[8:]
            if alt_path.exists():
                return True
        
        return False

    def get_file_size(self, path: str) -> int:
        p = Path(path)
        if p.exists():
            return p.stat().st_size
        
        alt_path = self.storage_dir / path
        if alt_path.exists():
            return alt_path.stat().st_size
        
        return 0

    def _metadata(self, **values: object) -> dict:
        return {**values, "storage_backend": self.backend_name}


class SupabaseStorageService(LocalStorageService):
    """Supabase Storage backend with no persistent local file storage."""
    
    backend_name = "supabase"

    def __init__(self):
        super().__init__()
        
        # ✅ التحقق من وجود المتغيرات
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
            logger.error("=" * 60)
            logger.error("❌❌❌ SUPABASE STORAGE NOT AVAILABLE ❌❌❌")
            logger.error("=" * 60)
            logger.error("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY is missing!")
            logger.error("Falling back to LOCAL storage.")
            logger.error("Files will be LOST on server restart!")
            logger.error("=" * 60)
            self.backend_name = "local"
            return
            
        self.base_url = settings.SUPABASE_URL.rstrip("/")
        self.bucket = getattr(settings, 'SUPABASE_STORAGE_BUCKET', 'files')
        self.headers = {
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
        }
        self.cache_dir = Path(getattr(settings, 'SUPABASE_STORAGE_CACHE_DIR', './cache'))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # ✅ التحقق من اتصال Supabase
        self._test_connection()
        
        if self.backend_name == "supabase":
            logger.info(f"✅ Supabase Storage initialized with bucket: {self.bucket}")

    def _get_mime_from_extension(self, ext: str) -> str:
        """Get MIME type from file extension."""
        mime_map = {
            # Documents
            "pdf": "application/pdf",
            "doc": "application/msword",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "xls": "application/vnd.ms-excel",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "ppt": "application/vnd.ms-powerpoint",
            "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "odt": "application/vnd.oasis.opendocument.text",
            "ods": "application/vnd.oasis.opendocument.spreadsheet",
            "odp": "application/vnd.oasis.opendocument.presentation",
            
            # Images
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "webp": "image/webp",
            "svg": "image/svg+xml",
            "bmp": "image/bmp",
            "tiff": "image/tiff",
            "ico": "image/x-icon",
            
            # Data
            "json": "application/json",
            "xml": "application/xml",
            "csv": "text/csv",
            "tsv": "text/tab-separated-values",
            "txt": "text/plain",
            "yaml": "application/x-yaml",
            "yml": "application/x-yaml",
            "parquet": "application/parquet",
            "feather": "application/feather",
            
            # Archives
            "zip": "application/zip",
            "rar": "application/x-rar-compressed",
            "7z": "application/x-7z-compressed",
            "tar": "application/x-tar",
            "gz": "application/gzip",
            
            # Database
            "sqlite": "application/x-sqlite3",
            "db": "application/x-sqlite3",
            "sql": "application/sql",
            
            # Other
            "html": "text/html",
            "htm": "text/html",
            "md": "text/markdown",
        }
        return mime_map.get(ext.lower(), "application/pdf")  # ✅ PDF كـ fallback

    def _get_supported_mime_type(self, mime_type: str, path: Path) -> str:
        """Get a supported MIME type for Supabase Storage."""
        
        # ✅ أنواع MIME المدعومة في Supabase
        supported = {
            # Images
            "image/jpeg": "image/jpeg",
            "image/png": "image/png",
            "image/gif": "image/gif",
            "image/webp": "image/webp",
            "image/svg+xml": "image/svg+xml",
            "image/bmp": "image/bmp",
            "image/tiff": "image/tiff",
            "image/x-icon": "image/x-icon",
            
            # Documents
            "application/pdf": "application/pdf",
            "application/msword": "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": 
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.ms-excel": "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": 
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-powerpoint": "application/vnd.ms-powerpoint",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation": 
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/vnd.oasis.opendocument.text": "application/vnd.oasis.opendocument.text",
            "application/vnd.oasis.opendocument.spreadsheet": "application/vnd.oasis.opendocument.spreadsheet",
            "application/vnd.oasis.opendocument.presentation": "application/vnd.oasis.opendocument.presentation",
            
            # Data
            "application/json": "application/json",
            "application/xml": "application/xml",
            "text/csv": "text/csv",
            "text/tab-separated-values": "text/tab-separated-values",
            "text/plain": "text/plain",
            "application/x-yaml": "application/x-yaml",
            "application/parquet": "application/parquet",
            
            # Archives
            "application/zip": "application/zip",
            "application/x-rar-compressed": "application/x-rar-compressed",
            "application/x-7z-compressed": "application/x-7z-compressed",
            "application/x-tar": "application/x-tar",
            "application/gzip": "application/gzip",
            
            # Database
            "application/x-sqlite3": "application/x-sqlite3",
            "application/sql": "application/sql",
            
            # Other
            "text/html": "text/html",
            "text/markdown": "text/markdown",
        }
        
        # ✅ إذا كان النوع مدعوماً، استخدمه
        if mime_type in supported:
            return supported[mime_type]
        
        # ✅ إذا كان application/octet-stream، حاول استنتاج النوع من الامتداد
        if mime_type == "application/octet-stream" or mime_type == "application/octet-stream":
            ext = path.suffix.lower()
            if ext:
                guessed = self._get_mime_from_extension(ext)
                if guessed in supported:
                    return guessed
        
        # ✅ استخدام PDF كـ fallback (مدعوم دائماً)
        return "application/pdf"

    def _test_connection(self) -> None:
        """Test Supabase connection by uploading a small test file."""
        try:
            import httpx
            
            # ✅ استخدام JSON (نوع MIME مدعوم)
            test_content = json.dumps({"test": "connection", "timestamp": str(uuid.uuid4())}).encode()
            test_path = f"test/{uuid.uuid4().hex[:8]}.json"
            
            url = f"{self.base_url}/storage/v1/object/{self.bucket}/{test_path}"
            
            response = httpx.post(
                url,
                headers={
                    **self.headers, 
                    "Content-Type": "application/json",
                    "x-upsert": "true"
                },
                content=test_content,
                timeout=30
            )
            
            if response.status_code in (200, 201):
                # ✅ حذف ملف الاختبار
                delete_url = f"{self.base_url}/storage/v1/object/{self.bucket}/{test_path}"
                delete_response = httpx.delete(delete_url, headers=self.headers, timeout=30)
                if delete_response.status_code in (200, 204):
                    logger.info("✅ Supabase Storage connection test passed")
                    self.backend_name = "supabase"
                else:
                    logger.warning(f"⚠️ Test file uploaded but could not delete: {delete_response.status_code}")
                    self.backend_name = "supabase"  # ✅ استمر حتى مع فشل الحذف
            else:
                logger.error(f"❌ Supabase Storage test failed: {response.status_code} - {response.text[:200]}")
                self.backend_name = "local"
        except Exception as e:
            logger.error(f"❌ Supabase Storage test error: {e}")
            self.backend_name = "local"

    async def save_upload(self, file: UploadFile, user_id: int) -> dict:
        """Save uploaded file to Supabase Storage."""
        if self.backend_name == "local":
            return await super().save_upload(file, user_id)
            
        unique_name, ext = self._unique_filename(file.filename or "upload")
        object_key = f"uploads/{user_id}/{unique_name}"
        cache_path = self.cache_dir / object_key
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        size = 0
        async with aiofiles.open(cache_path, "wb") as f:
            while chunk := await file.read(1024 * 256):
                size += len(chunk)
                if size > settings.MAX_FILE_SIZE_BYTES:
                    await f.close()
                    cache_path.unlink(missing_ok=True)
                    raise FileTooLargeError(size / (1024 * 1024), settings.MAX_FILE_SIZE_MB)
                await f.write(chunk)

        # ✅ استنتاج نوع MIME مناسب من الامتداد
        mime_type = file.content_type or self._get_mime_from_extension(ext)
        
        await self._upload_file(cache_path, object_key, mime_type)
        cache_path.unlink(missing_ok=True)
        
        logger.info(f"✅ Uploaded to Supabase: {object_key} ({size} bytes) with MIME: {mime_type}")
        
        return self._metadata(
            path=self._storage_uri(object_key),
            name=unique_name,
            original_name=file.filename or unique_name,
            size_bytes=size,
            format=ext,
            mime_type=mime_type,
            bucket=self.bucket,
            object_key=object_key,
            public_url=self.public_url(object_key),
            storage_backend=self.backend_name,
        )

    async def save_bytes(self, path: str, content: bytes, content_type: str = None) -> Dict[str, Any]:
        """Save bytes directly to Supabase Storage."""
        if self.backend_name == "local":
            return await super().save_bytes(path, content, content_type)
        
        # Save to cache first
        cache_path = self.cache_dir / path
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        
        async with aiofiles.open(cache_path, "wb") as f:
            await f.write(content)
        
        # Upload to Supabase
        try:
            # ✅ استنتاج نوع MIME من المسار والامتداد
            ext = path.split('.')[-1].lower() if '.' in path else ''
            mime_type = content_type or self._get_mime_from_extension(ext)
            
            await self._upload_file(cache_path, path, mime_type)
            cache_path.unlink(missing_ok=True)
            
            return {
                "path": self._storage_uri(path),
                "name": Path(path).name,
                "original_name": Path(path).name,
                "size_bytes": len(content),
                "format": ext or 'bin',
                "mime_type": mime_type,
                "bucket": self.bucket,
                "object_key": path,
                "public_url": self.public_url(path),
                "storage_backend": self.backend_name,
            }
        except Exception as e:
            logger.error(f"❌ Failed to upload bytes to Supabase: {e}")
            return await super().save_bytes(path, content, content_type)

    async def save_output(self, path: str | Path, user_id: int, mime_type: str = "application/octet-stream") -> dict:
        """Save output file to Supabase Storage."""
        if self.backend_name == "local":
            return await super().save_output(path, user_id, mime_type)
            
        p = Path(path)
        object_key = f"outputs/{user_id}/{p.name}"
        
        # ✅ استنتاج نوع MIME من الامتداد
        ext = p.suffix.lstrip(".").lower()
        if mime_type == "application/octet-stream":
            mime_type = self._get_mime_from_extension(ext)
        
        await self._upload_file(p, object_key, mime_type)
        p.unlink(missing_ok=True)
        
        return self._metadata(
            path=self._storage_uri(object_key),
            name=p.name,
            original_name=p.name,
            size_bytes=p.stat().st_size,
            format=ext,
            mime_type=mime_type,
            bucket=self.bucket,
            object_key=object_key,
            public_url=self.public_url(object_key),
            storage_backend=self.backend_name,
        )

    async def get_read_path(self, path: str, user_id: int | None = None) -> str:
        """Get local readable path for a file from Supabase."""
        if self.backend_name == "local":
            return await super().get_read_path(path, user_id)
            
        object_key = self._object_key(path)
        if not object_key:
            return path
            
        cache_path = self.cache_dir / object_key
        if cache_path.exists():
            return str(cache_path)
            
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        url = f"{self.base_url}/storage/v1/object/{self.bucket}/{object_key}"
        
        try:
            async with httpx.AsyncClient(timeout=settings.SUPABASE_STORAGE_TIMEOUT_SECONDS) as client:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
            cache_path.write_bytes(response.content)
            return str(cache_path)
        except Exception as e:
            logger.error(f"❌ Failed to download from Supabase: {e}")
            return str(cache_path)

    def delete_file(self, path: str) -> bool:
        """Delete a file from Supabase Storage."""
        if self.backend_name == "local":
            return super().delete_file(path)
            
        object_key = self._object_key(path)
        if not object_key:
            return super().delete_file(path)
            
        url = f"{self.base_url}/storage/v1/object/{self.bucket}"
        try:
            import httpx as sync_httpx
            response = sync_httpx.request(
                "DELETE",
                url,
                headers={**self.headers, "Content-Type": "application/json"},
                json={"prefixes": [object_key]},
                timeout=settings.SUPABASE_STORAGE_TIMEOUT_SECONDS,
            )
            if response.status_code in (200, 204):
                logger.info(f"🗑️ Deleted from Supabase: {object_key}")
                (self.cache_dir / object_key).unlink(missing_ok=True)
                return True
            else:
                logger.warning(f"⚠️ Supabase delete returned {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ Supabase delete failed: {e}")
            return False

    def file_exists(self, path: str) -> bool:
        """Check if file exists in Supabase Storage."""
        if self.backend_name == "local":
            return super().file_exists(path)
            
        object_key = self._object_key(path)
        if not object_key:
            return super().file_exists(path)
            
        # Check cache first
        cache_path = self.cache_dir / object_key
        if cache_path.exists():
            return True
            
        # Check Supabase
        try:
            import httpx
            url = f"{self.base_url}/storage/v1/object/{self.bucket}/{object_key}"
            response = httpx.head(url, headers=self.headers, timeout=10)
            return response.status_code == 200
        except Exception:
            return False

    def public_url(self, object_key: str) -> str:
        """Get public URL for a file."""
        return f"{self.base_url}/storage/v1/object/public/{self.bucket}/{object_key}"

    async def _upload_file(self, path: Path, object_key: str, mime_type: str) -> None:
        """Upload file to Supabase Storage."""
        url = f"{self.base_url}/storage/v1/object/{self.bucket}/{object_key}"
        
        # ✅ تحويل أنواع MIME غير المدعومة إلى أنواع مدعومة
        mime_type = self._get_supported_mime_type(mime_type, path)
        
        headers = {
            **self.headers,
            "Content-Type": mime_type,
            "x-upsert": "true"
        }
        
        try:
            async with httpx.AsyncClient(timeout=settings.SUPABASE_STORAGE_TIMEOUT_SECONDS) as client:
                with path.open("rb") as f:
                    content = f.read()
                response = await client.post(url, headers=headers, content=content)
                response.raise_for_status()
                logger.info(f"✅ Uploaded to Supabase: {object_key} (MIME: {mime_type})")
        except httpx.HTTPStatusError as e:
            # ✅ إذا كان خطأ MIME type، حاول أنواع أخرى
            if e.response.status_code == 415:
                logger.warning(f"⚠️ MIME type {mime_type} not supported, trying fallback types...")
                
                # ✅ قائمة أنواع MIME للـ fallback
                fallback_types = [
                    "application/pdf",
                    "image/png", 
                    "image/jpeg",
                    "application/json",
                    "text/plain",
                    "application/zip"
                ]
                
                for fallback in fallback_types:
                    try:
                        logger.info(f"🔄 Trying fallback MIME: {fallback}")
                        headers["Content-Type"] = fallback
                        with path.open("rb") as f:
                            content = f.read()
                        response = await client.post(url, headers=headers, content=content)
                        response.raise_for_status()
                        logger.info(f"✅ Uploaded with fallback MIME: {fallback}")
                        return
                    except Exception:
                        continue
                
                # ✅ إذا فشلت جميع المحاولات
                logger.error(f"❌ All fallback MIME types failed for {object_key}")
                raise
            else:
                logger.error(f"❌ HTTP error uploading to Supabase: {e.response.status_code} - {e.response.text[:200]}")
                raise
        except Exception as e:
            logger.error(f"❌ Upload to Supabase failed: {e}")
            raise

    def _storage_uri(self, object_key: str) -> str:
        """Create storage URI."""
        return f"supabase://{self.bucket}/{object_key}"

    def _object_key(self, path: str) -> str | None:
        """Extract object key from storage URI."""
        prefix = f"supabase://{self.bucket}/"
        return path[len(prefix):] if path.startswith(prefix) else None


def _build_storage_service():
    """
    Build storage service based on configuration.
    
    ✅ محسنة: تعطي تحذيرات واضحة عند فشل Supabase
    """
    backend = getattr(settings, 'FILE_STORAGE_BACKEND', 'local').lower()
    
    logger.info("=" * 50)
    logger.info(f"📁 Storage Backend Configuration: {backend}")
    logger.info("=" * 50)
    
    # ✅ محاولة استخدام Supabase إذا كان مطلوباً
    if backend == "supabase":
        # ✅ التحقق من وجود المتغيرات
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
            logger.error("=" * 60)
            logger.error("❌❌❌  SUPABASE CREDENTIALS MISSING  ❌❌❌")
            logger.error("=" * 60)
            logger.error("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY is not set!")
            logger.error("")
            logger.error("Please add these environment variables:")
            logger.error("  SUPABASE_URL=https://your-project.supabase.co")
            logger.error("  SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIs...")
            logger.error("  SUPABASE_STORAGE_BUCKET=files")
            logger.error("=" * 60)
            logger.error("⚠️ FALLING BACK TO LOCAL STORAGE")
            logger.error("⚠️ Files will be LOST on server restart!")
            logger.error("=" * 60)
            return LocalStorageService()
        
        try:
            service = SupabaseStorageService()
            if service.backend_name == "local":
                logger.error("=" * 60)
                logger.error("❌❌❌ SUPABASE STORAGE FAILED ❌❌❌")
                logger.error("=" * 60)
                logger.error("Supabase Storage initialization failed.")
                logger.error("Falling back to LOCAL storage.")
                logger.error("Files will be LOST on server restart!")
                logger.error("=" * 60)
                return LocalStorageService()
            
            logger.info("=" * 60)
            logger.info("✅✅✅ USING SUPABASE STORAGE ✅✅✅")
            logger.info("=" * 60)
            logger.info(f"   URL: {settings.SUPABASE_URL[:40]}...")
            logger.info(f"   Bucket: {service.bucket}")
            logger.info("   Files are persistent and will survive restarts!")
            logger.info("=" * 60)
            return service
            
        except Exception as e:
            logger.error("=" * 60)
            logger.error(f"❌❌❌ SUPABASE STORAGE ERROR: {e} ❌❌❌")
            logger.error("=" * 60)
            logger.error("Falling back to LOCAL storage.")
            logger.error("Files will be LOST on server restart!")
            logger.error("=" * 60)
            return LocalStorageService()
    
    else:
        logger.warning("=" * 60)
        logger.warning("📁 USING LOCAL STORAGE BACKEND")
        logger.warning("=" * 60)
        logger.warning("⚠️ Files are stored locally on the server filesystem.")
        logger.warning("⚠️ All files will be LOST on server restart!")
        logger.warning("⚠️ Use Supabase Storage for persistent storage.")
        logger.warning("=" * 60)
        return LocalStorageService()


# ✅ Create global storage instance
storage = _build_storage_service()
