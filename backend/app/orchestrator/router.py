"""Orquestrador: escolhe o pipeline (edge/vlm/híbrido) por modo + capacidades.

Implementa a lógica de roteamento da Seção 2.1 da spec. A função `route` é pura
(recebe apenas flags de disponibilidade) e portanto testável sem dependências.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from ..inference.edge.detector import yolo_detector
from ..inference.edge.ocr import edge_ocr
from ..inference.vlm.claude_client import claude_vlm
from ..pipelines.analyze_pipeline import AnalyzePipeline
from ..pipelines.base import FrameContext, Pipeline
from ..pipelines.count_pipeline import CountPipeline
from ..pipelines.detect_pipeline import DetectPipeline
from ..pipelines.track_pipeline import TrackPipeline
from ..pipelines.describe_pipeline import DescribePipeline
from ..pipelines.read_pipeline import ReadPipeline
from ..schemas.enums import Mode, PipelineKind
from ..schemas.results import InferenceResult
from ..schemas.tasks import (
    AnalyzeParams,
    CountParams,
    DescribeParams,
    ReadParams,
    TaskConfig,
)


@dataclass(frozen=True)
class RouteDecision:
    mode: Mode
    use_edge: bool
    kind: PipelineKind


def route(
    task: TaskConfig,
    *,
    edge_detect: bool,
    edge_ocr_avail: bool,
    vlm: bool,
    continuous: bool = True,
) -> RouteDecision:
    """Decide o caminho de inferência preferindo backends disponíveis."""
    mode = task.mode

    if mode in (Mode.DESCREVER, Mode.ANALISAR):
        params = task.typed_params()
        prefer_edge = bool(getattr(params, "prefer_edge", False))
        # DESCREVER/ANALISAR têm caminho edge (YOLO) que roda sem token.
        # Preferimos VLM (mais rico) quando disponível e não forçado o local.
        if prefer_edge and edge_detect:
            use_edge = True
        elif vlm:
            use_edge = False
        elif edge_detect:           # sem token → cai no edge automaticamente
            use_edge = True
        else:
            use_edge = False        # nada disponível; pipeline emitirá erro claro
        return RouteDecision(mode, use_edge, PipelineKind.EDGE if use_edge else PipelineKind.VLM)

    if mode == Mode.LER:
        params: ReadParams = task.typed_params()  # type: ignore[assignment]
        prefer_vlm = params.prefer_vlm
        if not prefer_vlm and edge_ocr_avail:
            use_edge = True
        elif vlm:
            use_edge = False
        elif edge_ocr_avail:  # prefer_vlm mas VLM indisponível → cai no edge
            use_edge = True
        else:
            use_edge = False  # nada disponível; pipeline VLM emitirá erro claro
        return RouteDecision(mode, use_edge, PipelineKind.EDGE if use_edge else PipelineKind.VLM)

    if mode in (Mode.CONTAR, Mode.DETECTAR):
        if edge_detect:
            use_edge = True
        elif vlm:
            use_edge = False
        else:
            use_edge = True  # nada disponível; pipeline edge emitirá erro claro
        return RouteDecision(mode, use_edge, PipelineKind.EDGE if use_edge else PipelineKind.VLM)

    if mode == Mode.RASTREAR:
        # Rastreamento é temporal → exige detector edge (YOLO+ByteTrack); sem VLM.
        return RouteDecision(mode, True, PipelineKind.EDGE)

    raise ValueError(f"Modo não suportado: {mode}")


class Orchestrator:
    """Processa frames e mantém estado de pipeline por tarefa (por conexão WS)."""

    def __init__(self) -> None:
        self._cache: dict[str, Pipeline] = {}

    # ── capacidades ─────────────────────────────────────────────
    @staticmethod
    def capabilities() -> dict[str, bool]:
        return {
            "edge_detector": yolo_detector.available(),
            "edge_ocr": edge_ocr.available(),
            "vlm": claude_vlm.available(),
        }

    # ── seleção/cache de pipeline ───────────────────────────────
    @staticmethod
    def _key(task: TaskConfig, decision: RouteDecision) -> str:
        base = task.task_id or "adhoc"
        params_sig = json.dumps(task.params.model_dump(mode="json"), sort_keys=True)
        roi_sig = (
            json.dumps(task.roi.model_dump(mode="json"), sort_keys=True)
            if task.roi
            else ""
        )
        return f"{base}|{task.mode.value}|edge={decision.use_edge}|{hash(params_sig + roi_sig)}"

    def _build(self, task: TaskConfig, decision: RouteDecision) -> Pipeline:
        if task.mode == Mode.DESCREVER:
            return DescribePipeline(use_edge=decision.use_edge)
        if task.mode == Mode.ANALISAR:
            return AnalyzePipeline(use_edge=decision.use_edge)
        if task.mode == Mode.LER:
            return ReadPipeline(use_edge=decision.use_edge)
        if task.mode == Mode.CONTAR:
            return CountPipeline(use_edge=decision.use_edge)
        if task.mode == Mode.DETECTAR:
            return DetectPipeline(use_edge=decision.use_edge)
        if task.mode == Mode.RASTREAR:
            return TrackPipeline(use_edge=decision.use_edge)
        raise ValueError(f"Modo não suportado: {task.mode}")

    def _get_pipeline(self, task: TaskConfig, decision: RouteDecision) -> Pipeline:
        key = self._key(task, decision)
        pipe = self._cache.get(key)
        if pipe is None:
            pipe = self._build(task, decision)
            self._cache[key] = pipe
        return pipe

    def decide(self, task: TaskConfig, continuous: bool = True) -> RouteDecision:
        caps = self.capabilities()
        return route(
            task,
            edge_detect=caps["edge_detector"],
            edge_ocr_avail=caps["edge_ocr"],
            vlm=caps["vlm"],
            continuous=continuous,
        )

    async def process(self, ctx: FrameContext, task: TaskConfig) -> InferenceResult:
        decision = self.decide(task, continuous=ctx.continuous)
        pipeline = self._get_pipeline(task, decision)
        return await pipeline.run(ctx, task)
