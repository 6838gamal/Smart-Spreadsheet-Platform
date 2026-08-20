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

    async def save_bytes(self, path: str, content: bytes, content_type: str = None) -> Dict[str, Any]:
        """
        Save bytes directly to storage.
        
        Args:
            path: Storage path
            content: File content as bytes
            content_type: MIME type
        
        Returns:
            Dict: Storage metadata
        """
        # Ensure directory exists
        file_path = self.storage_dir / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write content
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)
        
        return self._metadata(
            path=str(file_path),
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
        
        # التحقق من وجود المتغيرات
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
            logger.warning(
                "Supabase storage is enabled but SUPABASE_URL or "
                "SUPABASE_SERVICE_ROLE_KEY is missing. Falling back to local storage."
            )
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
        
        logger.info(f"✅ Supabase Storage initialized with bucket: {self.bucket}")

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
            storage_backend=self.backend_name,
        )

    async def save_bytes(self, path: str, content: bytes, content_type: str = None) -> Dict[str, Any]:
        """
        Save bytes directly to Supabase Storage.
        
        Args:
            path: Storage path
            content: File content as bytes
            content_type: MIME type
        
        Returns:
            Dict: Storage metadata
        """
        if self.backend_name == "local":
            return await super().save_bytes(path, content, content_type)
        
        # Save to cache first
        cache_path = self.cache_dir / path
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        
        async with aiofiles.open(cache_path, "wb") as f:
            await f.write(content)
        
        # Upload to Supabase
        try:
            await self._upload_file(cache_path, path, content_type or "application/octet-stream")
            cache_path.unlink(missing_ok=True)
            
            return {
                "path": self._storage_uri(path),
                "name": Path(path).name,
                "original_name": Path(path).name,
                "size_bytes": len(content),
                "format": path.split('.')[-1].lower() if '.' in path else 'bin',
                "mime_type": content_type or "application/octet-stream",
                "bucket": self.bucket,
                "object_key": path,
                "public_url": self.public_url(path),
                "storage_backend": self.backend_name,
            }
        except Exception as e:
            logger.error(f"❌ Failed to upload bytes to Supabase: {e}")
            # Fallback to local
            return await super().save_bytes(path, content, content_type)

    async def save_output(self, path: str | Path, user_id: int, mime_type: str = "application/octet-stream") -> dict:
        """Save output file to Supabase Storage."""
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
            async with httpx.AsyncClient(timeout=getattr(settings, 'SUPABASE_STORAGE_TIMEOUT_SECONDS', 60)) as client:
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
            # Try local path
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
            if response.status_code == 200:
                logger.info(f"✅ Deleted from Supabase: {object_key}")
                # Delete from cache
                (self.cache_dir / object_key).unlink(missing_ok=True)
                return True
            else:
                logger.warning(f"⚠️ Supabase delete returned {response.status_code}: {response.text}")
                return False
        except Exception as e:
            logger.error(f"❌ Supabase delete failed: {e}")
            return False

    def file_exists(self, path: str) -> bool:
        """Check if file exists in Supabase Storage."""
        if self.backend_name == "local":
            return super().file_exists(path)
            
        # Check if it's a storage URI
        object_key = self._object_key(path)
        if not object_key:
            return super().file_exists(path)
            
        # Check cache first
        cache_path = self.cache_dir / object_key
        if cache_path.exists():
            return True
            
        # Check Supabase
        try:
            url = f"{self.base_url}/storage/v1/object/{self.bucket}/{object_key}"
            import httpx
            response = httpx.head(url, headers=self.headers, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"⚠️ File exists check failed: {e}")
            return False

    def public_url(self, object_key: str) -> str:
        """Get public URL for a file."""
        return f"{self.base_url}/storage/v1/object/public/{self.bucket}/{object_key}"

    async def _upload_file(self, path: Path, object_key: str, mime_type: str) -> None:
        """Upload file to Supabase Storage."""
        url = f"{self.base_url}/storage/v1/object/{self.bucket}/{object_key}"
        headers = {**self.headers, "Content-Type": mime_type, "x-upsert": "true"}
        
        try:
            async with httpx.AsyncClient(timeout=getattr(settings, 'SUPABASE_STORAGE_TIMEOUT_SECONDS', 60)) as client:
                with path.open("rb") as f:
                    content = f.read()
                response = await client.post(url, headers=headers, content=content)
                response.raise_for_status()
                logger.info(f"✅ Uploaded to Supabase: {object_key}")
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
    """Build storage service based on configuration."""
    backend = getattr(settings, 'FILE_STORAGE_BACKEND', 'local').lower()
    
    if backend == "supabase":
        try:
            service = SupabaseStorageService()
            if service.backend_name == "local":
                logger.warning("⚠️ Supabase not available, using local storage")
                return LocalStorageService()
            logger.info("✅ Using Supabase storage backend")
            return service
        except Exception as e:
            logger.warning(f"⚠️ Failed to initialize Supabase storage: {e}, falling back to local")
            return LocalStorageService()
    else:
        logger.info("📁 Using local storage backend")
        return LocalStorageService()


# Create global storage instance
storage = _build_storage_service()
