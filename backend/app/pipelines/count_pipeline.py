"""Pipeline CONTAR — detecção + tracking + contagem por linha/zona (edge),
com fallback de contagem por snapshot via VLM.

O estado de contagem (LineCounter/ZoneCounter) vive na instância do pipeline,
cacheada por tarefa no orquestrador, de modo a persistir entre frames.
"""
from __future__ import annotations

import asyncio
from collections import Counter
from time import perf_counter

from ..config import get_settings
from ..inference.edge.detector import YoloDetector
from ..inference.vlm.claude_client import claude_vlm
from ..preprocessing.image_ops import prepare_for_edge, prepare_for_vlm
from ..schemas.enums import Mode, ModelType, PipelineKind, ROIShape
from ..schemas.results import CountResult, InferenceResult
from ..schemas.tasks import CountParams, TaskConfig
from ..tracking.line_counter import LineCounter, ZoneCounter, bbox_center
from .base import FrameContext, Pipeline


class CountPipeline(Pipeline):
    model_name = "yolo"

    def __init__(self, use_edge: bool) -> None:
        self.use_edge = use_edge
        self.kind = PipelineKind.EDGE if use_edge else PipelineKind.VLM
        self.model_type = ModelType.EDGE if use_edge else ModelType.VLM
        self._line: LineCounter | None = None
        self._zone: ZoneCounter | None = None
        # Detector próprio por pipeline (cacheado por conexão/tarefa no
        # orquestrador) → estado de tracking ISOLADO entre streams.
        self._detector = YoloDetector()

    async def run(self, ctx: FrameContext, task: TaskConfig) -> InferenceResult:
        params: CountParams = task.typed_params()  # type: ignore[assignment]
        if self.use_edge:
            return await self._run_edge(ctx, task, params)
        return await self._run_vlm(ctx, task, params)

    # ── edge (YOLO + tracking) ──────────────────────────────────
    async def _run_edge(
        self, ctx: FrameContext, task: TaskConfig, params: CountParams
    ) -> InferenceResult:
        edge_bytes = prepare_for_edge(ctx.image_bytes, roi=None, max_side=640)
        t0 = perf_counter()
        detections = await asyncio.to_thread(
            self._detector.detect,
            edge_bytes,
            params.classes_alvo or None,
            params.conf_threshold,
            True,  # track=True → ids estáveis para a contagem por linha/zona
        )
        latency = int((perf_counter() - t0) * 1000)

        centers = {
            d.track_id: bbox_center(d.bbox)
            for d in detections
            if d.track_id is not None
        }

        cruzamentos = 0
        counted = detections  # subconjunto que entra nas contagens
        roi = params.counting_roi
        if roi and roi.shape == ROIShape.LINE and len(roi.points) >= 2:
            if self._line is None:
                self._line = LineCounter(tuple(roi.points[0]), tuple(roi.points[1]))
            self._line.update(centers)
            self._line.forget_absent(set(centers))
            cruzamentos = self._line.total
        elif roi and roi.shape == ROIShape.ZONE and len(roi.points) >= 3:
            if self._zone is None:
                self._zone = ZoneCounter([tuple(p) for p in roi.points])
            self._zone.update(centers)
            inside_ids = self._zone.inside
            # contagens/total/tracks descrevem a MESMA população (dentro da zona)
            counted = [d for d in detections if d.track_id in inside_ids]
            if params.counting == "accumulated":
                cruzamentos = self._zone.unique_entries

        contagens = dict(Counter(d.classe for d in counted))
        total = len(counted)
        tracks_ativos = len({d.track_id for d in counted if d.track_id is not None})
        confidence = (
            sum(d.confianca for d in detections) / len(detections)
            if detections
            else 1.0
        )
        payload = CountResult(
            contagens=contagens,
            total=total,
            tracks_ativos=tracks_ativos,
            cruzamentos_linha=cruzamentos,
            detections=detections,  # overlay mostra todas as detecções
        )
        return self.build_result(
            mode=Mode.CONTAR,
            ctx=ctx,
            task=task,
            payload=payload,
            latency_ms=latency,
            confidence=confidence,
            model_name=get_settings().yolo_weights,
        )

    # ── fallback VLM (contagem por snapshot) ────────────────────
    async def _run_vlm(
        self, ctx: FrameContext, task: TaskConfig, params: CountParams
    ) -> InferenceResult:
        img = prepare_for_vlm(ctx.image_bytes, roi=task.roi)
        t0 = perf_counter()
        data = await claude_vlm.count(img, "image/jpeg", params, task.prompt)
        latency = int((perf_counter() - t0) * 1000)

        contagens = {i["classe"]: int(i["quantidade"]) for i in data.get("itens", [])}
        total = int(data.get("total", sum(contagens.values())))
        payload = CountResult(contagens=contagens, total=total)
        return self.build_result(
            mode=Mode.CONTAR,
            ctx=ctx,
            task=task,
            payload=payload,
            latency_ms=latency,
            confidence=1.0,
            model_name=claude_vlm.model,
            warnings=["contagem_vlm_snapshot_sem_tracking"],
        )
