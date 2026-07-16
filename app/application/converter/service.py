"""Conversion application service."""

import logging
import time
import uuid
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, AuthorizationError, ProcessingError, UnsupportedFormatError
from app.core.config import settings
from app.infrastructure.repositories.file_repository import FileRepository
from app.infrastructure.repositories.operation_repository import OperationRepository
from app.infrastructure.database.models import OperationType, OperationStatus
from app.infrastructure.storage.local_storage import storage
from app.application.converter.engine import DataEngine
from app.application.converter.dto import ConvertRequestDTO, ConvertResultDTO

logger = logging.getLogger(__name__)

EXPORT_FORMATS = [
    "xlsx", "csv", "json", "xml", "yaml", "parquet", "feather",
    "ods", "html", "tsv", "sqlite", "docx",
]


class ConverterService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.file_repo = FileRepository(db)
        self.op_repo = OperationRepository(db)
        self.engine = DataEngine()

    async def convert(self, dto: ConvertRequestDTO, user_id: int) -> ConvertResultDTO:
        # Validate target format
        if dto.target_format.lower() not in EXPORT_FORMATS:
            raise UnsupportedFormatError(dto.target_format)

        # Fetch source file
        f = await self.file_repo.get_by_id(dto.file_id)
        if not f:
            raise NotFoundError("File")
        if f.owner_id != user_id:
            raise AuthorizationError()

        # Log operation start
        op = await self.op_repo.create(
            type=OperationType.CONVERT,
            user_id=user_id,
            file_id=f.id,
            input_path=f.path,
            params=dto.model_dump(),
        )

        t0 = time.time()
        try:
            df = self.engine.read(f.path, f.format, sheet=dto.sheet)
            rows, cols = df.shape

            # Build output path
            stem = Path(f.original_name).stem
            out_name = f"{stem}_{uuid.uuid4().hex[:6]}.{dto.target_format.lower()}"
            out_path = storage.get_output_path(user_id, out_name)

            self.engine.write(df, str(out_path), dto.target_format)

            duration_ms = int((time.time() - t0) * 1000)
            await self.op_repo.mark_complete(
                op, OperationStatus.SUCCESS,
                result={"rows": rows, "columns": cols, "output": str(out_path)},
                output_path=str(out_path),
                duration_ms=duration_ms,
            )

            logger.info(f"Converted {f.original_name} → {dto.target_format} ({rows} rows)")
            return ConvertResultDTO(
                output_path=str(out_path),
                output_filename=out_name,
                rows=rows,
                columns=cols,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((time.time() - t0) * 1000)
            await self.op_repo.mark_complete(
                op, OperationStatus.FAILED,
                error=str(e),
                duration_ms=duration_ms,
            )
            raise ProcessingError(str(e))
