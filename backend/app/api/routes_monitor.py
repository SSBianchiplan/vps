"""Módulo de Monitoramento (IoT) — visão geral agregada + sinal de transmissão.

`/monitor/overview` agrega KPIs e séries em SQL (leitura rápida, sem trafegar
linhas). `/monitor/signal` mede o enlace Wi-Fi até cada câmera e o RSSI local.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Query

from .. import audit
from ..db.repository import repository
from ..discovery import saved
from ..discovery import signal as sig

router = APIRouter(prefix="/monitor", tags=["monitor"])

_RANGE_DAYS = {"7d": 7, "30d": 30, "90d": 90, "12m": 365, "tudo": None}

# Rastreio de transições (em memória) — emite MONITOR só quando o estado MUDA,
# nunca a cada poll/amostra (evita inundar a trilha).
_last_online: dict[str, bool] = {}
_last_degraded: dict[str, bool] = {}


def _emit_online_transitions(probes: list[dict[str, Any]]) -> None:
    for p in probes:
        if not p.get("enabled", True):          # desligada não é "queda"
            continue
        key = str(p.get("id") or p.get("host") or p.get("name") or "?")
        now_on = bool(p.get("online"))
        prev = _last_online.get(key)
        _last_online[key] = now_on
        if prev is None or prev == now_on:
            continue                             # 1ª leitura ou sem mudança
        sid = f"cam:{p['id']}" if p.get("id") else p.get("host")
        name = p.get("name") or p.get("host") or key
        if now_on:
            audit.record("MONITOR", "ONLINE", summary=f"câmera online: {name}", severity="ok",
                         actor="monitor", source_id=sid, entity_type="camera", entity_id=p.get("id"),
                         payload={"latency_ms": p.get("latency_ms")})
        else:
            audit.record("MONITOR", "OFFLINE", summary=f"câmera offline: {name}", severity="alerta",
                         actor="monitor", source_id=sid, entity_type="camera", entity_id=p.get("id"))


def _bad_link(c: dict[str, Any]) -> tuple[bool, str]:
    """Enlace degradado? (perda/latência/buffer). Retorna (ruim, motivo)."""
    loss = c.get("packet_loss_pct") or 0
    lat = c.get("latency_ms") or 0
    buf = c.get("buffer_pct")
    if loss > 5:
        return True, f"perda {loss:.0f}%"
    if lat and lat > 300:
        return True, f"latência {lat:.0f}ms"
    if buf is not None and buf < 20:
        return True, f"buffer {buf:.0f}%"
    return False, ""


def _emit_signal_transitions(cameras: list[dict[str, Any]]) -> None:
    for c in cameras:
        key = str(c.get("host") or c.get("name") or "?")
        bad, reason = _bad_link(c)
        prev = _last_degraded.get(key)
        _last_degraded[key] = bad
        if prev is None or prev == bad:
            continue
        name = c.get("name") or key
        if bad:
            audit.record("MONITOR", "DEGRADED", summary=f"enlace degradado: {name} ({reason})",
                         severity="alerta", actor="monitor", source_id=c.get("host"),
                         entity_type="camera",
                         payload={"latency_ms": c.get("latency_ms"), "packet_loss_pct": c.get("packet_loss_pct"),
                                  "buffer_pct": c.get("buffer_pct")})
        else:
            audit.record("MONITOR", "RECOVERED", summary=f"enlace recuperado: {name}", severity="ok",
                         actor="monitor", source_id=c.get("host"), entity_type="camera")


@router.get("/overview")
async def overview(period: str = Query(default="12m", pattern="^(7d|30d|90d|12m|tudo)$")) -> dict[str, Any]:
    days = _RANGE_DAYS.get(period, 365)
    since = None
    if days is not None:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    agg = repository.aggregate_overview(since=since)
    cams = saved.list_public()

    # Disponibilidade média: razão de câmeras alcançáveis agora. Usa só os probes
    # de câmera (rápidos), sem o custo da leitura de RSSI do Wi-Fi local.
    probes = await sig.probe_cameras(cams)
    by_ip = {c["ip"]: c for c in cams}                            # join probe→câmera (id/enabled)
    for p in probes:
        cam = by_ip.get(p["host"], {})
        p["enabled"] = cam.get("enabled", True)                   # liga/desliga (raiz saved.py)
        p["id"] = cam.get("id")
    enabled = [c for c in cams if c.get("enabled", True)]
    _emit_online_transitions(probes)                              # trilha MONITOR (só em transição)
    online = [p for p in probes if p["online"] and p["enabled"]]  # desligada não conta como queda
    # None quando nada está ligado → UI mostra "—" (não "0%", que confunde)
    disponibilidade = round(100 * len(online) / len(enabled), 1) if enabled else None

    return {
        "period": period,
        "kpis": {
            "disponibilidade_media": disponibilidade,
            "alertas_detectados": agg["alerts"],
            "consumo_total_wh": None,        # sem telemetria de energia (slot futuro)
            "cameras": len(cams),
            "cameras_enabled": len(enabled),
            "cameras_online": len(online),
            "eventos_total": agg["total_events"],
        },
        "availability_series": [
            {"id": c.get("id"), "name": c["name"], "host": c["host"], "bars": c["bars"],
             "online": c["online"], "latency_ms": c["latency_ms"], "enabled": c["enabled"]}
            for c in probes
        ],
        "events_by_day": agg["by_day"],
        "events_by_mode": agg["by_mode"],
    }


def _persist_metrics(cameras: list[dict[str, Any]]) -> None:
    _emit_signal_transitions(cameras)            # trilha MONITOR: degradação/recuperação de enlace
    for c in cameras:
        repository.record_metric(
            source_id=c.get("host") or c.get("name") or "?",
            latency_ms=c.get("latency_ms"), jitter_ms=c.get("jitter_ms"),
            packet_loss=c.get("packet_loss_pct"), buffer_pct=c.get("buffer_pct"),
            fps=c.get("fps_est"),
            throughput_kbps=round((c.get("fps_est") or 0) * 40.0, 1),  # ~40KB/frame (estimativa)
        )


@router.get("/signal")
async def signal_status() -> dict[str, Any]:
    import asyncio
    snap = await sig.snapshot_signal(saved.list_public())
    # Persiste a amostra na série temporal (TimescaleDB-ready) p/ o gráfico em tempo real.
    try:
        await asyncio.to_thread(_persist_metrics, snap.get("cameras", []))
    except Exception:  # noqa: BLE001
        pass
    return snap


@router.get("/series")
def metric_series(
    source_id: str | None = Query(default=None),
    limit: int = Query(default=120, ge=2, le=600),
) -> dict[str, Any]:
    """Série temporal de rede/buffer p/ o gráfico em tempo real (latência/jitter/buffer/throughput)."""
    return {"samples": repository.query_metrics(source_id, limit)}
