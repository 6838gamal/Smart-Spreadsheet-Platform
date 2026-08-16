"""File management application service with hybrid storage (local + server)."""

import logging
import time
import json
import hashlib
import os
from pathlib import Path
from typing import Optional, Dict, Any, List, BinaryIO
from datetime import datetime, timedelta
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, AuthorizationError, ValidationError
from app.infrastructure.repositories.file_repository import FileRepository
from app.infrastructure.repositories.operation_repository import OperationRepository
from app.infrastructure.database.models import File, OperationType, OperationStatus
from app.infrastructure.storage.local_storage import storage
from app.application.files.dto import RenameFileDTO, FileMetaDTO
from app.application.converter.engine import DataEngine

logger = logging.getLogger(__name__)


class FileService:
    """
    Hybrid file service - stores metadata in DB, actual files in local storage (browser).
    
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
            # Spreadsheets
            'xlsx', 'xls', 'xlsm', 'xlsb', 'ods', 
            'csv', 'tsv', 'txt',
            # Data formats
            'json', 'xml', 'yaml', 'yml', 
            'parquet', 'feather', 'arrow',
            # Databases
            'sqlite', 'db', 'sql',
            # Documents
            'docx', 'doc', 'pdf', 'pptx', 'odt',
            # Web
            'html', 'htm', 'md', 'rst',
            # Images
            'jpg', 'jpeg', 'png', 'bmp', 'gif', 'webp', 'svg', 'ico',
            # Other
            'zip', 'gz', 'tar', '7z', 'rar'
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
        
        # Save file to server (temporary/backup)
        try:
            meta = await storage.save_upload(file, user_id)
        except Exception as e:
            logger.error(f"Failed to save file to server: {e}")
            raise ValidationError(f"Failed to save file: {str(e)}")
        
        # Create DB record with storage key
        try:
            db_file = await self.file_repo.create(
                owner_id=user_id,
                **meta,
                storage_key=storage_key,
                is_locally_stored=store_locally,
                size_bytes=file_size,
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
        
        Raises:
            NotFoundError: If file not found
            AuthorizationError: If user is not authorized
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
        
        # File not found
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
            raise NotFoundError("File content not found on server. Please sync your local copy.")
        
        chunk_size = 8192
        with open(f.path, 'rb') as fp:
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
        # Now the repository returns tuple (files, total)
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
            f.is_cached_locally = await self._is_file_cached_locally(f.storage_key)
            f.is_available_on_server = self.storage.file_exists(f.path)
        
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
        
        Raises:
            NotFoundError: If file not found
            AuthorizationError: If user is not authorized
        """
        f = await self.get_file(file_id, user_id)
        
        # Generate download token (for secure access)
        download_token = self._generate_download_token(file_id, user_id)
        
        # Check if file exists on server
        server_available = self.storage.file_exists(f.path)
        
        return {
            "file_id": f.id,
            "name": f.original_name,
            "size": f.size_bytes,
            "size_human": f.size_human,
            "format": f.format,
            "mime_type": f.mime_type,
            "storage_key": f.storage_key,
            "download_token": download_token,
            "meta": f.meta,
            "server_available": server_available,
            "is_favorite": f.is_favorite,
            "created_at": f.created_at.isoformat() if f.created_at else None,
            "updated_at": f.updated_at.isoformat() if f.updated_at else None
        }

    # ============================================================
    # FILE MODIFICATION
    # ============================================================

    async def rename_file(self, file_id: int, user_id: int, dto: RenameFileDTO) -> File:
        """
        Rename file metadata.
        
        Args:
            file_id: File ID
            user_id: User ID for authorization
            dto: Rename data
        
        Returns:
            File: Updated file record
        """
        f = await self.get_file(file_id, user_id)
        return await self.file_repo.update(f, original_name=dto.new_name)

    async def toggle_favorite(self, file_id: int, user_id: int) -> File:
        """
        Toggle favorite status.
        
        Args:
            file_id: File ID
            user_id: User ID for authorization
        
        Returns:
            File: Updated file record
        """
        f = await self.get_file(file_id, user_id)
        return await self.file_repo.update(f, is_favorite=not f.is_favorite)

    async def update_metadata(self, file_id: int, user_id: int, metadata: Dict[str, Any]) -> File:
        """
        Update file metadata.
        
        Args:
            file_id: File ID
            user_id: User ID for authorization
            metadata: New metadata
        
        Returns:
            File: Updated file record
        """
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
            delete_local: Whether to delete from local storage (client should handle)
        
        Raises:
            NotFoundError: If file not found
            AuthorizationError: If user is not authorized
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
                "storage_key": f.storage_key,
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
                file_size = local_file.get('size', 0)
                modified_at = local_file.get('modified_at')
                
                if not file_id or not storage_key:
                    errors += 1
                    continue
                
                # Check if file exists and belongs to user
                f = await self.file_repo.get_by_id(file_id)
                if f and f.owner_id == user_id:
                    # Update local storage status
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
        """
        Clean up old files not accessed for X days.
        
        Args:
            days: Number of days to keep files
        
        Returns:
            dict: Cleanup results
        """
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        # Get old files (all users)
        old_files = await self.file_repo.get_old_files(None, days)  # None = all users
        
        deleted = 0
        deleted_files = []
        
        for f in old_files:
            try:
                # Delete from storage
                if self.storage.file_exists(f.path):
                    self.storage.delete_file(f.path)
                
                # Delete from database
                await self.file_repo.delete(f)
                deleted += 1
                deleted_files.append(f.original_name)
                
                logger.info(f"Cleaned up old file: {f.original_name} (ID: {f.id})")
            except Exception as e:
                logger.error(f"Failed to clean up file {f.id}: {e}")
        
        return {
            "deleted": deleted,
            "deleted_files": deleted_files[:10],  # First 10
            "cutoff_date": cutoff.isoformat()
        }

    # ============================================================
    # FILE PREVIEW AND STATISTICS
    # ============================================================

    async def get_preview(self, file_id: int, user_id: int, rows: int = 100) -> dict:
        """
        Get file preview (for supported formats).
        
        Args:
            file_id: File ID
            user_id: User ID for authorization
            rows: Number of rows to preview
        
        Returns:
            dict: File preview data
        
        Raises:
            NotFoundError: If file not found on server
        """
        f = await self.get_file(file_id, user_id)
        
        # Check if file exists on server
        if not self.storage.file_exists(f.path):
            raise NotFoundError("File content not available on server")
        
        return self.engine.preview(f.path, f.format, rows=rows)

    async def get_storage_stats(self, user_id: int) -> dict:
        """
        Get storage statistics for user.
        
        Args:
            user_id: User ID
        
        Returns:
            dict: Storage usage statistics
        """
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
        # Check file size
        if file.size and file.size > self.MAX_UPLOAD_SIZE:
            raise ValidationError(
                f"File too large. Maximum size is {self.MAX_UPLOAD_SIZE // (1024*1024)}MB"
            )
        
        # Check file format
        if file.filename:
            ext = file.filename.split('.')[-1].lower()
            if ext not in self.SUPPORTED_FORMATS:
                logger.warning(f"Unsupported file format: {ext}")
                # Allow anyway but warn
                # raise ValidationError(f"Unsupported file format: {ext}")
        
        # Validate file name (security)
        if file.filename and ('..' in file.filename or '/' in file.filename or '\\' in file.filename):
            raise ValidationError("Invalid file name")

    # ============================================================
    # PRIVATE METHODS
    # ============================================================

    def _generate_storage_key(self, filename: str, user_id: int) -> str:
        """
        Generate unique storage key for local storage.
        
        Args:
            filename: Original filename
            user_id: User ID
        
        Returns:
            str: Unique storage key
        """
        timestamp = int(time.time() * 1000)
        file_hash = hashlib.md5(f"{filename}_{user_id}_{timestamp}".encode()).hexdigest()[:16]
        return f"file_{user_id}_{file_hash}_{timestamp}"

    def _generate_download_token(self, file_id: int, user_id: int) -> str:
        """
        Generate secure download token.
        
        Args:
            file_id: File ID
            user_id: User ID
        
        Returns:
            str: Download token
        """
        token_data = f"{file_id}_{user_id}_{int(time.time())}_{os.urandom(8).hex()}"
        return hashlib.sha256(token_data.encode()).hexdigest()[:32]

    async def _is_file_cached_locally(self, storage_key: str) -> bool:
        """
        Check if file is stored in local storage (IndexedDB).
        
        Args:
            storage_key: Storage key
        
        Returns:
            bool: True if file is cached locally
        """
        # This is client-side check - server can only guess
        # We return False by default, client will handle actual check
        return False

    async def _extract_file_metadata(self, db_file: File, meta: dict) -> None:
        """
        Extract metadata from file (non-blocking).
        
        Args:
            db_file: File record
            meta: File metadata from upload
        """
        try:
            file_meta = self.engine.get_metadata(meta.get("path"), meta.get("format"))
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
        """
        Log an operation.
        
        Args:
            user_id: User ID
            file_id: File ID
            operation_type: Operation type
            input_path: Input file path
            result: Operation result
            duration_ms: Duration in milliseconds
            status: Operation status
        """
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
        """
        Get file content from cache.
        
        Args:
            file_id: File ID
        
        Returns:
            Optional[bytes]: Cached content
        """
        if not self.cache:
            return None
        
        try:
            return await self.cache.get_file_content(file_id)
        except Exception as e:
            logger.warning(f"Cache get failed: {e}")
            return None

    async def _set_cache(self, file_id: int, content: bytes, ttl: int = 300) -> None:
        """
        Set file content in cache.
        
        Args:
            file_id: File ID
            content: File content
            ttl: Time to live in seconds
        """
        if not self.cache:
            return
        
        try:
            await self.cache.cache_file_content(file_id, content, ttl=ttl)
        except Exception as e:
            logger.warning(f"Cache set failed: {e}")

    async def _delete_from_cache(self, file_id: int) -> None:
        """
        Delete file content from cache.
        
        Args:
            file_id: File ID
        """
        if not self.cache:
            return
        
        try:
            await self.cache.delete_file_content(file_id)
        except Exception as e:
            logger.warning(f"Cache delete failed: {e}")

    async def _get_from_server(self, file: File) -> Optional[bytes]:
        """
        Get file content from server.
        
        Args:
            file: File record
        
        Returns:
            Optional[bytes]: File content
        """
        if not self.storage.file_exists(file.path):
            return None
        
        try:
            with open(file.path, 'rb') as fp:
                return fp.read()
        except Exception as e:
            logger.error(f"Failed to read file from server {file.path}: {e}")
            return None
