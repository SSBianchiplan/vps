"""Detector edge (YOLO/RT-DETR via Ultralytics) com import preguiçoso.

Em Apple Silicon priorize CoreML/Neural Engine em produção; MPS para protótipo.
Se Ultralytics/numpy não estiverem instalados, `available()` retorna False e o
orquestrador cai no caminho VLM automaticamente.
"""
from __future__ import annotations

import io
from functools import lru_cache
from typing import Any

from ...config import get_settings
from ...schemas.results import Detection
from ..errors import EdgeUnavailableError


@lru_cache(maxsize=1)
def _deps() -> tuple[Any, Any] | None:
    """Retorna (YOLO, numpy) se disponíveis, senão None (cacheado)."""
    try:
        import numpy as np
        from ultralytics import YOLO
        return YOLO, np
    except Exception:
        return None


class YoloDetector:
    def __init__(self) -> None:
        self._model: Any | None = None
        self._track_model: Any | None = None

    def available(self) -> bool:
        return _deps() is not None

    def _load(self, track: bool = False) -> Any:
        deps = _deps()
        if deps is None:
            raise EdgeUnavailableError(
                "Caminho edge indisponível (instale requirements-edge.txt)."
            )
        YOLO, _ = deps
        settings = get_settings()
        if track:
            if self._track_model is None:
                self._track_model = YOLO(settings.yolo_weights)
            return self._track_model
        if self._model is None:
            self._model = YOLO(settings.yolo_weights)
        return self._model

    def _to_np(self, image_bytes: bytes):
        deps = _deps()
        assert deps is not None
        _, np = deps
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        return np.asarray(img), img.size  # (array RGB, (w, h))

    def detect(
        self,
        image_bytes: bytes,
        classes: list[str] | None = None,
        conf: float | None = None,
        track: bool = False,
    ) -> list[Detection]:
        """Detecta objetos e devolve bboxes normalizadas [x,y,w,h]."""
        model = self._load(track=track)
        settings = get_settings()
        arr, (w, h) = self._to_np(image_bytes)
        conf = conf if conf is not None else settings.yolo_conf

        names: dict[int, str] = model.names  # type: ignore[assignment]
        wanted = set(classes or [])

        if track:
            results = model.track(
                arr, persist=True, conf=conf, verbose=False,
                device=settings.edge_device, tracker="bytetrack.yaml",
            )
        else:
            results = model.predict(
                arr, conf=conf, verbose=False, device=settings.edge_device
            )

        out: list[Detection] = []
        r = results[0]
        boxes = getattr(r, "boxes", None)
        if boxes is None:
            return out
        for box in boxes:
            cls_idx = int(box.cls[0])
            classe = names.get(cls_idx, str(cls_idx))
            if wanted and classe not in wanted:
                continue
            x1, y1, x2, y2 = (float(v) for v in box.xyxy[0])
            track_id = int(box.id[0]) if getattr(box, "id", None) is not None else None
            out.append(
                Detection(
                    classe=classe,
                    confianca=float(box.conf[0]),
                    bbox=[x1 / w, y1 / h, (x2 - x1) / w, (y2 - y1) / h],
                    track_id=track_id,
                )
            )
        return out

    def embed(self, image_bytes: bytes):
        """Vetor de features (embedding) do frame — base p/ anomalia não supervisionada."""
        model = self._load(track=False)
        settings = get_settings()
        arr, _ = self._to_np(image_bytes)
        out = model.embed(arr, verbose=False, device=settings.edge_device)
        v = out[0]
        return v.detach().cpu().numpy().astype("float32")


yolo_detector = YoloDetector()
