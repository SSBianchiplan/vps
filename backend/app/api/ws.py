"""WebSocket de streaming: frames entram, resultados saem em tempo real.

Cada conexão tem seu próprio Orchestrator (estado de contagem isolado) e um
coletor de métricas de saúde (FPS, latência). Erros por frame são reportados
sem derrubar a conexão.
"""
from __future__ import annotations

import asyncio
import json
import time
from collections import deque

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import TypeAdapter, ValidationError

from .. import recording
from ..actions import engine as action_engine
from ..notify import dispatch as notify_dispatch
from ..config import get_settings
from ..db.repository import repository
from ..inference.errors import InferenceError
from ..logging_conf import get_logger
from ..orchestrator.router import Orchestrator
from ..pipelines.base import FrameContext
from ..schemas.messages import (
    AlertMessage,
    ClientMessage,
    ControlMessage,
    ErrorMessage,
    FrameMessage,
    HealthMessage,
    ResultMessage,
    StatusMessage,
    dump,
)
from ..schemas.tasks import TaskConfig
from ..utils.images import b64_to_bytes, frame_hash, media_type_of
from .deps import task_from_row

router = APIRouter()
log = get_logger("visiondesk.ws")
_client_adapter: TypeAdapter[ClientMessage] = TypeAdapter(ClientMessage)


class _Metrics:
    def __init__(self) -> None:
        self.lat: deque[int] = deque(maxlen=30)
        self.stamps: deque[float] = deque(maxlen=120)

    def add(self, latency_ms: int) -> None:
        self.lat.append(latency_ms)
        self.stamps.append(time.monotonic())

    def fps(self) -> float:
        now = time.monotonic()
        return float(sum(1 for t in self.stamps if now - t <= 1.0))

    def avg_latency(self) -> float:
        return sum(self.lat) / len(self.lat) if self.lat else 0.0


def _save_frame_if_enabled(data: bytes) -> str | None:
    settings = get_settings()
    if not settings.persist_frames:
        return None
    from ..vps import lgpd
    data = lgpd.anonymize(data)        # LGPD: borra rostos antes de persistir (§15)
    h = frame_hash(data)
    path = settings.frames_path() / f"{h}.jpg"
    if not path.exists():
        path.write_bytes(data)
    return str(path)


@router.websocket("/ws/stream")
async def stream(ws: WebSocket) -> None:
    await ws.accept()
    orch = Orchestrator()
    metrics = _Metrics()
    caps = Orchestrator.capabilities()
    current_task: TaskConfig | None = None
    current_sig: str | None = None
    last_health = 0.0

    await ws.send_json(dump(StatusMessage(state="connected", detail="VisionDesk pronto")))

    async def resolve_task(msg: FrameMessage) -> TaskConfig:
        nonlocal current_task, current_sig
        if msg.task is not None:
            sig = msg.task.model_dump_json()
            if sig != current_sig:
                # Persiste a config e fixa o task_id retornado (fora do event loop).
                task = msg.task
                task_id = await asyncio.to_thread(repository.upsert_task, task)
                task = task.model_copy(update={"task_id": task_id})
                current_task, current_sig = task, sig
            assert current_task is not None
            return current_task
        if msg.task_id:
            if current_task is not None and current_task.task_id == msg.task_id:
                return current_task
            row = await asyncio.to_thread(repository.get_task, msg.task_id)
            if not row:
                raise InferenceError(f"task_id desconhecido: {msg.task_id}", code="task_not_found")
            current_task = task_from_row(row)
            current_sig = current_task.model_dump_json()
            return current_task
        raise InferenceError("frame sem task nem task_id", code="missing_task")

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = _client_adapter.validate_python(json.loads(raw))
            except (ValidationError, json.JSONDecodeError) as exc:
                await ws.send_json(dump(ErrorMessage(code="bad_message", message=str(exc))))
                continue

            if isinstance(msg, ControlMessage):
                if msg.action == "ping":
                    await ws.send_json(dump(StatusMessage(state="connected", detail="pong")))
                elif msg.action == "start":
                    await ws.send_json(dump(StatusMessage(state="running")))
                elif msg.action == "stop":
                    await ws.send_json(dump(StatusMessage(state="stopped")))
                continue

            assert isinstance(msg, FrameMessage)
            try:
                task = await resolve_task(msg)
                data = b64_to_bytes(msg.image_b64)
                ctx = FrameContext(
                    image_bytes=data,
                    media_type=media_type_of(data),
                    frame_seq=msg.frame_seq,
                    source_id=msg.source_id,
                    continuous=True,
                )
                result = await orch.process(ctx, task)
                frame_ref = _save_frame_if_enabled(data)
                # Persistência fora do event loop (sqlite síncrono).
                await asyncio.to_thread(repository.save_inference, result, frame_ref)
                # Gravação automática por detecção (pessoa/cachorro etc.).
                await asyncio.to_thread(recording.maybe_capture, result, data)
                metrics.add(result.latency_ms)
                await ws.send_json(dump(ResultMessage(result=result)))

                # AGIR (M5) + NOTIFICAR: regras + notificação de detecção; alertas → cliente.
                try:
                    alerts = await action_engine.run_rules(task.task_id, result)
                    alerts += await notify_dispatch.notify_detection(task, result)
                    for al in alerts:
                        await ws.send_json(dump(AlertMessage(
                            action_type=al["action_type"], message=al["message"],
                            rule=al["rule"], payload=al.get("payload"),
                        )))
                except Exception:  # noqa: BLE001
                    log.exception("erro no action engine / notificação")

                now = time.monotonic()
                if now - last_health > 1.0:
                    last_health = now
                    await ws.send_json(
                        dump(
                            HealthMessage(
                                fps=metrics.fps(),
                                avg_latency_ms=round(metrics.avg_latency(), 1),
                                last_latency_ms=result.latency_ms,
                                model_active=result.model_name,
                                pipeline=result.pipeline,
                                edge_available=caps["edge_detector"] or caps["edge_ocr"],
                                vlm_available=caps["vlm"],
                            )
                        )
                    )
            except InferenceError as exc:
                await ws.send_json(
                    dump(ErrorMessage(code=exc.code, message=exc.message, frame_seq=msg.frame_seq))
                )
            except Exception as exc:  # noqa: BLE001
                log.exception("erro processando frame")
                await ws.send_json(
                    dump(ErrorMessage(code="internal", message=str(exc), frame_seq=msg.frame_seq))
                )
    except WebSocketDisconnect:
        log.info("cliente desconectou")
