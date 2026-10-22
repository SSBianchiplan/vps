"""Pipeline DETECTAR — detecção de objetos (YOLO/Ultralytics edge) com bboxes.

Diferente de CONTAR: sem tracking/linha/zona — só localiza objetos no frame
(caixas + classe + confiança) para overlay e gatilho de notificação. Fallback
VLM (Claude retorna bboxes) quando o edge não está disponível.
"""
from __future__ import annotations

import asyncio
from collections import Counter
from time import perf_counter

from ..config import get_settings
from ..inference.edge.detector import YoloDetector
from ..inference.vlm.claude_client import claude_vlm
from ..preprocessing.image_ops import prepare_for_edge, prepare_for_vlm
from ..schemas.enums import Mode, ModelType, PipelineKind
from ..schemas.results import Detection, DetectResult, InferenceResult
from ..schemas.tasks import DetectParams, TaskConfig
from .base import FrameContext, Pipeline


class DetectPipeline(Pipeline):
    model_name = "yolo"

    def __init__(self, use_edge: bool) -> None:
        self.use_edge = use_edge
        self.kind = PipelineKind.EDGE if use_edge else PipelineKind.VLM
        self.model_type = ModelType.EDGE if use_edge else ModelType.VLM
        self._detector = YoloDetector()

    async def run(self, ctx: FrameContext, task: TaskConfig) -> InferenceResult:
        params: DetectParams = task.typed_params()  # type: ignore[assignment]
        if self.use_edge:
            return await self._run_edge(ctx, task, params)
        return await self._run_vlm(ctx, task, params)

    async def _run_edge(self, ctx: FrameContext, task: TaskConfig, params: DetectParams) -> InferenceResult:
        edge_bytes = prepare_for_edge(ctx.image_bytes, roi=None, max_side=640)
        t0 = perf_counter()
        dets = await asyncio.to_thread(
            self._detector.detect, edge_bytes, params.classes_alvo or None, params.conf_threshold, False,
        )
        latency = int((perf_counter() - t0) * 1000)
        dets.sort(key=lambda d: d.confianca, reverse=True)
        dets = dets[: params.max_det]
        conf = sum(d.confianca for d in dets) / len(dets) if dets else 0.0
        payload = DetectResult(
            detections=dets, total=len(dets), contagens=dict(Counter(d.classe for d in dets)),
        )
        return self.build_result(
            mode=Mode.DETECTAR, ctx=ctx, task=task, payload=payload,
            latency_ms=latency, confidence=conf, model_name=get_settings().yolo_weights,
        )

    async def _run_vlm(self, ctx: FrameContext, task: TaskConfig, params: DetectParams) -> InferenceResult:
        # Frame inteiro (roi=None) p/ as bboxes ficarem alinhadas ao overlay.
        img = prepare_for_vlm(ctx.image_bytes, roi=None)
        t0 = perf_counter()
        data = await claude_vlm.detect(img, "image/jpeg", params.classes_alvo, task.prompt)
        latency = int((perf_counter() - t0) * 1000)
        dets: list[Detection] = []
        for o in data.get("objetos", []):
            bbox = o.get("bbox") or []
            c = float(o.get("confianca", 0.0))
            if len(bbox) == 4 and c >= params.conf_threshold:  # respeita o slider de confiança
                dets.append(Detection(classe=o.get("classe", "?"), confianca=c, bbox=bbox))
        dets.sort(key=lambda d: d.confianca, reverse=True)
        dets = dets[: params.max_det]
        conf = sum(d.confianca for d in dets) / len(dets) if dets else 0.0
        payload = DetectResult(
            detections=dets, total=len(dets), contagens=dict(Counter(d.classe for d in dets)),
        )
        return self.build_result(
            mode=Mode.DETECTAR, ctx=ctx, task=task, payload=payload,
            latency_ms=latency, confidence=conf, model_name=claude_vlm.model,
            warnings=["deteccao_vlm_snapshot"],
        )
