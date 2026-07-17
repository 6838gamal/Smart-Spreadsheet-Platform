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
from app.application.converter.engine import DataEngine, DIRECT_PAIRS
from app.application.converter.dto import ConvertRequestDTO, ConvertResultDTO

logger = logging.getLogger(__name__)

# Formats available as export targets in the UI
EXPORT_FORMATS = [
    "xlsx", "csv", "json", "xml", "yaml", "parquet", "feather",
    "ods", "html", "tsv", "sqlite", "docx", "pdf",
    "pptx",
    "png", "jpg",
    "svg",
]


class ConverterService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.file_repo = FileRepository(db)
        self.op_repo = OperationRepository(db)
        self.engine = DataEngine()

    async def convert(self, dto: ConvertRequestDTO, user_id: int) -> ConvertResultDTO:
        target_fmt = dto.target_format.lower()

        # Validate target format
        if target_fmt not in EXPORT_FORMATS:
            raise UnsupportedFormatError(dto.target_format)

        # Fetch source file
        f = await self.file_repo.get_by_id(dto.file_id)
        if not f:
            raise NotFoundError("File")
        if f.owner_id != user_id:
            raise AuthorizationError()

        src_fmt = f.format.lower().lstrip(".")

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
            # Determine output filename/extension
            stem = Path(f.original_name).stem
            out_name = f"{stem}_{uuid.uuid4().hex[:6]}.{target_fmt}"
            out_path = storage.get_output_path(user_id, out_name)

            is_direct = (src_fmt, target_fmt) in DIRECT_PAIRS

            if is_direct:
                # Non-tabular direct conversion (image↔PDF, SVG↔PDF)
                actual_path = self.engine.convert_direct(
                    f.path, src_fmt, str(out_path), target_fmt
                )
                # actual_path may differ (e.g. multi-page PDF→images becomes a .zip)
                actual_name = Path(actual_path).name
                rows, cols = 0, 0
            else:
                # Tabular path: read → DataFrame → write
                df = self.engine.read(f.path, src_fmt, sheet=dto.sheet)
                rows, cols = df.shape
                self.engine.write(df, str(out_path), target_fmt)
                actual_path = str(out_path)
                actual_name = out_name

            duration_ms = int((time.time() - t0) * 1000)
            await self.op_repo.mark_complete(
                op, OperationStatus.SUCCESS,
                result={"rows": rows, "columns": cols, "output": actual_path},
                output_path=actual_path,
                duration_ms=duration_ms,
            )

            logger.info(f"Converted {f.original_name} → {target_fmt} ({rows} rows, {duration_ms}ms)")
            return ConvertResultDTO(
                output_path=actual_path,
                output_filename=actual_name,
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
