"""History & export endpoints."""
import json
import csv
import io
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete

from app.database import get_db, ExtractionRecord
from app.models.schemas import HistoryItem

router = APIRouter()


@router.get("/history", response_model=list[HistoryItem], summary="List extraction history")
async def list_history(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    document_type: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(ExtractionRecord).order_by(ExtractionRecord.created_at.desc())
    if document_type:
        stmt = stmt.where(ExtractionRecord.document_type == document_type.upper())
    stmt = stmt.limit(limit).offset(offset)
    rows = await db.execute(stmt)
    records = rows.scalars().all()

    return [
        HistoryItem(
            id=r.id,
            file_name=r.file_name,
            document_type=r.document_type,
            overall_confidence=r.overall_confidence,
            raw_text_length=r.raw_text_length,
            processing_time_ms=r.processing_time_ms,
            created_at=r.created_at.isoformat(),
            warnings_count=len(json.loads(r.warnings or "[]")),
        )
        for r in records
    ]


@router.get("/history/{record_id}", summary="Get full extraction result by ID")
async def get_history_item(record_id: int, db: AsyncSession = Depends(get_db)):
    row = await db.get(ExtractionRecord, record_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Record {record_id} not found")
    return json.loads(row.result_json)


@router.delete("/history/{record_id}", summary="Delete a history record")
async def delete_history_item(record_id: int, db: AsyncSession = Depends(get_db)):
    row = await db.get(ExtractionRecord, record_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Record {record_id} not found")
    await db.delete(row)
    await db.commit()
    return {"deleted": record_id}


@router.delete("/history", summary="Clear all history")
async def clear_history(db: AsyncSession = Depends(get_db)):
    result = await db.execute(delete(ExtractionRecord))
    await db.commit()
    return {"deleted_count": result.rowcount}


@router.get("/history/{record_id}/export", summary="Export extraction as JSON or CSV")
async def export_history_item(
    record_id: int,
    format: str = Query("json", pattern="^(json|csv)$"),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(ExtractionRecord, record_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Record {record_id} not found")

    data = json.loads(row.result_json)
    safe_name = row.file_name.replace(" ", "_").split(".")[0]

    if format == "json":
        content = json.dumps(data, indent=2, default=str)
        return StreamingResponse(
            io.StringIO(content),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{safe_name}_extraction.json"'},
        )

    # CSV — flatten the extracted data dict
    flat = data.get("data", {})
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["field", "value"])
    for k, v in flat.items():
        writer.writerow([k, json.dumps(v) if isinstance(v, (dict, list)) else v])
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}_extraction.csv"'},
    )


@router.get("/stats", summary="Extraction statistics")
async def get_stats(db: AsyncSession = Depends(get_db)):
    total = await db.scalar(select(func.count()).select_from(ExtractionRecord))
    avg_conf = await db.scalar(select(func.avg(ExtractionRecord.overall_confidence)))
    avg_ms = await db.scalar(select(func.avg(ExtractionRecord.processing_time_ms)))

    # Count by document type
    type_counts_rows = await db.execute(
        select(ExtractionRecord.document_type, func.count().label("cnt"))
        .group_by(ExtractionRecord.document_type)
    )
    by_type = {r.document_type: r.cnt for r in type_counts_rows}

    return {
        "total_extractions": total or 0,
        "avg_confidence": round(avg_conf or 0, 3),
        "avg_processing_ms": round(avg_ms or 0, 1),
        "by_document_type": by_type,
    }
