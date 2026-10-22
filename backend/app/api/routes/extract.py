"""
Extraction Endpoints
═══════════════════════════════════════════════════════════════════════════════

POST /api/v1/extract/text   — extract from raw text body
POST /api/v1/extract/file   — extract from uploaded file (PDF/DOCX/TXT/image)
POST /api/v1/extract/batch  — extract multiple texts in parallel (up to 5)

All results are persisted to SQLite history.
"""

import json
import asyncio
import logging
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert

from app.database import get_db, ExtractionRecord
from app.models.schemas import (
    ExtractionRequest, ExtractionResponse, DocumentType,
)
from app.services.extractor import extract_structured
from app.services.file_processor import process_file

router = APIRouter()
logger = logging.getLogger(__name__)


# ─── Utility ─────────────────────────────────────────────────────────────────

async def _persist(result: ExtractionResponse, db: AsyncSession) -> int:
    """Save extraction result to SQLite; return the new row id."""
    stmt = insert(ExtractionRecord).values(
        file_name=result.file_name or "text-input",
        document_type=result.document_type.value,
        overall_confidence=result.overall_confidence,
        raw_text_length=result.raw_text_length,
        result_json=json.dumps(result.model_dump(mode="json"), default=str),
        warnings=json.dumps(result.warnings),
        processing_time_ms=result.processing_time_ms,
    )
    row = await db.execute(stmt)
    await db.commit()
    return row.lastrowid


# ─── Text endpoint ────────────────────────────────────────────────────────────

@router.post(
    "/extract/text",
    response_model=ExtractionResponse,
    summary="Extract from raw text",
    description=(
        "Pass unstructured document text in the request body. "
        "Optionally hint the document type; if omitted it is auto-detected."
    ),
)
async def extract_from_text(
    body: ExtractionRequest,
    db: AsyncSession = Depends(get_db),
) -> ExtractionResponse:
    try:
        result = await extract_structured(
            text=body.text,
            document_type=body.document_type or DocumentType.UNKNOWN,
            file_name="text-input",
            custom_fields=body.custom_fields,
        )
        result.id = await _persist(result, db)
        return result

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error during text extraction")
        raise HTTPException(
            status_code=500,
            detail=f"Extraction failed: {str(e)[:300]}",
        )


# ─── File endpoint ────────────────────────────────────────────────────────────

@router.post(
    "/extract/file",
    response_model=ExtractionResponse,
    summary="Extract from uploaded file",
    description=(
        "Upload a PDF, DOCX, TXT, PNG, or JPG. "
        "The backend extracts the text layer and runs structured extraction."
    ),
)
async def extract_from_file(
    file: UploadFile = File(..., description="File to extract data from"),
    document_type: Optional[str] = Form(
        None, description="DocumentType hint: RESUME, INVOICE, CONTRACT, etc."
    ),
    db: AsyncSession = Depends(get_db),
) -> ExtractionResponse:

    # ── Validate file ────────────────────────────────────────────────────────
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file was uploaded")

    # Parse document_type form param
    doc_type = DocumentType.UNKNOWN
    if document_type:
        try:
            doc_type = DocumentType(document_type.upper())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid document_type '{document_type}'. "
                       f"Valid values: {[t.value for t in DocumentType]}",
            )

    content = await file.read()

    try:
        text = await process_file(file.filename, content)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        logger.exception(f"File processing failed for '{file.filename}'")
        raise HTTPException(status_code=500, detail=f"File processing failed: {str(e)[:200]}")

    try:
        result = await extract_structured(
            text=text,
            document_type=doc_type,
            file_name=file.filename,
        )
        result.id = await _persist(result, db)
        return result

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception(f"Extraction failed for '{file.filename}'")
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)[:300]}")


# ─── Batch endpoint ───────────────────────────────────────────────────────────

class BatchItem(ExtractionRequest):
    label: Optional[str] = None   # Optional user label for tracking


@router.post(
    "/extract/batch",
    summary="Batch extract from multiple texts",
    description="Process up to 5 documents in parallel. Returns array of ExtractionResponse.",
)
async def extract_batch(
    items: list[BatchItem],
    db: AsyncSession = Depends(get_db),
) -> list[dict]:

    if len(items) == 0:
        raise HTTPException(status_code=400, detail="Batch must contain at least 1 item")
    if len(items) > 5:
        raise HTTPException(
            status_code=400,
            detail=f"Batch limit is 5 items; you sent {len(items)}"
        )

    async def _process_one(item: BatchItem, index: int) -> dict:
        try:
            result = await extract_structured(
                text=item.text,
                document_type=item.document_type or DocumentType.UNKNOWN,
                file_name=item.label or f"batch-item-{index + 1}",
                custom_fields=item.custom_fields,
            )
            results_queue.append((index, item.label, result))
            return {"index": index, "label": item.label, "success": True, "result": result.model_dump(mode="json")}
        except Exception as e:
            logger.warning(f"Batch item {index} failed: {e}")
            return {"index": index, "label": item.label, "success": False, "error": str(e)[:200]}

    results_queue: list[tuple[int, str | None, ExtractionResponse]] = []
    tasks = [_process_one(item, i) for i, item in enumerate(items)]
    rows = await asyncio.gather(*tasks)

    # Persist sequentially — a single SQLAlchemy AsyncSession must not be
    # shared across concurrent coroutines. Map DB ids back by index.
    for _index, _label, result in results_queue:
        row_id = await _persist(result, db)
        payload = rows[_index]
        if payload.get("success") and payload.get("result"):
            payload["result"]["id"] = row_id

    return sorted(rows, key=lambda r: r["index"])
