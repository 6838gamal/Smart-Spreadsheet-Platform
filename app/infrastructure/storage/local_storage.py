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
from pathlib import Path
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
        self.storage_dir = Path(getattr(settings, 'STORAGE_DIR', './storage'))
        self.storage_dir.mkdir(parents=True, exist_ok=True)

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

        return self._metadata(
            path=str(file_path),
            name=unique_name,
            original_name=file.filename or unique_name,
            size_bytes=size,
            format=ext,
            mime_type=file.content_type or "application/octet-stream",
        )

    async def save_output(self, path: str | Path, user_id: int, mime_type: str = "application/octet-stream") -> dict:
        """Save output file to local storage."""
        p = Path(path)
        user_dir = self.storage_dir / str(user_id) / "outputs"
        user_dir.mkdir(parents=True, exist_ok=True)
        dest_path = user_dir / p.name
        
        # Copy file to storage directory
        if p.exists():
            shutil.copy2(p, dest_path)
        
        return self._metadata(
            path=str(dest_path),
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
        return path

    def delete_file(self, path: str) -> bool:
        """Delete a file from storage."""
        p = Path(path)
        if p.exists():
            p.unlink()
            return True
        return False

    def file_exists(self, path: str) -> bool:
        return Path(path).exists()

    def get_file_size(self, path: str) -> int:
        p = Path(path)
        return p.stat().st_size if p.exists() else 0

    def _metadata(self, **values: object) -> dict:
        return {**values, "storage_backend": self.backend_name}


class SupabaseStorageService(LocalStorageService):
    """Supabase Storage backend with no persistent local file storage."""

    backend_name = "supabase"

    def __init__(self):
        super().__init__()
        
        # التحقق من وجود المتغيرات، وإذا لم تكن موجودة استخدم التخزين المحلي
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
            logger.warning(
                "Supabase storage is enabled but SUPABASE_URL or "
                "SUPABASE_SERVICE_ROLE_KEY is missing. Falling back to local storage."
            )
            # تحويل الكائن إلى LocalStorageService بدلاً من Supabase
            self.__class__ = LocalStorageService
            self.__init__()
            return
            
        self.base_url = settings.SUPABASE_URL.rstrip("/")
        self.bucket = getattr(settings, 'SUPABASE_STORAGE_BUCKET', 'files')
        self.headers = {
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
        }
        self.cache_dir = Path(getattr(settings, 'SUPABASE_STORAGE_CACHE_DIR', './cache'))
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def save_upload(self, file: UploadFile, user_id: int) -> dict:
        # إذا كان الكائن تحول إلى LocalStorageService، استخدم دالة الأب
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

        await self._upload_file(
            cache_path, object_key, file.content_type or "application/octet-stream"
        )
        cache_path.unlink(missing_ok=True)
        return self._metadata(
            path=self._storage_uri(object_key),
            name=unique_name,
            original_name=file.filename or unique_name,
            size_bytes=size,
            format=ext,
            mime_type=file.content_type or "application/octet-stream",
            bucket=self.bucket,
            object_key=object_key,
            public_url=self.public_url(object_key),
        )

    async def save_output(self, path: str | Path, user_id: int, mime_type: str = "application/octet-stream") -> dict:
        # إذا كان الكائن تحول إلى LocalStorageService، استخدم دالة الأب
        if self.backend_name == "local":
            return await super().save_output(path, user_id, mime_type)
            
        p = Path(path)
        object_key = f"outputs/{user_id}/{p.name}"
        await self._upload_file(p, object_key, mime_type)
        p.unlink(missing_ok=True)
        return self._metadata(
            path=self._storage_uri(object_key),
            name=p.name,
            original_name=p.name,
            size_bytes=p.stat().st_size,
            format=p.suffix.lstrip(".").lower(),
            mime_type=mime_type,
            bucket=self.bucket,
            object_key=object_key,
            public_url=self.public_url(object_key),
        )

    async def get_read_path(self, path: str, user_id: int | None = None) -> str:
        # إذا كان الكائن تحول إلى LocalStorageService، استخدم دالة الأب
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
        async with httpx.AsyncClient(timeout=getattr(settings, 'SUPABASE_STORAGE_TIMEOUT_SECONDS', 60)) as client:
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()
        cache_path.write_bytes(response.content)
        return str(cache_path)

    def delete_file(self, path: str) -> bool:
        # إذا كان الكائن تحول إلى LocalStorageService، استخدم دالة الأب
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
                timeout=getattr(settings, 'SUPABASE_STORAGE_TIMEOUT_SECONDS', 60),
            )
            response.raise_for_status()
            (self.cache_dir / object_key).unlink(missing_ok=True)
            return True
        except Exception:
            return False

    def file_exists(self, path: str) -> bool:
        if self.backend_name == "local":
            return super().file_exists(path)
        return bool(path and (path.startswith("supabase://") or super().file_exists(path)))

    def public_url(self, object_key: str) -> str:
        return f"{self.base_url}/storage/v1/object/public/{self.bucket}/{object_key}"

    async def _upload_file(self, path: Path, object_key: str, mime_type: str) -> None:
        url = f"{self.base_url}/storage/v1/object/{self.bucket}/{object_key}"
        headers = {**self.headers, "Content-Type": mime_type, "x-upsert": "true"}
        async with httpx.AsyncClient(timeout=getattr(settings, 'SUPABASE_STORAGE_TIMEOUT_SECONDS', 60)) as client:
            with path.open("rb") as f:
                response = await client.post(url, headers=headers, content=f.read())
            response.raise_for_status()

    def _storage_uri(self, object_key: str) -> str:
        return f"supabase://{self.bucket}/{object_key}"

    def _object_key(self, path: str) -> str | None:
        prefix = f"supabase://{self.bucket}/"
        return path[len(prefix):] if path.startswith(prefix) else None


def _build_storage_service():
    """Build storage service based on configuration."""
    backend = getattr(settings, 'FILE_STORAGE_BACKEND', 'local').lower()
    
    if backend == "supabase":
        # حاول استخدام Supabase، وإذا فشل استخدم Local
        try:
            service = SupabaseStorageService()
            # إذا تحول الكائن إلى Local، فهذا يعني أن Supabase غير متوفر
            if service.backend_name == "local":
                return service
            return service
        except Exception as e:
            logger.warning(f"Failed to initialize Supabase storage: {e}, falling back to local")
            return LocalStorageService()
    else:
        # استخدام التخزين المحلي بشكل افتراضي
        logger.info("Using local storage backend")
        return LocalStorageService()


# Create global storage instance
storage = _build_storage_service()
