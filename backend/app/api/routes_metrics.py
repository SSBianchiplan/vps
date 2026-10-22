"""Métricas Prometheus (#8) — /api/metrics (text exposition, sem dep externa)."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from .. import metrics

router = APIRouter(tags=["metrics"])


@router.get("/metrics", response_class=PlainTextResponse)
def prometheus_metrics() -> str:
    return metrics.prometheus()
