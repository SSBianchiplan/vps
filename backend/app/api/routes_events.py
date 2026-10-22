"""Timeline de RASTREABILIDADE TOTAL do sistema (trilha de auditoria unificada).

Lê `audit_event` (app.audit): cada leitura/contagem/detecção/descrição/análise,
alteração de dados (CRUD), evento de câmera, ação (AGIR), captura VPS e alerta de
monitor — uma linha com envelope comum. Filtros por categoria/ação/fonte/severidade/texto.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from .. import audit, audit_pg
from ..discovery import saved as saved_cams

router = APIRouter(prefix="/events", tags=["events"])

# compat: modo de inferência (UI antiga) ↔ ação canônica da trilha
_MODE_ACTION = {"LER": "READ", "CONTAR": "COUNT", "DETECTAR": "DETECT",
                "RASTREAR": "TRACK", "DESCREVER": "DESCRIBE", "ANALISAR": "ANALYZE"}
_ACTION_MODE = {v: k for k, v in _MODE_ACTION.items()}

_CAT_LABEL = {
    "INFERENCE": "Inferência", "CAMERA": "Câmera", "DATA": "Dados", "ACTION": "Ação",
    "RECORDING": "Gravação", "VPS": "VPS", "MONITOR": "Monitor", "SYSTEM": "Sistema",
}
_CAT_ICON = {"INFERENCE": "👁", "CAMERA": "📷", "DATA": "✏️", "ACTION": "⚡",
             "RECORDING": "🎬", "VPS": "🧵", "MONITOR": "📶", "SYSTEM": "⚙"}


def _source_label(source_id: str | None) -> str | None:
    if not source_id:
        return None
    if source_id == "screen":
        return "🖥 Tela (captura)"
    if source_id.startswith("cam:"):
        cam = saved_cams.get(source_id[len("cam:"):])
        if cam and cam.get("name"):
            return cam["name"]
    return source_id


@router.get("")
def list_events(
    category: str | None = Query(default=None),
    action: str | None = Query(default=None),
    mode: str | None = Query(default=None, description="compat: LER/CONTAR/... → ação"),
    source_id: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    q: str | None = Query(default=None, description="busca em resumo/entidade/ação"),
    since: str | None = Query(default=None),
    limit: int = Query(default=300, le=2000),
) -> dict[str, Any]:
    if mode and not action:
        action = _MODE_ACTION.get(mode.upper(), mode)
    rows = audit.query(category=category, action=action, source_id=source_id,
                       severity=severity, q=q, since=since, limit=limit)
    for r in rows:
        r["source_label"] = _source_label(r.get("source_id")) or _CAT_LABEL.get(r.get("category", ""), "sistema")
        r["timestamp"] = r.get("event_ts")  # alias p/ a UI
        # aliases legados (compat com Dashboard/Monitor/CameraDetail/MiniChart)
        pay = r.get("payload") or {}
        sev = r.get("severity")
        r["severidade"] = "alerta" if sev == "warn" else sev
        r["titulo"] = r.get("summary")
        r["detection_id"] = r.get("event_id")
        r["mode"] = _ACTION_MODE.get(r.get("action")) if r.get("category") == "INFERENCE" else None
        r["latency_ms"] = pay.get("latency_ms")
        r["confidence"] = pay.get("confidence")
        r["pipeline"] = pay.get("pipeline")
    return {"events": rows, "count": len(rows)}


@router.get("/categories")
def categories() -> dict[str, Any]:
    counts = audit.summary().get("by_category", {})
    return {"categories": [
        {"key": c, "label": _CAT_LABEL.get(c, c), "icon": _CAT_ICON.get(c, "•"),
         "count": counts.get(c, 0)}
        for c in audit.CATEGORIES
    ]}


@router.get("/sources")
def event_sources() -> dict[str, Any]:
    out = []
    for s in audit.sources():
        sid = s["source_id"]
        out.append({"source_id": sid, "descricao": _source_label(sid)})
    return {"sources": out}


@router.get("/summary")
def events_summary(since: str | None = Query(default=None)) -> dict[str, Any]:
    return audit.summary(since=since)


@router.post("/sync-pg")
def sync_pg() -> dict[str, Any]:
    """Sincroniza a trilha runtime (SQLite) → PostgreSQL (base visiondesk_audit)."""
    return audit_pg.sync()
