"""Exportação de eventos de inferência (CSV/JSON)."""
from __future__ import annotations

import csv
import io
import json

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, PlainTextResponse

from ..db.repository import repository

router = APIRouter(prefix="/export", tags=["export"])


@router.get("")
def export(
    task_id: str | None = Query(default=None),
    format: str = Query(default="json", pattern="^(json|csv)$"),
    limit: int = Query(default=1000, le=10000),
):
    rows = repository.query_detections(task_id=task_id, limit=limit)

    if format == "json":
        return JSONResponse(content=rows)

    # CSV — achata result_json em uma coluna textual.
    buf = io.StringIO()
    fields = [
        "detection_id", "timestamp", "task_id", "source_id", "model_id",
        "pipeline", "latency_ms", "confidence", "frame_ref", "result_json",
    ]
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        if isinstance(r.get("result_json"), (dict, list)):
            r["result_json"] = json.dumps(r["result_json"], ensure_ascii=False)
        writer.writerow(r)
    return PlainTextResponse(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=visiondesk_export.csv"},
    )
