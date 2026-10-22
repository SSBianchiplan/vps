"""Schemas de configuração de tarefa (definidos no frontend)."""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from .enums import Mode, ROIShape

# Pontos em coordenadas NORMALIZADAS [0,1] relativas ao frame de inferência,
# para serem independentes de resolução de preview vs. inferência.
Point = tuple[float, float]


class ROI(BaseModel):
    """Região de interesse desenhável sobre o vídeo."""

    shape: ROIShape
    # rect: [x, y, w, h] | line: [[x1,y1],[x2,y2]] | zone: [[x,y], ...]
    points: list[Point] = Field(default_factory=list)

    def as_rect(self) -> tuple[float, float, float, float] | None:
        if self.shape == ROIShape.RECT and len(self.points) >= 2:
            (x, y), (w, h) = self.points[0], self.points[1]
            return (x, y, w, h)
        return None


# ── Parâmetros por modo (painel dinâmico da UI) ─────────────────────


class ReadParams(BaseModel):
    mode: Literal[Mode.LER] = Mode.LER
    idioma: str = "por"
    pattern_regex: str | None = None          # validação do formato esperado
    campos_logicos: list[str] = Field(default_factory=list)  # ex. ["n_op", "codigo_peca"]
    prefer_vlm: bool = False                   # forçar VLM (texto irregular/manuscrito)


class CountParams(BaseModel):
    mode: Literal[Mode.CONTAR] = Mode.CONTAR
    classes_alvo: list[str] = Field(default_factory=list)  # ex. ["person", "box"]
    conf_threshold: float = 0.35
    counting: Literal["instant", "accumulated"] = "instant"
    # Linha/zona de contagem (em coordenadas normalizadas) — opcional.
    counting_roi: ROI | None = None


class TrackParams(BaseModel):
    mode: Literal[Mode.RASTREAR] = Mode.RASTREAR
    classes_alvo: list[str] = Field(default_factory=list)
    conf_threshold: float = 0.35
    algorithm: Literal["bytetrack", "botsort"] = "bytetrack"  # tracking-by-detection
    counting_roi: ROI | None = None      # linha (sentido) ou zona (dwell)
    dwell_sla_s: float | None = None     # alerta DWELL_EXCEEDED (parado além do SLA)
    anonymize_persons: bool = True       # LGPD: não destacar/persistir pessoas


class DetectParams(BaseModel):
    mode: Literal[Mode.DETECTAR] = Mode.DETECTAR
    classes_alvo: list[str] = Field(default_factory=list)  # vazio = todas as classes COCO
    conf_threshold: float = 0.35
    max_det: int = 50
    notificar: bool = False                    # dispara notificação ao detectar
    notificar_classes: list[str] = Field(default_factory=list)  # vazio = qualquer classe


class DescribeParams(BaseModel):
    mode: Literal[Mode.DESCREVER] = Mode.DESCREVER
    foco: str | None = None
    nivel_detalhe: Literal["baixo", "medio", "alto"] = "medio"
    prefer_edge: bool = False                  # forçar motor local (YOLO, sem token)


class AnalyzeParams(BaseModel):
    mode: Literal[Mode.ANALISAR] = Mode.ANALISAR
    criterios: list[str] = Field(default_factory=list)
    rotulo_ok: str = "OK"
    rotulo_nok: str = "NOK"
    rubrica: str | None = None
    acao_nok: Literal["nenhuma", "alerta", "mqtt"] = "nenhuma"
    crop_roi: bool = True                      # recortar ROI por edge antes do VLM
    prefer_edge: bool = False                  # forçar motor local (YOLO, sem token)


ModeParams = Annotated[
    ReadParams | CountParams | DetectParams | TrackParams | DescribeParams | AnalyzeParams,
    Field(discriminator="mode"),
]


class TaskConfig(BaseModel):
    """Configuração declarativa da tarefa (corresponde a DIM_TASK)."""

    task_id: str | None = None
    mode: Mode
    prompt: str | None = None         # instrução livre para o VLM
    params: ModeParams
    roi: ROI | None = None            # ROI principal (crop/inspeção)

    def typed_params(
        self,
    ) -> ReadParams | CountParams | DetectParams | TrackParams | DescribeParams | AnalyzeParams:
        return self.params


class TaskCreateResponse(BaseModel):
    task_id: str
