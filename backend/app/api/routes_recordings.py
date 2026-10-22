"""Gravações por detecção: listar, servir arquivo, configurar e captura manual."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .. import recording
from ..utils.images import b64_to_bytes

router = APIRouter(prefix="/recordings", tags=["recordings"])


class RecordingConfigIn(BaseModel):
    enabled: bool | None = None
    classes: list[str] | None = None       # ex.: ["person","dog"]
    cooldown_s: float | None = None


class ManualIn(BaseModel):
    source_id: str
    image_b64: str
    classes: dict[str, int] | None = None


@router.get("")
def list_recordings(
    source_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict[str, Any]:
    return {"recordings": recording.list_recordings(source_id, limit)}


@router.get("/config")
def get_config() -> dict[str, Any]:
    return recording.load_config()


@router.put("/config")
def put_config(body: RecordingConfigIn) -> dict[str, Any]:
    return recording.save_config(body.model_dump(exclude_none=True))


@router.post("/manual")
def manual(body: ManualIn) -> dict[str, Any]:
    try:
        data = b64_to_bytes(body.image_b64)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"imagem inválida: {exc}")
    return recording.manual_capture(body.source_id, data, body.classes)


@router.get("/{rec_id}/file")
def get_file(rec_id: str) -> FileResponse:
    p = recording.file_path(rec_id)
    if not p:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "gravação não encontrada"})
    return FileResponse(p, media_type="image/jpeg")
