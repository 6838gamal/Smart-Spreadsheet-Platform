"""File repository — data access for File model."""

import logging
from typing import Optional, List, Tuple
from datetime import datetime, timedelta

from sqlalchemy import select, func, desc, asc, or_, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.repositories.base import BaseRepository
from app.infrastructure.database.models import File, FileStatus

logger = logging.getLogger(__name__)


class FileRepository(BaseRepository[File]):
    """Repository for File model with safe column access."""
    
    model = File

    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self._has_storage_columns = None

    async def _check_storage_columns(self) -> bool:
        """
        Check if storage columns exist in the database.
        Uses information_schema for safe checking.
        """
        if self._has_storage_columns is not None:
            return self._has_storage_columns
        
        try:
            # استخدام information_schema للتحقق من وجود الأعمدة
            result = await self.db.execute(
                text("""
                    SELECT EXISTS (
                        SELECT 1 
                        FROM information_schema.columns 
                        WHERE table_name = 'files' 
                        AND column_name = 'storage_key'
                    )
                """)
            )
            exists = result.scalar()
            
            self._has_storage_columns = exists
            if exists:
                logger.info("Storage columns found in files table")
            else:
                logger.warning("Storage columns not found in files table")
            
            return exists
            
        except Exception as e:
            logger.error(f"Error checking storage columns: {e}")
            self._has_storage_columns = False
            return False

    async def get_by_owner(
        self,
        owner_id: int,
        limit: int = 50,
        offset: int = 0,
        search: str | None = None,
        format_filter: str | None = None,
        only_local: bool = False,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> Tuple[List[File], int]:
        """
        Get files by owner with filters, sorting, and pagination.
        """
        has_storage = await self._check_storage_columns()
        
        # Build base query
        q = select(File).where(File.owner_id == owner_id)
        
        # Apply search filter
        if search:
            q = q.where(
                or_(
                    File.original_name.ilike(f"%{search}%"),
                    File.name.ilike(f"%{search}%")
                )
            )
        
        # Apply format filter
        if format_filter:
            q = q.where(File.format == format_filter)
        
        # Apply local storage filter (only if column exists)
        if only_local and has_storage:
            q = q.where(File.is_locally_stored == True)
        
        # Get total count
        count_query = select(func.count()).select_from(q.subquery())
        try:
            total_result = await self.db.execute(count_query)
            total = total_result.scalar_one()
        except Exception as e:
            logger.error(f"Error getting total count: {e}")
            raise
        
        # Apply sorting
        if sort_by == "name":
            sort_column = File.original_name
        elif sort_by == "size":
            sort_column = File.size_bytes
        elif sort_by == "updated_at":
            sort_column = File.updated_at
        else:
            sort_column = File.created_at
        
        if sort_order == "asc":
            q = q.order_by(asc(sort_column))
        else:
            q = q.order_by(desc(sort_column))
        
        # Apply pagination
        q = q.limit(limit).offset(offset)
        
        try:
            result = await self.db.execute(q)
            files = list(result.scalars().all())
            return files, total
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            raise

    async def count_by_owner(self, owner_id: int) -> int:
        """Count total files for owner."""
        result = await self.db.execute(
            select(func.count()).select_from(File).where(File.owner_id == owner_id)
        )
        return result.scalar_one()

    async def total_size_by_owner(self, owner_id: int) -> int:
        """Get total file size for owner."""
        result = await self.db.execute(
            select(func.coalesce(func.sum(File.size_bytes), 0))
            .where(File.owner_id == owner_id)
        )
        return result.scalar_one()

    async def get_favorites(self, owner_id: int, limit: int = 10) -> List[File]:
        """Get favorite files for owner."""
        result = await self.db.execute(
            select(File)
            .where(File.owner_id == owner_id, File.is_favorite == True)
            .order_by(desc(File.updated_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_recent(self, owner_id: int, limit: int = 8) -> List[File]:
        """Get most recent files for owner."""
        has_storage = await self._check_storage_columns()
        
        # Build columns list
        columns = [
            File.id, File.name, File.original_name, File.path,
            File.size_bytes, File.format, File.mime_type, File.status,
            File.is_favorite, File.tags, File.meta, File.owner_id,
            File.created_at, File.updated_at
        ]
        
        if has_storage:
            columns.extend([File.storage_key, File.is_locally_stored, File.last_synced_at])
        
        stmt = select(*columns).where(File.owner_id == owner_id)
        stmt = stmt.order_by(desc(File.created_at)).limit(limit)
        
        try:
            result = await self.db.execute(stmt)
            rows = result.all()
            
            files = []
            for row in rows:
                file_data = {}
                for i, col in enumerate(columns):
                    file_data[col.key] = row[i]
                file = File(**file_data)
                files.append(file)
            
            return files
            
        except Exception as e:
            logger.error(f"Error in get_recent: {e}")
            raise

    async def get_by_format_counts(self, owner_id: int) -> dict[str, int]:
        """Get file format statistics for owner."""
        result = await self.db.execute(
            select(File.format, func.count(File.id))
            .where(File.owner_id == owner_id)
            .group_by(File.format)
        )
        return {row[0] or 'unknown': row[1] for row in result.all()}

    async def get_by_storage_key(self, storage_key: str) -> File | None:
        """Get file by storage key if column exists."""
        if not await self._check_storage_columns():
            return None
        result = await self.db.execute(
            select(File).where(File.storage_key == storage_key)
        )
        return result.scalar_one_or_none()

    async def get_old_files(
        self,
        owner_id: int | None = None,
        days: int = 30,
        exclude_favorites: bool = True
    ) -> List[File]:
        """Get old files not accessed for X days."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        q = select(File).where(File.created_at < cutoff)
        
        if owner_id is not None:
            q = q.where(File.owner_id == owner_id)
        
        if exclude_favorites:
            q = q.where(File.is_favorite == False)
        
        q = q.order_by(File.created_at)
        
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def search_files(
        self,
        owner_id: int,
        query: str,
        limit: int = 20
    ) -> List[File]:
        """Search files by name or tags."""
        result = await self.db.execute(
            select(File)
            .where(File.owner_id == owner_id)
            .where(
                or_(
                    File.original_name.ilike(f"%{query}%"),
                    File.name.ilike(f"%{query}%")
                )
            )
            .order_by(desc(File.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_files_by_ids(
        self,
        file_ids: List[int],
        owner_id: int
    ) -> List[File]:
        """Get multiple files by IDs."""
        result = await self.db.execute(
            select(File)
            .where(File.id.in_(file_ids))
            .where(File.owner_id == owner_id)
        )
        return list(result.scalars().all())

    async def delete_bulk(
        self,
        file_ids: List[int],
        owner_id: int
    ) -> int:
        """Delete multiple files."""
        files = await self.get_files_by_ids(file_ids, owner_id)
        count = len(files)
        
        for file in files:
            await self.db.delete(file)
        
        await self.db.commit()
        return count

    async def update_storage_status(
        self,
        file_id: int,
        is_locally_stored: bool
    ) -> File | None:
        """Update local storage status of a file."""
        if not await self._check_storage_columns():
            return None
            
        file = await self.get_by_id(file_id)
        if file:
            file.is_locally_stored = is_locally_stored
            await self.db.commit()
            await self.db.refresh(file)
        return file

    async def get_storage_stats(self, owner_id: int) -> dict:
        """Get detailed storage statistics for owner."""
        total_files = await self.count_by_owner(owner_id)
        total_size = await self.total_size_by_owner(owner_id)
        
        local_count = 0
        if await self._check_storage_columns():
            local_count_result = await self.db.execute(
                select(func.count())
                .select_from(File)
                .where(File.owner_id == owner_id, File.is_locally_stored == True)
            )
            local_count = local_count_result.scalar_one()
        
        favorites_result = await self.db.execute(
            select(func.count())
            .select_from(File)
            .where(File.owner_id == owner_id, File.is_favorite == True)
        )
        favorites_count = favorites_result.scalar_one()
        
        format_counts = await self.get_by_format_counts(owner_id)
        
        return {
            "total_files": total_files,
            "total_size_bytes": total_size,
            "locally_stored": local_count,
            "cloud_files": total_files - local_count,
            "favorites": favorites_count,
            "formats": format_counts
        }
