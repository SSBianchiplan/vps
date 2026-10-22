"""Base dos pipelines de inferência: contexto de frame e helpers comuns."""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone

from pydantic import BaseModel

from ..schemas.enums import Mode, ModelType, PipelineKind
from ..schemas.results import InferenceResult
from ..schemas.tasks import TaskConfig


@dataclass
class FrameContext:
    image_bytes: bytes
    media_type: str
    frame_seq: int = 0
    source_id: str | None = None
    continuous: bool = True  # True = stream contínuo; False = snapshot sob demanda


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_detection_id() -> str:
    return f"det_{uuid.uuid4().hex[:12]}"


class Pipeline(ABC):
    kind: PipelineKind
    model_name: str
    model_type: ModelType

    @abstractmethod
    async def run(self, ctx: FrameContext, task: TaskConfig) -> InferenceResult: ...

    def build_result(
        self,
        *,
        mode: Mode,
        ctx: FrameContext,
        task: TaskConfig,
        payload: BaseModel,
        latency_ms: int,
        confidence: float,
        warnings: list[str] | None = None,
        model_name: str | None = None,
        model_type: ModelType | None = None,
    ) -> InferenceResult:
        from ..inference.versions import version_for

        mname = model_name or self.model_name
        return InferenceResult(
            detection_id=new_detection_id(),
            task_id=task.task_id,
            source_id=ctx.source_id,
            mode=mode,
            model_name=mname,
            model_version=version_for(mname),
            model_type=model_type or self.model_type,
            pipeline=self.kind.value,
            timestamp=_now_iso(),
            latency_ms=latency_ms,
            confidence=round(confidence, 4),
            frame_seq=ctx.frame_seq,
            result=payload.model_dump(mode="json"),
            warnings=warnings or [],
        )
