"""
File storage services.

PostgreSQL stores file metadata in the ``files`` table while the binary file
content is delegated to a storage backend.  Local storage remains available for
processing, but uploaded and generated file bytes are persisted only in
Supabase Storage. PostgreSQL keeps the file metadata and object keys.
"""

import uuid
from pathlib import Path
import aiofiles
import httpx
from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import FileTooLargeError, UnsupportedFormatError


class LocalStorageService:
    """Temporary filesystem helper used only while processing files."""

    backend_name = "temporary"

    def __init__(self):
        self.output_dir = Path(settings.OUTPUT_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)

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
        """Uploading to local storage is intentionally disabled."""
        raise RuntimeError("Local upload storage is disabled. Configure Supabase Storage.")

    async def save_output(self, path: str | Path, user_id: int, mime_type: str = "application/octet-stream") -> dict:
        """Return metadata for a temporary output file before remote upload."""
        p = Path(path)
        return self._metadata(
            path=str(p),
            name=p.name,
            original_name=p.name,
            size_bytes=p.stat().st_size if p.exists() else 0,
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
        self.base_url = settings.SUPABASE_URL.rstrip("/")
        self.bucket = settings.SUPABASE_STORAGE_BUCKET
        self.headers = {
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
        }
        self.cache_dir = Path(settings.SUPABASE_STORAGE_CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.configuration_errors = self._validate_configuration()

    async def save_upload(self, file: UploadFile, user_id: int) -> dict:
        self._ensure_configured()
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
        self._ensure_configured()
        p = Path(path)
        size_bytes = p.stat().st_size
        object_key = f"outputs/{user_id}/{p.name}"
        await self._upload_file(p, object_key, mime_type)
        p.unlink(missing_ok=True)
        return self._metadata(
            path=self._storage_uri(object_key),
            name=p.name,
            original_name=p.name,
            size_bytes=size_bytes,
            format=p.suffix.lstrip(".").lower(),
            mime_type=mime_type,
            bucket=self.bucket,
            object_key=object_key,
            public_url=self.public_url(object_key),
        )

    async def get_read_path(self, path: str, user_id: int | None = None) -> str:
        object_key = self._object_key(path)
        if not object_key:
            return path
        self._ensure_configured()
        cache_path = self.cache_dir / object_key
        if cache_path.exists():
            return str(cache_path)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        url = f"{self.base_url}/storage/v1/object/{self.bucket}/{object_key}"
        async with httpx.AsyncClient(timeout=settings.SUPABASE_STORAGE_TIMEOUT_SECONDS) as client:
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()
        cache_path.write_bytes(response.content)
        return str(cache_path)

    def delete_file(self, path: str) -> bool:
        object_key = self._object_key(path)
        if not object_key:
            return super().delete_file(path)
        if self.configuration_errors:
            return False
        url = f"{self.base_url}/storage/v1/object/{self.bucket}"
        try:
            response = httpx.request(
                "DELETE",
                url,
                headers={**self.headers, "Content-Type": "application/json"},
                json={"prefixes": [object_key]},
                timeout=settings.SUPABASE_STORAGE_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            (self.cache_dir / object_key).unlink(missing_ok=True)
            return True
        except httpx.HTTPError:
            return False

    def file_exists(self, path: str) -> bool:
        return bool(path and (path.startswith("supabase://") or super().file_exists(path)))

    def public_url(self, object_key: str) -> str:
        if not self.base_url:
            return ""
        return f"{self.base_url}/storage/v1/object/public/{self.bucket}/{object_key}"

    @property
    def is_configured(self) -> bool:
        return not self.configuration_errors

    def _validate_configuration(self) -> list[str]:
        errors: list[str] = []
        if not self.base_url:
            errors.append("SUPABASE_URL is not configured")
        if not settings.SUPABASE_SERVICE_ROLE_KEY:
            errors.append("SUPABASE_SERVICE_ROLE_KEY is not configured")
        if not self.bucket:
            errors.append("SUPABASE_STORAGE_BUCKET is not configured")
        return errors

    def _ensure_configured(self) -> None:
        if self.configuration_errors:
            raise RuntimeError(
                "Supabase Storage is not configured: " + "; ".join(self.configuration_errors)
            )

    async def _upload_file(self, path: Path, object_key: str, mime_type: str) -> None:
        url = f"{self.base_url}/storage/v1/object/{self.bucket}/{object_key}"
        headers = {**self.headers, "Content-Type": mime_type, "x-upsert": "true"}
        async with httpx.AsyncClient(timeout=settings.SUPABASE_STORAGE_TIMEOUT_SECONDS) as client:
            with path.open("rb") as f:
                response = await client.post(url, headers=headers, content=f.read())
            response.raise_for_status()

    def _storage_uri(self, object_key: str) -> str:
        return f"supabase://{self.bucket}/{object_key}"

    def _object_key(self, path: str) -> str | None:
        prefix = f"supabase://{self.bucket}/"
        return path[len(prefix):] if path.startswith(prefix) else None


def _build_storage_service() -> SupabaseStorageService:
    # Keep application startup safe: invalid/missing environment variables are
    # reported at operation time instead of crashing module import.
    return SupabaseStorageService()


storage = _build_storage_service()
