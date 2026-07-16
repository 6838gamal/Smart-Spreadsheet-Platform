"""File management application service."""

import logging
import time
from pathlib import Path
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, AuthorizationError
from app.infrastructure.repositories.file_repository import FileRepository
from app.infrastructure.repositories.operation_repository import OperationRepository
from app.infrastructure.database.models import File, OperationType, OperationStatus
from app.infrastructure.storage.local_storage import storage
from app.application.files.dto import RenameFileDTO
from app.application.converter.engine import DataEngine

logger = logging.getLogger(__name__)


class FileService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.file_repo = FileRepository(db)
        self.op_repo = OperationRepository(db)

    async def upload(self, file: UploadFile, user_id: int) -> File:
        t0 = time.time()
        meta = await storage.save_upload(file, user_id)

        # Create DB record
        db_file = await self.file_repo.create(
            owner_id=user_id,
            **meta,
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
            result={"file_id": db_file.id},
            duration_ms=duration_ms,
        )

        logger.info(f"Uploaded file: {meta['original_name']} ({db_file.size_human})")
        return db_file

    async def get_file(self, file_id: int, user_id: int) -> File:
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
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[File], int]:
        files = await self.file_repo.get_by_owner(
            user_id, limit=limit, offset=offset,
            search=search, format_filter=format_filter,
        )
        total = await self.file_repo.count_by_owner(user_id)
        return files, total

    async def delete_file(self, file_id: int, user_id: int) -> None:
        f = await self.get_file(file_id, user_id)
        storage.delete_file(f.path)
        await self.file_repo.delete(f)
        logger.info(f"Deleted file: {f.original_name}")

    async def rename_file(self, file_id: int, user_id: int, dto: RenameFileDTO) -> File:
        f = await self.get_file(file_id, user_id)
        return await self.file_repo.update(f, name=dto.new_name)

    async def toggle_favorite(self, file_id: int, user_id: int) -> File:
        f = await self.get_file(file_id, user_id)
        return await self.file_repo.update(f, is_favorite=not f.is_favorite)

    async def get_preview(self, file_id: int, user_id: int, rows: int = 100) -> dict:
        f = await self.get_file(file_id, user_id)
        engine = DataEngine()
        return engine.preview(f.path, f.format, rows=rows)
