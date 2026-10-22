"""Métricas in-process (exposição Prometheus, sem dependência externa) — #8.

Atualizadas a cada inferência persistida; servidas em /api/metrics e consumíveis
por Prometheus/Grafana (KPIs: CLD_Inference_Latency_ms, throughput, edge/vlm).
"""
from __future__ import annotations

from collections import defaultdict

_total = 0
_by_pipeline: dict[str, int] = defaultdict(int)
_lat_sum = 0.0
_lat_count = 0
_last_latency = 0.0


def record(pipeline: str, latency_ms: int) -> None:
    global _total, _lat_sum, _lat_count, _last_latency
    _total += 1
    _by_pipeline[pipeline] += 1
    _lat_sum += latency_ms
    _lat_count += 1
    _last_latency = float(latency_ms)


def prometheus() -> str:
    from .orchestrator.router import Orchestrator
    from .workers import manager

    caps = Orchestrator.capabilities()
    running = sum(1 for w in manager.status() if w.get("running"))
    avg = (_lat_sum / _lat_count) if _lat_count else 0.0
    lines = [
        "# HELP visiondesk_up 1 se o serviço está ativo",
        "visiondesk_up 1",
        "# HELP visiondesk_inferences_total total de inferências",
        f"visiondesk_inferences_total {_total}",
        "# HELP visiondesk_inference_latency_ms_avg latência média (CLD_Inference_Latency_ms)",
        f"visiondesk_inference_latency_ms_avg {avg:.1f}",
        f"visiondesk_inference_latency_ms_last {_last_latency:.1f}",
        "# HELP visiondesk_workers_running workers de câmera ativos",
        f"visiondesk_workers_running {running}",
        f'visiondesk_capability{{name="edge"}} {1 if caps["edge_detector"] else 0}',
        f'visiondesk_capability{{name="vlm"}} {1 if caps["vlm"] else 0}',
        f'visiondesk_capability{{name="edge_ocr"}} {1 if caps["edge_ocr"] else 0}',
    ]
    for pipe, n in _by_pipeline.items():
        lines.append(f'visiondesk_inferences_by_pipeline{{pipeline="{pipe}"}} {n}')
    return "\n".join(lines) + "\n"
