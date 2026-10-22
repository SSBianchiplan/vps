"""Pipeline RASTREAR — tracking temporal (VPS_Rastreamento_Objetos).

Detecção por frame (YOLO track=ByteTrack) → FlowTracker (identidade no tempo,
linha c/ sentido, zona/dwell, KPIs de fluxo) → eventos semânticos (LINE_CROSSED,
ZONE_ENTERED/EXITED, DWELL_EXCEEDED) na trilha (Event Store). Estado vive na
instância do pipeline (cacheada por tarefa/stream no orquestrador).
"""
from __future__ import annotations

import asyncio
import time
from collections import Counter
from time import perf_counter

from ..config import get_settings
from ..inference.edge.detector import YoloDetector
from ..preprocessing.image_ops import prepare_for_edge
from ..schemas.enums import Mode, ModelType, PipelineKind, ROIShape
from ..schemas.results import InferenceResult, TrackResult
from ..schemas.tasks import TaskConfig, TrackParams
from ..tracking.line_counter import bbox_center
from ..tracking.tracker import FlowTracker
from .base import FrameContext, Pipeline

_SEV = {"DWELL_EXCEEDED": "alerta", "LINE_CROSSED": "info", "ZONE_ENTERED": "info", "ZONE_EXITED": "info"}


class TrackPipeline(Pipeline):
    model_name = "tracker-bytetrack"

    def __init__(self, use_edge: bool) -> None:
        self.use_edge = use_edge
        self.kind = PipelineKind.EDGE if use_edge else PipelineKind.VLM
        self.model_type = ModelType.EDGE
        self._detector = YoloDetector()
        self._flow = FlowTracker()

    async def run(self, ctx: FrameContext, task: TaskConfig) -> InferenceResult:
        params: TrackParams = task.typed_params()  # type: ignore[assignment]
        edge_bytes = prepare_for_edge(ctx.image_bytes, roi=None, max_side=640)
        t0 = perf_counter()
        detections = await asyncio.to_thread(
            self._detector.detect, edge_bytes, params.classes_alvo or None, params.conf_threshold, True,
        )
        latency = int((perf_counter() - t0) * 1000)

        centers = {
            d.track_id: (d.classe, *bbox_center(d.bbox))
            for d in detections if d.track_id is not None
        }

        line = zone = None
        roi = params.counting_roi
        if roi and roi.shape == ROIShape.LINE and len(roi.points) >= 2:
            line = (tuple(roi.points[0]), tuple(roi.points[1]))
        elif roi and roi.shape == ROIShape.ZONE and len(roi.points) >= 3:
            zone = [tuple(p) for p in roi.points]

        summary, events = self._flow.update(
            centers, time.monotonic(), line=line, zone=zone, dwell_sla_s=params.dwell_sla_s,
        )

        # LGPD: não exibir/persistir bbox de pessoas (anonimização) — fluxo segue contado.
        overlay = detections
        if params.anonymize_persons:
            overlay = [d for d in detections if d.classe.lower() not in ("person", "pessoa")]

        self._emit(ctx, events)

        confidence = sum(d.confianca for d in detections) / len(detections) if detections else 1.0
        payload = TrackResult(
            active=summary["active"], unique_total=summary["unique_total"],
            line_in=summary["line_in"], line_out=summary["line_out"], crossings=summary["crossings"],
            zone_unique=summary["zone_unique"], wip=summary["wip"],
            dwell_avg_s=summary["dwell_avg_s"], dwell_max_s=summary["dwell_max_s"],
            dwell_exceeded=summary["dwell_exceeded"], kpis=summary["kpis"],
            contagens=dict(Counter(d.classe for d in detections)),
            trajectories=summary["trajectories"], events=events, detections=overlay,
        )
        return self.build_result(
            mode=Mode.RASTREAR, ctx=ctx, task=task, payload=payload,
            latency_ms=latency, confidence=confidence, model_name=self.model_name,
            warnings=[] if self.use_edge else ["rastreamento_requer_edge_yolo"],
        )

    def _emit(self, ctx: FrameContext, events: list[dict]) -> None:
        """Eventos semânticos de track → trilha (Event Store) — baixo volume, durável.

        Vínculo track↔Tag-ID (Fio Dourado do movimento): se a fonte tem um Fio
        aberto (bridge bindings), os eventos de track carregam o tag_id → o
        objeto em movimento entra na linhagem.
        """
        if not events:
            return
        try:
            from .. import audit
            from ..vps import bridge
            tag_id = bridge.bindings().get(ctx.source_id or "")  # Tag-ID vinculado à fonte (se houver)
            for e in events:
                act = e["action"]
                if act == "ZONE_EXITED":   # sumário durável (cycle time) → silver/lakehouse
                    self._persist_summary(ctx, e, tag_id)
                extra = f" {e.get('direction') or ''}".rstrip()
                dwell = f" · dwell {e['dwell_s']}s" if e.get("dwell_s") is not None else ""
                fio = f" · Fio {tag_id.split(':')[3]}" if tag_id and len(tag_id.split(':')) > 3 else ""
                audit.record(
                    "INFERENCE", act, severity=_SEV.get(act, "info"), actor="visão",
                    source_id=ctx.source_id, entity_type="track", entity_id=str(e["track_id"]),
                    correlation_id=tag_id or None,   # liga ao Fio Dourado quando vinculado
                    summary=f"{e.get('object_class', '?')} T-{e['track_id']}: {act}{extra}{dwell}{fio}",
                    payload={**e, "tag_id": tag_id},
                )
        except Exception:  # noqa: BLE001 — telemetria nunca quebra a inferência
            pass

    @staticmethod
    def _persist_summary(ctx: FrameContext, e: dict, tag_id: str | None) -> None:
        """Grava 1 sumário por dwell concluído (downsampled, não por frame)."""
        try:
            from datetime import datetime, timezone
            from ..db.database import get_connection
            now = datetime.now(timezone.utc).isoformat()
            get_connection().execute(
                "INSERT INTO vps_track_summary(source_id,track_id,object_class,tag_id,dwell_s,event_ts,created_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (ctx.source_id, e.get("track_id"), e.get("object_class"), tag_id, e.get("dwell_s"), now, now))
        except Exception:  # noqa: BLE001
            pass
