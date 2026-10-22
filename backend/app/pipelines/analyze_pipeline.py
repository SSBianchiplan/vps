"""Pipeline ANALISAR — inspeção OK/NOK estruturada.

Caminho VLM (Claude + adaptive thinking, julgamento rico) quando há token; com
ROI+crop_roi recorta a região antes de enviar (foco + economia de tokens). O
veredito canônico OK/NOK é mapeado para os rótulos do operador.

Caminho edge (YOLO + regras determinísticas sobre as detecções) roda sem token,
automaticamente quando o VLM está indisponível ou quando prefer_edge=True.
"""
from __future__ import annotations

import asyncio
from time import perf_counter

from ..config import get_settings
from ..inference.edge.analyze import edge_analyze
from ..inference.edge.detector import YoloDetector
from ..inference.vlm.claude_client import claude_vlm
from ..preprocessing.image_ops import prepare_for_edge, prepare_for_vlm
from ..schemas.enums import Mode, ModelType, PipelineKind
from ..schemas.results import AnalyzeResult, InferenceResult, ItemVerificado
from ..schemas.tasks import AnalyzeParams, TaskConfig
from .base import FrameContext, Pipeline


class AnalyzePipeline(Pipeline):
    model_name = "claude"

    def __init__(self, use_edge: bool = False) -> None:
        self.use_edge = use_edge
        self.kind = PipelineKind.EDGE if use_edge else PipelineKind.VLM
        self.model_type = ModelType.EDGE if use_edge else ModelType.VLM
        self._detector = YoloDetector()

    async def run(self, ctx: FrameContext, task: TaskConfig) -> InferenceResult:
        params: AnalyzeParams = task.typed_params()  # type: ignore[assignment]
        if self.use_edge:
            return await self._run_edge(ctx, task, params)
        return await self._run_vlm(ctx, task, params)

    async def _run_edge(self, ctx: FrameContext, task: TaskConfig, params: AnalyzeParams) -> InferenceResult:
        roi = task.roi if params.crop_roi else None
        edge_bytes = prepare_for_edge(ctx.image_bytes, roi=roi, max_side=640)
        t0 = perf_counter()
        dets = await asyncio.to_thread(self._detector.detect, edge_bytes, None, None, False)
        latency = int((perf_counter() - t0) * 1000)
        payload, warnings = edge_analyze(dets, params.criterios, params.rotulo_ok, params.rotulo_nok)
        return self.build_result(
            mode=Mode.ANALISAR, ctx=ctx, task=task, payload=payload,
            latency_ms=latency, confidence=payload.confianca,
            model_name=get_settings().yolo_weights, model_type=ModelType.EDGE,
            warnings=["analise_edge_sem_vlm", *warnings],
        )

    async def _run_vlm(self, ctx: FrameContext, task: TaskConfig, params: AnalyzeParams) -> InferenceResult:
        roi = task.roi if params.crop_roi else None
        is_hybrid = roi is not None and bool(roi.points)
        img = prepare_for_vlm(ctx.image_bytes, roi=roi)

        t0 = perf_counter()
        data = await claude_vlm.analyze(img, "image/jpeg", params, task.prompt)
        latency = int((perf_counter() - t0) * 1000)

        canon = str(data.get("veredito", "NOK")).upper()
        veredito = params.rotulo_ok if canon == "OK" else params.rotulo_nok
        itens = [ItemVerificado(**i) for i in data.get("itens_verificados", [])]
        payload = AnalyzeResult(
            veredito=veredito,
            confianca=float(data.get("confianca", 0.0)),
            itens_verificados=itens,
            resumo=str(data.get("resumo", "")),
        )
        return self.build_result(
            mode=Mode.ANALISAR, ctx=ctx, task=task, payload=payload,
            latency_ms=latency, confidence=payload.confianca,
            model_name=claude_vlm.model, model_type=ModelType.VLM,
            warnings=(["crop_hibrido_roi"] if is_hybrid else []),
        )
