"""Inferência sob demanda (snapshot único) via REST — útil para testes/curl."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import recording
from ..db.repository import repository
from ..inference.errors import InferenceError
from ..orchestrator.router import Orchestrator
from ..pipelines.base import FrameContext
from ..schemas.results import InferenceResult
from ..schemas.tasks import TaskConfig
from ..utils.images import b64_to_bytes, media_type_of

router = APIRouter(prefix="/infer", tags=["infer"])

# Orquestrador stateless para chamadas one-shot (sem estado de contagem entre frames).
_orchestrator = Orchestrator()


class InferRequest(BaseModel):
    image_b64: str
    task: TaskConfig
    source_id: str | None = None


@router.post("", response_model=InferenceResult)
async def infer(req: InferRequest) -> InferenceResult:
    try:
        data = b64_to_bytes(req.image_b64)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"imagem base64 inválida: {exc}")

    ctx = FrameContext(
        image_bytes=data,
        media_type=media_type_of(data),
        frame_seq=0,
        source_id=req.source_id,
        continuous=False,
    )
    try:
        result = await _orchestrator.process(ctx, req.task)
    except InferenceError as exc:
        raise HTTPException(status_code=503, detail={"code": exc.code, "message": exc.message})

    await asyncio.to_thread(repository.save_inference, result, None)
    # Gravação automática por detecção (pessoa/cachorro etc.).
    await asyncio.to_thread(recording.maybe_capture, result, data)
    return result
