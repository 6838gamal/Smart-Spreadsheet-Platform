"""
Local filesystem storage service.
Handles file save, delete, and path resolution.
Designed to be swappable with S3/GCS in the future.
"""

import os
import uuid
import shutil
import aiofiles
from pathlib import Path
from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import FileTooLargeError, UnsupportedFormatError


class LocalStorageService:
    def __init__(self):
        self.upload_dir = Path(settings.UPLOAD_DIR)
        self.output_dir = Path(settings.OUTPUT_DIR)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
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
        """Save an uploaded file and return metadata dict."""
        unique_name, ext = self._unique_filename(file.filename or "upload")
        user_dir = self.upload_dir / str(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)
        dest = user_dir / unique_name

        size = 0
        async with aiofiles.open(dest, "wb") as f:
            while chunk := await file.read(1024 * 256):  # 256KB chunks
                size += len(chunk)
                if size > settings.MAX_FILE_SIZE_BYTES:
                    await f.close()
                    dest.unlink(missing_ok=True)
                    raise FileTooLargeError(size / (1024 * 1024), settings.MAX_FILE_SIZE_MB)
                await f.write(chunk)

        return {
            "path": str(dest),
            "name": unique_name,
            "original_name": file.filename or unique_name,
            "size_bytes": size,
            "format": ext,
            "mime_type": file.content_type or "application/octet-stream",
        }

    def get_output_path(self, user_id: int, filename: str) -> Path:
        """Return a path in the outputs directory for a user."""
        out_dir = self.output_dir / str(user_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir / filename

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


storage = LocalStorageService()
