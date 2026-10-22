"""Inferência sob demanda (snapshot único) via REST — útil para testes/curl."""
from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import recording
from ..config import get_settings
from ..db.repository import repository
from ..inference.errors import InferenceError
from ..logging_conf import get_logger
from ..orchestrator.router import Orchestrator
from ..pipelines.base import FrameContext
from ..schemas.results import InferenceResult
from ..schemas.tasks import TaskConfig
from ..utils.images import b64_to_bytes, media_type_of

router = APIRouter(prefix="/infer", tags=["infer"])
log = get_logger("visiondesk.infer")

# Orquestrador stateless para chamadas one-shot (sem estado de contagem entre frames).
_orchestrator = Orchestrator()


class InferRequest(BaseModel):
    image_b64: str
    task: TaskConfig
    source_id: str | None = None


@router.get("/classes")
def classes() -> dict:
    """Classes-alvo disponiveis: catalogo de 150 cruzado com o modelo carregado.

    A interface montava o campo com texto livre, e um nome que o modelo nao
    conhece nunca dispara a regra — sem erro nenhum na tela. Aqui a lista vem
    do proprio detector, entao o que aparece e o que realmente detecta.
    """
    from ..inference.edge.detector import yolo_detector
    from ..inference.edge.target_classes import GRUPOS, catalogo

    nomes: dict[int, str] | None = None
    modelo = None
    if yolo_detector.available():
        try:
            m = yolo_detector._load()          # noqa: SLF001 - leitura do vocabulario
            nomes = m.names
            modelo = Path(get_settings().yolo_weights).stem
        except Exception:  # noqa: BLE001
            nomes = None
    cat = catalogo(nomes)
    return {
        "model": modelo,
        "model_classes": len(nomes) if nomes else 0,
        "grupos": GRUPOS,
        "classes": cat,
        "total": len(cat),
    }


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
    except Exception as exc:  # noqa: BLE001
        # Sem isto o cliente recebia "Internal Server Error" pelado: nem o tipo
        # do erro. Diagnosticar exigia acesso ao servidor — e quem opera não tem.
        log.exception("falha inferindo (modo %s)", req.task.mode)
        raise HTTPException(
            status_code=500,
            detail={"code": "infer_failed", "message": f"{type(exc).__name__}: {exc}"},
        )

    # Gravar é separado de responder: a inferência já deu certo e vai para quem
    # pediu mesmo que o banco recuse. A falha vira aviso no resultado, não um
    # 500 que apaga um trabalho que funcionou.
    try:
        await asyncio.to_thread(repository.save_inference, result, None)
    except Exception:  # noqa: BLE001
        log.exception("falha ao gravar a inferência")
        result.warnings.append("persistencia_falhou")
    try:
        # Gravação automática por detecção (pessoa/cachorro etc.).
        await asyncio.to_thread(recording.maybe_capture, result, data)
    except Exception:  # noqa: BLE001
        log.exception("falha na gravação automática")
        result.warnings.append("gravacao_automatica_falhou")
    return result
