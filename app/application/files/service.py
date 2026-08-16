"""File management application service with hybrid storage (local + server)."""

import logging
import time
import json
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, AuthorizationError, ValidationError
from app.infrastructure.repositories.file_repository import FileRepository
from app.infrastructure.repositories.operation_repository import OperationRepository
from app.infrastructure.database.models import File, OperationType, OperationStatus
from app.infrastructure.storage.local_storage import storage
from app.application.files.dto import RenameFileDTO, FileMetadataDTO
from app.application.converter.engine import DataEngine
from app.infrastructure.cache.redis_cache import RedisCache

logger = logging.getLogger(__name__)


class FileService:
    """Hybrid file service - stores metadata in DB, actual files in local storage (browser)"""

    def __init__(self, db: AsyncSession, cache: Optional[RedisCache] = None):
        self.db = db
        self.file_repo = FileRepository(db)
        self.op_repo = OperationRepository(db)
        self.cache = cache or RedisCache()
        self.storage = storage
        
        # Maximum file size for local storage (100MB)
        self.MAX_LOCAL_SIZE = 100 * 1024 * 1024  # 100MB
        
        # Supported formats for local storage
        self.SUPPORTED_FORMATS = {
            'xlsx', 'xls', 'xlsm', 'xlsb', 'ods', 'csv', 'tsv', 'txt',
            'json', 'xml', 'yaml', 'yml', 'parquet', 'feather',
            'sqlite', 'db', 'sql', 'docx', 'doc', 'pdf', 'pptx',
            'html', 'htm', 'jpg', 'jpeg', 'png', 'bmp', 'gif', 'webp', 'svg'
        }

    async def upload(self, file: UploadFile, user_id: int, store_locally: bool = True) -> File:
        """
        Upload file - stores metadata in DB and file content in local storage.
        
        Args:
            file: The uploaded file
            user_id: Owner user ID
            store_locally: Whether to store file content locally (browser)
        
        Returns:
            File: The created file record
        """
        t0 = time.time()
        
        # Validate file size
        if file.size > self.MAX_LOCAL_SIZE:
            logger.warning(f"File too large for local storage: {file.size} bytes")
            # Still store but with warning
            # Could also reject if too large
        
        # Generate unique storage key for local storage
        storage_key = self._generate_storage_key(file.filename, user_id)
        
        # Save file to server (temporary/backup)
        meta = await storage.save_upload(file, user_id)
        
        # Create DB record with storage key
        db_file = await self.file_repo.create(
            owner_id=user_id,
            **meta,
            storage_key=storage_key,  # New field for local storage reference
            is_locally_stored=store_locally,
            size_bytes=file.size or 0
        )
        
        # Try to extract metadata (non-blocking failure)
        try:
            engine = DataEngine()
            file_meta = engine.get_metadata(meta["path"], meta["format"])
            await self.file_repo.update(db_file, meta={**db_file.meta, **file_meta})
        except Exception as e:
            logger.warning(f"Metadata extraction failed for {meta['name']}: {e}")
        
        duration_ms = int((time.time() - t0) * 1000)
        
        # Log operation
        op = await self.op_repo.create(
            type=OperationType.UPLOAD,
            user_id=user_id,
            file_id=db_file.id,
            input_path=meta["path"],
        )
        await self.op_repo.mark_complete(
            op, OperationStatus.SUCCESS,
            result={
                "file_id": db_file.id,
                "storage_key": storage_key,
                "store_locally": store_locally
            },
            duration_ms=duration_ms,
        )
        
        logger.info(f"Uploaded file: {meta['original_name']} ({db_file.size_human}) - Storage Key: {storage_key}")
        return db_file

    async def get_file_content(self, file_id: int, user_id: int) -> Optional[bytes]:
        """
        Get file content - tries local storage first, then server.
        
        Args:
            file_id: File ID
            user_id: User ID for authorization
        
        Returns:
            Optional[bytes]: File content if found
        """
        f = await self.get_file(file_id, user_id)
        
        # Try to get from cache first
        cached_content = await self.cache.get_file_content(file_id)
        if cached_content:
            logger.info(f"File {file_id} served from cache")
            return cached_content
        
        # Check if file exists on server
        if storage.file_exists(f.path):
            with open(f.path, 'rb') as fp:
                content = fp.read()
            
            # Cache for future requests
            await self.cache.cache_file_content(file_id, content, ttl=300)  # 5 minutes
            
            return content
        
        # File not found on server - client must have local copy
        logger.warning(f"File {file_id} not found on server - client may have local copy")
        return None

    async def stream_file(self, file_id: int, user_id: int, start: int = 0, end: int = None):
        """
        Stream file content - supports range requests.
        
        Args:
            file_id: File ID
            user_id: User ID for authorization
            start: Start byte
            end: End byte
        
        Yields:
            bytes: File chunks
        """
        f = await self.get_file(file_id, user_id)
        
        if not storage.file_exists(f.path):
            raise NotFoundError("File content not found on server. Please sync your local copy.")
        
        with open(f.path, 'rb') as fp:
            fp.seek(start)
            chunk_size = 8192
            bytes_remaining = (end or f.size_bytes) - start
            
            while bytes_remaining > 0:
                chunk = fp.read(min(chunk_size, bytes_remaining))
                if not chunk:
                    break
                bytes_remaining -= len(chunk)
                yield chunk

    async def download_file(self, file_id: int, user_id: int) -> Dict[str, Any]:
        """
        Get file download information - client will fetch content.
        
        Returns:
            Dict: File info for download
        """
        f = await self.get_file(file_id, user_id)
        
        # Generate download token (for secure access)
        download_token = self._generate_download_token(file_id, user_id)
        
        return {
            "file_id": file_id,
            "name": f.original_name,
            "size": f.size_bytes,
            "format": f.format,
            "mime_type": f.mime_type,
            "storage_key": f.storage_key,
            "download_token": download_token,
            "meta": f.meta,
            "server_available": storage.file_exists(f.path)
        }

    async def get_file(self, file_id: int, user_id: int) -> File:
        """Get file metadata by ID with authorization."""
        f = await self.file_repo.get_by_id(file_id)
        if not f:
            raise NotFoundError("File")
        if f.owner_id != user_id:
            raise AuthorizationError()
        return f

    async def list_files(
        self,
        user_id: int,
        search: str | None = None,
        format_filter: str | None = None,
        only_local: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[File], int]:
        """
        List files with filters.
        
        Args:
            user_id: User ID
            search: Search query
            format_filter: File format filter
            only_local: Only show files stored locally
            limit: Pagination limit
            offset: Pagination offset
        
        Returns:
            tuple: List of files and total count
        """
        files = await self.file_repo.get_by_owner(
            user_id, 
            limit=limit, 
            offset=offset,
            search=search, 
            format_filter=format_filter,
            only_local=only_local
        )
        
        # Enrich with local storage status
        for f in files:
            f.is_cached_locally = await self._is_file_cached_locally(f.storage_key)
        
        total = await self.file_repo.count_by_owner(user_id)
        return files, total

    async def delete_file(self, file_id: int, user_id: int, delete_local: bool = True) -> None:
        """
        Delete file - removes from server and optionally local storage.
        
        Args:
            file_id: File ID
            user_id: User ID for authorization
            delete_local: Whether to delete from local storage (client should handle)
        """
        f = await self.get_file(file_id, user_id)
        
        # Delete from server
        if storage.file_exists(f.path):
            storage.delete_file(f.path)
        
        # Delete from cache
        await self.cache.delete_file_content(file_id)
        
        # Delete from database
        await self.file_repo.delete(f)
        
        # Log the deletion with local storage info
        op = await self.op_repo.create(
            type=OperationType.DELETE,
            user_id=user_id,
            file_id=file_id,
            input_path=f.path,
        )
        await self.op_repo.mark_complete(
            op, OperationStatus.SUCCESS,
            result={
                "file_id": file_id,
                "storage_key": f.storage_key,
                "delete_local": delete_local
            },
            duration_ms=0,
        )
        
        logger.info(f"Deleted file: {f.original_name} (Local: {delete_local})")

    async def rename_file(self, file_id: int, user_id: int, dto: RenameFileDTO) -> File:
        """Rename file metadata."""
        f = await self.get_file(file_id, user_id)
        return await self.file_repo.update(f, original_name=dto.new_name)

    async def toggle_favorite(self, file_id: int, user_id: int) -> File:
        """Toggle favorite status."""
        f = await self.get_file(file_id, user_id)
        return await self.file_repo.update(f, is_favorite=not f.is_favorite)

    async def get_preview(self, file_id: int, user_id: int, rows: int = 100) -> dict:
        """Get file preview (for supported formats)."""
        f = await self.get_file(file_id, user_id)
        
        # Check if file exists on server
        if not storage.file_exists(f.path):
            raise NotFoundError("File content not available on server")
        
        engine = DataEngine()
        return engine.preview(f.path, f.format, rows=rows)

    async def sync_local_files(self, user_id: int, local_files: list[Dict[str, Any]]) -> dict:
        """
        Sync local file status - updates metadata for files stored in browser.
        
        Args:
            user_id: User ID
            local_files: List of local file info {storage_key, file_id, size, modified}
        
        Returns:
            dict: Sync result
        """
        updated = 0
        for local_file in local_files:
            file_id = local_file.get('file_id')
            storage_key = local_file.get('storage_key')
            
            if not file_id or not storage_key:
                continue
            
            # Check if file exists and belongs to user
            f = await self.file_repo.get_by_id(file_id)
            if f and f.owner_id == user_id:
                # Update last_synced timestamp
                await self.file_repo.update(
                    f, 
                    last_synced_at=datetime.utcnow(),
                    is_locally_stored=True
                )
                updated += 1
        
        return {
            "synced": updated,
            "total": len(local_files),
            "timestamp": datetime.utcnow().isoformat()
        }

    async def cleanup_unused_files(self, days: int = 30) -> dict:
        """
        Clean up old files not accessed for X days.
        
        Args:
            days: Number of days to keep files
        
        Returns:
            dict: Cleanup results
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        # Get old files
        old_files = await self.file_repo.get_old_files(cutoff)
        
        deleted = 0
        for f in old_files:
            try:
                # Delete from storage
                if storage.file_exists(f.path):
                    storage.delete_file(f.path)
                
                # Delete from database
                await self.file_repo.delete(f)
                deleted += 1
                
                logger.info(f"Cleaned up old file: {f.original_name} (ID: {f.id})")
            except Exception as e:
                logger.error(f"Failed to clean up file {f.id}: {e}")
        
        return {
            "deleted": deleted,
            "deleted_files": [f.original_name for f in old_files[:10]],  # First 10
            "cutoff_date": cutoff.isoformat()
        }

    async def get_storage_stats(self, user_id: int) -> dict:
        """
        Get storage statistics for user.
        
        Returns:
            dict: Storage usage statistics
        """
        files = await self.file_repo.get_by_owner(user_id, limit=10000)
        total_size = sum(f.size_bytes for f in files)
        local_count = sum(1 for f in files if f.is_locally_stored)
        
        return {
            "user_id": user_id,
            "total_files": len(files),
            "total_size_bytes": total_size,
            "total_size_human": self._human_size(total_size),
            "locally_stored_files": local_count,
            "cloud_files": len(files) - local_count,
            "formats": self._group_by_format(files)
        }

    # ============================================================
    # PRIVATE METHODS
    # ============================================================

    def _generate_storage_key(self, filename: str, user_id: int) -> str:
        """Generate unique storage key for local storage."""
        timestamp = int(time.time() * 1000)
        file_hash = hashlib.md5(f"{filename}_{user_id}_{timestamp}".encode()).hexdigest()[:16]
        return f"file_{user_id}_{file_hash}_{timestamp}"

    def _generate_download_token(self, file_id: int, user_id: int) -> str:
        """Generate secure download token."""
        token_data = f"{file_id}_{user_id}_{int(time.time())}"
        return hashlib.sha256(token_data.encode()).hexdigest()[:32]

    async def _is_file_cached_locally(self, storage_key: str) -> bool:
        """Check if file is stored in local storage (IndexedDB)."""
        # This is client-side check - server can only guess
        # We store last_synced_at field to track
        return False  # Server doesn't know local cache status

    def _human_size(self, bytes_size: int) -> str:
        """Convert bytes to human readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} PB"

    def _group_by_format(self, files: list[File]) -> dict:
        """Group files by format."""
        formats = {}
        for f in files:
            fmt = f.format or 'unknown'
            formats[fmt] = formats.get(fmt, 0) + 1
        return formats


# ============================================================
# DTO (Data Transfer Objects)
# ============================================================

class FileMetadataDTO:
    """Data transfer object for file metadata."""
    
    def __init__(
        self,
        name: str,
        original_name: str,
        path: str,
        size_bytes: int,
        format: str,
        mime_type: str,
        storage_key: str,
        is_locally_stored: bool = True
    ):
        self.name = name
        self.original_name = original_name
        self.path = path
        self.size_bytes = size_bytes
        self.format = format
        self.mime_type = mime_type
        self.storage_key = storage_key
        self.is_locally_stored = is_locally_stored
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "original_name": self.original_name,
            "path": self.path,
            "size_bytes": self.size_bytes,
            "format": self.format,
            "mime_type": self.mime_type,
            "storage_key": self.storage_key,
            "is_locally_stored": self.is_locally_stored
        }
