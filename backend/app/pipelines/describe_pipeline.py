"""Pipeline DESCREVER — descrição de cena.

Caminho VLM (Claude, rico) quando há token; caminho edge (YOLO → descrição
PT-BR sintetizada) quando o VLM está indisponível ou o operador força o motor
local (prefer_edge). Snapshot sob demanda.
"""
from __future__ import annotations

import asyncio
from time import perf_counter

from ..config import get_settings
from ..inference.edge.describe import edge_describe
from ..inference.edge.detector import YoloDetector
from ..inference.vlm.claude_client import claude_vlm
from ..preprocessing.image_ops import prepare_for_edge, prepare_for_vlm
from ..schemas.enums import Mode, ModelType, PipelineKind
from ..schemas.results import DescribeResult, InferenceResult
from ..schemas.tasks import DescribeParams, TaskConfig
from .base import FrameContext, Pipeline


class DescribePipeline(Pipeline):
    model_name = "claude"

    def __init__(self, use_edge: bool = False) -> None:
        self.use_edge = use_edge
        self.kind = PipelineKind.EDGE if use_edge else PipelineKind.VLM
        self.model_type = ModelType.EDGE if use_edge else ModelType.VLM
        self._detector = YoloDetector()

    async def run(self, ctx: FrameContext, task: TaskConfig) -> InferenceResult:
        params: DescribeParams = task.typed_params()  # type: ignore[assignment]
        if self.use_edge:
            return await self._run_edge(ctx, task, params)
        return await self._run_vlm(ctx, task, params)

    async def _run_edge(self, ctx: FrameContext, task: TaskConfig, params: DescribeParams) -> InferenceResult:
        edge_bytes = prepare_for_edge(ctx.image_bytes, roi=task.roi, max_side=640)
        t0 = perf_counter()
        dets = await asyncio.to_thread(self._detector.detect, edge_bytes, None, None, False)
        latency = int((perf_counter() - t0) * 1000)
        payload = edge_describe(dets, params.nivel_detalhe)
        conf = (sum(d.confianca for d in dets) / len(dets)) if dets else 0.0
        return self.build_result(
            mode=Mode.DESCREVER, ctx=ctx, task=task, payload=payload,
            latency_ms=latency, confidence=conf, model_name=get_settings().yolo_weights,
            model_type=ModelType.EDGE, warnings=["descricao_edge_sem_vlm"],
        )

    async def _run_vlm(self, ctx: FrameContext, task: TaskConfig, params: DescribeParams) -> InferenceResult:
        img = prepare_for_vlm(ctx.image_bytes, roi=task.roi)
        t0 = perf_counter()
        data = await claude_vlm.describe(img, "image/jpeg", params, task.prompt)
        latency = int((perf_counter() - t0) * 1000)
        payload = DescribeResult(**data)
        return self.build_result(
            mode=Mode.DESCREVER, ctx=ctx, task=task, payload=payload,
            latency_ms=latency, confidence=1.0, model_name=claude_vlm.model,
            model_type=ModelType.VLM,
        )
