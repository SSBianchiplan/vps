"""Schemas de resultado de inferência (result_json) por modo.

Correspondem à Seção 6.3 da spec.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .enums import Mode, ModelType

BBox = list[float]  # [x, y, w, h] em coordenadas normalizadas [0,1]
Point = tuple[float, float]  # (x, y) normalizado


# ── LER ─────────────────────────────────────────────────────────────
class Leitura(BaseModel):
    texto: str
    campo: str | None = None
    confianca: float = 0.0
    bbox: BBox | None = None
    valido: bool | None = None  # passou na validação regex (se houver)


class ReadResult(BaseModel):
    leituras: list[Leitura] = Field(default_factory=list)


# ── CONTAR ──────────────────────────────────────────────────────────
class Detection(BaseModel):
    classe: str
    confianca: float
    bbox: BBox
    track_id: int | None = None


class CountResult(BaseModel):
    contagens: dict[str, int] = Field(default_factory=dict)
    total: int = 0
    tracks_ativos: int = 0
    cruzamentos_linha: int = 0
    detections: list[Detection] = Field(default_factory=list)  # p/ overlay


# ── DETECTAR ────────────────────────────────────────────────────────
class DetectResult(BaseModel):
    detections: list[Detection] = Field(default_factory=list)
    total: int = 0
    contagens: dict[str, int] = Field(default_factory=dict)  # por classe (resumo)


# ── RASTREAR (object tracking / fluxo) ──────────────────────────────
class Trajectory(BaseModel):
    track_id: int
    object_class: str = "?"
    points: list[Point] = Field(default_factory=list)  # caminho normalizado (downsampled)


class TrackEvent(BaseModel):
    action: str                  # LINE_CROSSED | ZONE_ENTERED | ZONE_EXITED | DWELL_EXCEEDED
    track_id: int
    object_class: str = "?"
    direction: str | None = None  # IN | OUT
    dwell_s: float | None = None


class TrackResult(BaseModel):
    active: int = 0              # tracks ativos neste frame
    unique_total: int = 0       # IDs únicos vistos (contagem sem duplicidade)
    line_in: int = 0
    line_out: int = 0
    crossings: int = 0
    zone_unique: int = 0
    wip: int = 0                 # ocupação atual da zona
    dwell_avg_s: float = 0.0
    dwell_max_s: float = 0.0
    dwell_exceeded: int = 0
    kpis: dict[str, Any] = Field(default_factory=dict)        # CLD_* de fluxo
    contagens: dict[str, int] = Field(default_factory=dict)   # por classe (ativos)
    trajectories: list[Trajectory] = Field(default_factory=list)
    events: list[TrackEvent] = Field(default_factory=list)    # eventos semânticos deste frame
    detections: list[Detection] = Field(default_factory=list)  # overlay (bbox + track_id)


# ── DESCREVER ───────────────────────────────────────────────────────
class DescribeResult(BaseModel):
    descricao: str = ""
    objetos: list[str] = Field(default_factory=list)
    alertas: list[str] = Field(default_factory=list)


# ── ANALISAR ────────────────────────────────────────────────────────
class ItemVerificado(BaseModel):
    criterio: str
    atende: bool
    observacao: str = ""


class AnalyzeResult(BaseModel):
    veredito: str = "NOK"  # rótulo OK/NOK conforme config
    confianca: float = 0.0
    itens_verificados: list[ItemVerificado] = Field(default_factory=list)
    resumo: str = ""


ResultPayload = ReadResult | CountResult | DetectResult | TrackResult | DescribeResult | AnalyzeResult


class InferenceResult(BaseModel):
    """Envelope de um evento de inferência (corresponde a FACT_DETECTION)."""

    detection_id: str
    task_id: str | None = None
    source_id: str | None = None
    mode: Mode
    model_name: str
    model_version: str | None = None   # rastreabilidade/rollback (§5.2)
    model_type: ModelType
    pipeline: str
    timestamp: str            # ISO-8601 UTC
    latency_ms: int
    confidence: float
    frame_seq: int | None = None
    result: dict[str, Any]    # serialização do ResultPayload do modo
    warnings: list[str] = Field(default_factory=list)
