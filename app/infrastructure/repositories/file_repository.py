"""File repository — data access for File model."""

from sqlalchemy import select, func, desc, asc, or_
from app.infrastructure.repositories.base import BaseRepository
from app.infrastructure.database.models import File, FileStatus


class FileRepository(BaseRepository[File]):
    """Repository for File model with advanced query capabilities."""
    
    model = File

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
    ) -> tuple[list[File], int]:
        """
        Get files by owner with filters, sorting, and pagination.
        
        Args:
            owner_id: Owner user ID
            limit: Number of records to return
            offset: Number of records to skip
            search: Search query in file name or tags
            format_filter: Filter by file format
            only_local: Only show files stored locally
            sort_by: Sort field (created_at, name, size, updated_at)
            sort_order: Sort order (asc, desc)
        
        Returns:
            Tuple of (list of files, total count)
        """
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
        
        # Apply local storage filter
        if only_local:
            q = q.where(File.is_locally_stored == True)
        
        # Get total count first (before pagination)
        count_query = select(func.count()).select_from(q.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()
        
        # Apply sorting
        if sort_by == "name":
            sort_column = File.original_name
        elif sort_by == "size":
            sort_column = File.size_bytes
        elif sort_by == "updated_at":
            sort_column = File.updated_at
        else:  # created_at (default)
            sort_column = File.created_at
        
        if sort_order == "asc":
            q = q.order_by(asc(sort_column))
        else:
            q = q.order_by(desc(sort_column))
        
        # Apply pagination
        q = q.limit(limit).offset(offset)
        
        # Execute query
        result = await self.db.execute(q)
        files = list(result.scalars().all())
        
        return files, total

    async def count_by_owner(self, owner_id: int) -> int:
        """Count total files for owner."""
        result = await self.db.execute(
            select(func.count()).select_from(File).where(File.owner_id == owner_id)
        )
        return result.scalar_one()

    async def total_size_by_owner(self, owner_id: int) -> int:
        """Get total file size for owner."""
        result = await self.db.execute(
            select(func.coalesce(func.sum(File.size_bytes), 0)).where(File.owner_id == owner_id)
        )
        return result.scalar_one()

    async def get_favorites(self, owner_id: int, limit: int = 10) -> list[File]:
        """Get favorite files for owner."""
        result = await self.db.execute(
            select(File)
            .where(File.owner_id == owner_id, File.is_favorite == True)
            .order_by(desc(File.updated_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_recent(self, owner_id: int, limit: int = 8) -> list[File]:
        """Get most recent files for owner."""
        result = await self.db.execute(
            select(File)
            .where(File.owner_id == owner_id)
            .order_by(desc(File.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_format_counts(self, owner_id: int) -> dict[str, int]:
        """Get file format statistics for owner."""
        result = await self.db.execute(
            select(File.format, func.count(File.id))
            .where(File.owner_id == owner_id)
            .group_by(File.format)
        )
        return {row[0] or 'unknown': row[1] for row in result.all()}

    # ============================================================
    # ADDITIONAL HELPER METHODS
    # ============================================================

    async def get_by_storage_key(self, storage_key: str) -> File | None:
        """Get file by storage key."""
        result = await self.db.execute(
            select(File).where(File.storage_key == storage_key)
        )
        return result.scalar_one_or_none()

    async def get_old_files(
        self,
        owner_id: int,
        days: int = 30,
        exclude_favorites: bool = True
    ) -> list[File]:
        """Get old files not accessed for X days."""
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        q = select(File).where(
            File.owner_id == owner_id,
            File.created_at < cutoff
        )
        
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
    ) -> list[File]:
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
        file_ids: list[int],
        owner_id: int
    ) -> list[File]:
        """Get multiple files by IDs."""
        result = await self.db.execute(
            select(File)
            .where(File.id.in_(file_ids))
            .where(File.owner_id == owner_id)
        )
        return list(result.scalars().all())

    async def delete_bulk(
        self,
        file_ids: list[int],
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
        file = await self.get_by_id(file_id)
        if file:
            file.is_locally_stored = is_locally_stored
            await self.db.commit()
            await self.db.refresh(file)
        return file

    async def get_storage_stats(self, owner_id: int) -> dict:
        """Get detailed storage statistics for owner."""
        # Total files and size
        total_files = await self.count_by_owner(owner_id)
        total_size = await self.total_size_by_owner(owner_id)
        
        # Local vs cloud
        local_count_result = await self.db.execute(
            select(func.count())
            .select_from(File)
            .where(File.owner_id == owner_id, File.is_locally_stored == True)
        )
        local_count = local_count_result.scalar_one()
        
        # Favorites count
        favorites_result = await self.db.execute(
            select(func.count())
            .select_from(File)
            .where(File.owner_id == owner_id, File.is_favorite == True)
        )
        favorites_count = favorites_result.scalar_one()
        
        # Format distribution
        format_counts = await self.get_by_format_counts(owner_id)
        
        return {
            "total_files": total_files,
            "total_size_bytes": total_size,
            "locally_stored": local_count,
            "cloud_files": total_files - local_count,
            "favorites": favorites_count,
            "formats": format_counts
        }
