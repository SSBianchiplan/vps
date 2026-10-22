"""Pipeline LER — OCR estruturado (edge ou VLM) + validação regex + campos.

A inferência roda sobre o frame inteiro (redimensionado) para que os bboxes
fiquem em coordenadas normalizadas do frame completo. A ROI, quando presente,
filtra as leituras (centro dentro da ROI). Texto irregular/manuscrito ou
ausência do OCR edge caem no VLM.
"""
from __future__ import annotations

import asyncio
import re
from time import perf_counter

from ..inference.edge.ocr import edge_ocr
from ..inference.vlm.claude_client import claude_vlm
from ..preprocessing.image_ops import prepare_for_vlm, resize_max_side
from ..schemas.enums import Mode, ModelType, PipelineKind
from ..schemas.results import InferenceResult, Leitura, ReadResult
from ..schemas.tasks import ReadParams, TaskConfig
from ..tracking.line_counter import point_in_polygon
from ..utils.images import open_image, to_jpeg
from .base import FrameContext, Pipeline


def _center_in_roi(bbox: list[float] | None, roi) -> bool:
    if bbox is None or roi is None or not roi.points:
        return True
    x, y, w, h = bbox
    c = (x + w / 2, y + h / 2)
    rect = roi.as_rect()
    if rect is not None:
        rx, ry, rw, rh = rect
        return rx <= c[0] <= rx + rw and ry <= c[1] <= ry + rh
    return point_in_polygon(c, [tuple(p) for p in roi.points])


class ReadPipeline(Pipeline):
    model_name = "ocr"

    def __init__(self, use_edge: bool) -> None:
        self.use_edge = use_edge
        self.kind = PipelineKind.EDGE if use_edge else PipelineKind.VLM
        self.model_type = ModelType.EDGE if use_edge else ModelType.VLM

    async def run(self, ctx: FrameContext, task: TaskConfig) -> InferenceResult:
        params: ReadParams = task.typed_params()  # type: ignore[assignment]
        warnings: list[str] = []
        t0 = perf_counter()

        if self.use_edge:
            img = resize_max_side(open_image(ctx.image_bytes), 1280)
            ocr_bytes = to_jpeg(img, quality=90)
            leituras = await asyncio.to_thread(edge_ocr.recognize, ocr_bytes, params.idioma)
            model_name = f"ocr:{edge_ocr.backend() or 'edge'}"
        else:
            img_bytes = prepare_for_vlm(ctx.image_bytes, roi=None, max_side=1280)
            data = await claude_vlm.read(img_bytes, "image/jpeg", params, task.prompt)
            leituras = [Leitura(**l) for l in data.get("leituras", [])]
            model_name = claude_vlm.model

        # Filtra por ROI (se houver) usando o centro de cada leitura.
        if task.roi and task.roi.points:
            leituras = [l for l in leituras if _center_in_roi(l.bbox, task.roi)]

        # Validação de formato (regex) e marcação de validade.
        if params.pattern_regex:
            try:
                pat = re.compile(params.pattern_regex)
                for l in leituras:
                    l.valido = bool(pat.search(l.texto))
            except re.error:
                warnings.append("regex_invalida")

        latency = int((perf_counter() - t0) * 1000)
        confidence = (sum(l.confianca for l in leituras) / len(leituras)) if leituras else 0.0
        payload = ReadResult(leituras=leituras)
        return self.build_result(
            mode=Mode.LER,
            ctx=ctx,
            task=task,
            payload=payload,
            latency_ms=latency,
            confidence=confidence,
            model_name=model_name,
            warnings=warnings,
        )
