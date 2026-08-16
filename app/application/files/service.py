"""File management application service with PostgreSQL metadata and object storage."""

import logging
import time
import hashlib
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, AuthorizationError, ValidationError
from app.infrastructure.repositories.file_repository import FileRepository
from app.infrastructure.repositories.operation_repository import OperationRepository
from app.infrastructure.database.models import File, OperationType, OperationStatus
from app.infrastructure.storage.local_storage import storage
from app.application.files.dto import RenameFileDTO
from app.application.converter.engine import DataEngine

logger = logging.getLogger(__name__)


class FileService:
    """
    File service - stores metadata in PostgreSQL and file bytes in the configured storage backend.
    
    This service provides:
    - File upload with local storage support
    - File metadata management
    - File content retrieval from local storage or server
    - File deletion with local cleanup
    - File synchronization between local and server
    - Storage statistics and cleanup
    """

    def __init__(self, db: AsyncSession, cache=None):
        """
        Initialize file service.
        
        Args:
            db: AsyncSession for database operations
            cache: Optional cache instance (Redis or similar)
        """
        self.db = db
        self.file_repo = FileRepository(db)
        self.op_repo = OperationRepository(db)
        self.cache = cache
        self.storage = storage
        self.engine = DataEngine()
        
        # Maximum file size for local storage (100MB)
        self.MAX_LOCAL_SIZE = 100 * 1024 * 1024  # 100MB
        
        # Maximum file size for upload (500MB)
        self.MAX_UPLOAD_SIZE = 500 * 1024 * 1024  # 500MB
        
        # Supported formats for local storage
        self.SUPPORTED_FORMATS = {
            'xlsx', 'xls', 'xlsm', 'xlsb', 'ods', 'csv', 'tsv', 'txt',
            'json', 'xml', 'yaml', 'yml', 'parquet', 'feather', 'arrow',
            'sqlite', 'db', 'sql', 'docx', 'doc', 'pdf', 'pptx', 'odt',
            'html', 'htm', 'md', 'rst', 'jpg', 'jpeg', 'png', 'bmp',
            'gif', 'webp', 'svg', 'ico', 'zip', 'gz', 'tar', '7z', 'rar'
        }

    # ============================================================
    # FILE UPLOAD
    # ============================================================

    async def upload(self, file: UploadFile, user_id: int, store_locally: bool = True) -> File:
        """
        Upload file - stores metadata in DB and file content in local storage.
        
        Args:
            file: The uploaded file
            user_id: Owner user ID
            store_locally: Whether to store file content locally (browser)
        
        Returns:
            File: The created file record
        
        Raises:
            ValidationError: If file validation fails
        """
        t0 = time.time()
        
        # Validate file
        await self._validate_file(file)
        
        # Generate unique storage key for local storage
        storage_key = self._generate_storage_key(file.filename, user_id)
        
        # Get file size
        file_size = file.size or 0
        
        # Save file bytes to configured object storage
        try:
            meta = await self.storage.save_upload(file, user_id)
        except Exception as e:
            logger.error(f"Failed to save file to server: {e}")
            raise ValidationError(f"Failed to save file: {str(e)}")
        
        # Create DB record with explicit parameters
        try:
            db_file = await self.file_repo.create(
                owner_id=user_id,
                name=meta.get("name"),
                original_name=meta.get("original_name"),
                path=meta.get("path"),
                size_bytes=meta.get("size_bytes") or file_size,
                format=meta.get("format"),
                mime_type=meta.get("mime_type"),
                storage_key=storage_key,
                is_locally_stored=store_locally,
                storage_backend=meta.get("storage_backend") or "local",
                storage_bucket=meta.get("bucket"),
                storage_object_key=meta.get("object_key"),
                status="READY"
            )
        except Exception as e:
            logger.error(f"Failed to create file record: {e}")
            # Clean up uploaded file
            if meta.get("path") and self.storage.file_exists(meta["path"]):
                self.storage.delete_file(meta["path"])
            raise ValidationError(f"Failed to save file metadata: {str(e)}")
        
        # Try to extract metadata (non-blocking failure)
        await self._extract_file_metadata(db_file, meta)
        
        duration_ms = int((time.time() - t0) * 1000)
        
        # Log operation
        await self._log_operation(
            user_id=user_id,
            file_id=db_file.id,
            operation_type=OperationType.UPLOAD,
            input_path=meta.get("path"),
            result={
                "file_id": db_file.id,
                "storage_key": storage_key,
                "storage_backend": meta.get("storage_backend"),
                "object_key": meta.get("object_key"),
                "store_locally": store_locally
            },
            duration_ms=duration_ms,
            status=OperationStatus.SUCCESS
        )
        
        logger.info(
            f"Uploaded file: {meta.get('original_name', 'unknown')} "
            f"({db_file.size_human}) - Storage Key: {storage_key}"
        )
        return db_file

    # ============================================================
    # FILE RETRIEVAL
    # ============================================================

    async def get_file(self, file_id: int, user_id: int) -> File:
        """
        Get file metadata by ID with authorization.
        
        Args:
            file_id: File ID
            user_id: User ID for authorization
        
        Returns:
            File: The file record
        
        Raises:
            NotFoundError: If file not found
            AuthorizationError: If user is not authorized
        """
        f = await self.file_repo.get_by_id(file_id)
        if not f:
            raise NotFoundError(f"File with ID {file_id} not found")
        if f.owner_id != user_id:
            raise AuthorizationError("You are not authorized to access this file")
        return f

    async def get_file_content(self, file_id: int, user_id: int) -> Optional[bytes]:
        """
        Get file content - tries cache first, then local storage, then server.
        
        Args:
            file_id: File ID
            user_id: User ID for authorization
        
        Returns:
            Optional[bytes]: File content if found
        """
        # Get file metadata
        f = await self.get_file(file_id, user_id)
        
        # Try to get from cache first
        cached_content = await self._get_from_cache(file_id)
        if cached_content:
            logger.info(f"File {file_id} served from cache")
            return cached_content
        
        # Try to get from server
        content = await self._get_from_server(f)
        if content:
            # Cache for future requests
            await self._set_cache(file_id, content)
            return content
        
        logger.warning(f"File {file_id} content not found (path: {f.path})")
        return None

    async def stream_file(self, file_id: int, user_id: int, start: int = 0, end: Optional[int] = None):
        """
        Stream file content - supports range requests.
        
        Args:
            file_id: File ID
            user_id: User ID for authorization
            start: Start byte
            end: End byte
        
        Yields:
            bytes: File chunks
        
        Raises:
            NotFoundError: If file not found on server
        """
        f = await self.get_file(file_id, user_id)
        
        if not self.storage.file_exists(f.path):
            raise NotFoundError("File content not found in storage")
        
        read_path = await self.storage.get_read_path(f.path, user_id)
        chunk_size = 8192
        with open(read_path, 'rb') as fp:
            fp.seek(start)
            bytes_remaining = (end or f.size_bytes) - start
            
            while bytes_remaining > 0:
                chunk = fp.read(min(chunk_size, bytes_remaining))
                if not chunk:
                    break
                bytes_remaining -= len(chunk)
                yield chunk

    async def list_files(
        self,
        user_id: int,
        search: Optional[str] = None,
        format_filter: Optional[str] = None,
        only_local: bool = False,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> tuple[List[File], int]:
        """
        List files with filters and pagination.
        
        Args:
            user_id: User ID
            search: Search query in file name or tags
            format_filter: File format filter
            only_local: Only show files stored locally
            limit: Pagination limit
            offset: Pagination offset
            sort_by: Sort field (created_at, name, size, updated_at)
            sort_order: Sort order (asc, desc)
        
        Returns:
            tuple: List of files and total count
        """
        files, total = await self.file_repo.get_by_owner(
            owner_id=user_id,
            limit=limit,
            offset=offset,
            search=search,
            format_filter=format_filter,
            only_local=only_local,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        # Enrich with local storage status
        for f in files:
            f.is_cached_locally = False
            f.is_available_on_server = self.storage.file_exists(f.path) if hasattr(self.storage, 'file_exists') else False
        
        return files, total

    # ============================================================
    # FILE DOWNLOAD INFORMATION
    # ============================================================

    async def get_download_info(self, file_id: int, user_id: int) -> Dict[str, Any]:
        """
        Get file download information - client will fetch content.
        
        Args:
            file_id: File ID
            user_id: User ID for authorization
        
        Returns:
            Dict: File info for download
        """
        f = await self.get_file(file_id, user_id)
        download_token = self._generate_download_token(file_id, user_id)
        server_available = self.storage.file_exists(f.path)
        
        return {
            "file_id": f.id,
            "name": f.original_name,
            "size": f.size_bytes,
            "size_human": f.size_human,
            "format": f.format,
            "mime_type": f.mime_type,
            "storage_key": getattr(f, 'storage_key', None),
            "download_token": download_token,
            "meta": f.meta,
            "server_available": server_available,
            "storage_backend": getattr(self.storage, "backend_name", "local"),
            "is_favorite": f.is_favorite,
            "is_locally_stored": getattr(f, 'is_locally_stored', False),
            "created_at": f.created_at.isoformat() if f.created_at else None,
            "updated_at": f.updated_at.isoformat() if f.updated_at else None
        }

    # ============================================================
    # FILE MODIFICATION
    # ============================================================

    async def rename_file(self, file_id: int, user_id: int, dto: RenameFileDTO) -> File:
        """Rename file metadata."""
        f = await self.get_file(file_id, user_id)
        return await self.file_repo.update(f, original_name=dto.new_name)

    async def toggle_favorite(self, file_id: int, user_id: int) -> File:
        """Toggle favorite status."""
        f = await self.get_file(file_id, user_id)
        return await self.file_repo.update(f, is_favorite=not f.is_favorite)

    async def update_metadata(self, file_id: int, user_id: int, metadata: Dict[str, Any]) -> File:
        """Update file metadata."""
        f = await self.get_file(file_id, user_id)
        return await self.file_repo.update(f, meta=metadata)

    # ============================================================
    # FILE DELETION
    # ============================================================

    async def delete_file(self, file_id: int, user_id: int, delete_local: bool = True) -> None:
        """
        Delete file - removes from server and optionally local storage.
        
        Args:
            file_id: File ID
            user_id: User ID for authorization
            delete_local: Whether to delete from local storage
        """
        f = await self.get_file(file_id, user_id)
        
        # Delete from server
        if self.storage.file_exists(f.path):
            self.storage.delete_file(f.path)
            logger.info(f"Deleted file from server: {f.path}")
        
        # Delete from cache
        await self._delete_from_cache(file_id)
        
        # Delete from database
        await self.file_repo.delete(f)
        
        # Log the deletion
        await self._log_operation(
            user_id=user_id,
            file_id=file_id,
            operation_type=OperationType.DELETE,
            input_path=f.path,
            result={
                "file_id": file_id,
                "storage_key": getattr(f, 'storage_key', None),
                "delete_local": delete_local
            },
            duration_ms=0,
            status=OperationStatus.SUCCESS
        )
        
        logger.info(f"Deleted file: {f.original_name} (Local: {delete_local})")

    # ============================================================
    # FILE SYNC AND CLEANUP
    # ============================================================

    async def sync_local_files(self, user_id: int, local_files: List[Dict[str, Any]]) -> dict:
        """
        Sync local file status - updates metadata for files stored in browser.
        
        Args:
            user_id: User ID
            local_files: List of local file info {storage_key, file_id, size, modified}
        
        Returns:
            dict: Sync result
        """
        updated = 0
        errors = 0
        
        for local_file in local_files:
            try:
                file_id = local_file.get('file_id')
                storage_key = local_file.get('storage_key')
                modified_at = local_file.get('modified_at')
                
                if not file_id or not storage_key:
                    errors += 1
                    continue
                
                f = await self.file_repo.get_by_id(file_id)
                if f and f.owner_id == user_id:
                    update_data = {
                        'is_locally_stored': True,
                        'last_synced_at': datetime.utcnow()
                    }
                    
                    if modified_at:
                        update_data['meta'] = {
                            **f.meta,
                            'local_modified_at': modified_at
                        }
                    
                    await self.file_repo.update(f, **update_data)
                    updated += 1
                else:
                    errors += 1
                    
            except Exception as e:
                logger.error(f"Sync error for file {local_file.get('file_id')}: {e}")
                errors += 1
        
        return {
            "synced": updated,
            "errors": errors,
            "total": len(local_files),
            "timestamp": datetime.utcnow().isoformat()
        }

    async def cleanup_unused_files(self, days: int = 30) -> dict:
        """Clean up old files not accessed for X days."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        old_files = await self.file_repo.get_old_files(None, days)
        
        deleted = 0
        deleted_files = []
        
        for f in old_files:
            try:
                if self.storage.file_exists(f.path):
                    self.storage.delete_file(f.path)
                
                await self.file_repo.delete(f)
                deleted += 1
                deleted_files.append(f.original_name)
                logger.info(f"Cleaned up old file: {f.original_name} (ID: {f.id})")
            except Exception as e:
                logger.error(f"Failed to clean up file {f.id}: {e}")
        
        return {
            "deleted": deleted,
            "deleted_files": deleted_files[:10],
            "cutoff_date": cutoff.isoformat()
        }

    # ============================================================
    # FILE PREVIEW AND STATISTICS
    # ============================================================

    async def get_preview(self, file_id: int, user_id: int, rows: int = 100) -> dict:
        """Get file preview (for supported formats)."""
        f = await self.get_file(file_id, user_id)
        
        if not self.storage.file_exists(f.path):
            raise NotFoundError("File content not available in storage")
        
        read_path = await self.storage.get_read_path(f.path, user_id)
        return self.engine.preview(read_path, f.format, rows=rows)

    async def get_storage_stats(self, user_id: int) -> dict:
        """Get storage statistics for user."""
        return await self.file_repo.get_storage_stats(user_id)

    # ============================================================
    # VALIDATION METHODS
    # ============================================================

    async def _validate_file(self, file: UploadFile) -> None:
        """
        Validate uploaded file.
        
        Args:
            file: Uploaded file
        
        Raises:
            ValidationError: If validation fails
        """
        if file.size and file.size > self.MAX_UPLOAD_SIZE:
            raise ValidationError(
                f"File too large. Maximum size is {self.MAX_UPLOAD_SIZE // (1024*1024)}MB"
            )
        
        if file.filename:
            ext = file.filename.split('.')[-1].lower()
            if ext not in self.SUPPORTED_FORMATS:
                logger.warning(f"Unsupported file format: {ext}")
        
        if file.filename and ('..' in file.filename or '/' in file.filename or '\\' in file.filename):
            raise ValidationError("Invalid file name")

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
        token_data = f"{file_id}_{user_id}_{int(time.time())}_{os.urandom(8).hex()}"
        return hashlib.sha256(token_data.encode()).hexdigest()[:32]

    async def _extract_file_metadata(self, db_file: File, meta: dict) -> None:
        """Extract metadata from file (non-blocking)."""
        try:
            read_path = await self.storage.get_read_path(meta.get("path"), db_file.owner_id)
            file_meta = self.engine.get_metadata(read_path, meta.get("format"))
            if file_meta:
                await self.file_repo.update(db_file, meta={**db_file.meta, **file_meta})
                logger.info(f"Extracted metadata for file {db_file.id}: {file_meta}")
        except Exception as e:
            logger.warning(f"Metadata extraction failed for {meta.get('name', 'unknown')}: {e}")

    async def _log_operation(
        self,
        user_id: int,
        file_id: int,
        operation_type: OperationType,
        input_path: Optional[str] = None,
        result: Optional[dict] = None,
        duration_ms: int = 0,
        status: OperationStatus = OperationStatus.SUCCESS
    ) -> None:
        """Log an operation."""
        try:
            op = await self.op_repo.create(
                type=operation_type,
                user_id=user_id,
                file_id=file_id,
                input_path=input_path,
            )
            await self.op_repo.mark_complete(
                op, status,
                result=result or {},
                duration_ms=duration_ms,
            )
        except Exception as e:
            logger.error(f"Failed to log operation: {e}")

    async def _get_from_cache(self, file_id: int) -> Optional[bytes]:
        """Get file content from cache."""
        if not self.cache:
            return None
        try:
            return await self.cache.get_file_content(file_id)
        except Exception as e:
            logger.warning(f"Cache get failed: {e}")
            return None

    async def _set_cache(self, file_id: int, content: bytes, ttl: int = 300) -> None:
        """Set file content in cache."""
        if not self.cache:
            return
        try:
            await self.cache.cache_file_content(file_id, content, ttl=ttl)
        except Exception as e:
            logger.warning(f"Cache set failed: {e}")

    async def _delete_from_cache(self, file_id: int) -> None:
        """Delete file content from cache."""
        if not self.cache:
            return
        try:
            await self.cache.delete_file_content(file_id)
        except Exception as e:
            logger.warning(f"Cache delete failed: {e}")

    async def _get_from_server(self, file: File) -> Optional[bytes]:
        """Get file content from server."""
        if not self.storage.file_exists(file.path):
            return None
        try:
            read_path = await self.storage.get_read_path(file.path, file.owner_id)
            with open(read_path, 'rb') as fp:
                return fp.read()
        except Exception as e:
            logger.error(f"Failed to read file from server {file.path}: {e}")
            return None
