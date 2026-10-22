"""Protocolo WebSocket entre frontend e backend.

Envelope discriminado por `type`. O cliente envia frames + a config de tarefa;
o servidor roteia, infere, persiste e devolve o resultado (overlay + painel).
"""
from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from .results import InferenceResult
from .tasks import TaskConfig


# ── Cliente → Servidor ──────────────────────────────────────────────
class FrameMessage(BaseModel):
    type: Literal["frame"] = "frame"
    # JPEG/PNG em base64 (sem prefixo data: URI).
    image_b64: str
    frame_seq: int = 0
    source_id: str | None = None
    # A config pode vir embutida (modo declarativo) ou referenciada por task_id.
    task: TaskConfig | None = None
    task_id: str | None = None


class ControlMessage(BaseModel):
    type: Literal["control"] = "control"
    # O snapshot é enviado como uma mensagem 'frame' comum (não há ação dedicada).
    action: Literal["start", "stop", "ping"]


ClientMessage = Annotated[
    FrameMessage | ControlMessage,
    Field(discriminator="type"),
]


# ── Servidor → Cliente ──────────────────────────────────────────────
class ResultMessage(BaseModel):
    type: Literal["result"] = "result"
    result: InferenceResult


class ErrorMessage(BaseModel):
    type: Literal["error"] = "error"
    code: str
    message: str
    frame_seq: int | None = None


class HealthMessage(BaseModel):
    type: Literal["health"] = "health"
    fps: float = 0.0
    avg_latency_ms: float = 0.0
    last_latency_ms: int = 0
    model_active: str = ""
    pipeline: str = ""
    edge_available: bool = False
    vlm_available: bool = False


class StatusMessage(BaseModel):
    type: Literal["status"] = "status"
    state: Literal["connected", "running", "stopped"]
    detail: str = ""


class AlertMessage(BaseModel):
    """Alerta do Action Engine (M5/AGIR) — overlay/clipboard no frontend."""
    type: Literal["alert"] = "alert"
    action_type: str                 # alert_visual | clipboard
    message: str = ""
    rule: str = ""
    payload: Any = None


ServerMessage = ResultMessage | ErrorMessage | HealthMessage | StatusMessage | AlertMessage


def dump(msg: BaseModel) -> dict[str, Any]:
    """Serializa para JSON-compatível (modo='json' resolve enums/datas)."""
    return msg.model_dump(mode="json")
