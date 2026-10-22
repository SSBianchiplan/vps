"""Trilha de auditoria / rastreabilidade total do sistema.

Fonte única da timeline de Eventos: cada ação (leitura, contagem, detecção,
descrição, análise, CRUD de dados, evento de câmera, ação AGIR, captura VPS,
alerta de monitor) vira 1 linha em `audit_event` (append-only).

`record()` é best-effort: NUNCA derruba o caminho quente do chamador.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from .db.database import get_connection

# Categorias canônicas (espelhadas no PG).
CATEGORIES = ["INFERENCE", "CAMERA", "DATA", "ACTION", "RECORDING", "VPS", "MONITOR", "SYSTEM"]

# Modo de inferência → verbo de ação + ícone (mapeamento estável).
_MODE_ACTION = {"LER": "READ", "CONTAR": "COUNT", "DETECTAR": "DETECT",
                "RASTREAR": "TRACK", "DESCREVER": "DESCRIBE", "ANALISAR": "ANALYZE"}
_ICON = {
    "INFERENCE": "👁", "CAMERA": "📷", "DATA": "✏️", "ACTION": "⚡",
    "RECORDING": "🎬", "VPS": "🧵", "MONITOR": "📶", "SYSTEM": "⚙",
    "READ": "🔤", "COUNT": "🔢", "DETECT": "🎯", "DESCRIBE": "📝", "ANALYZE": "✅",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def icon_for(category: str, action: str | None = None) -> str:
    return _ICON.get((action or "").upper()) or _ICON.get(category, "•")


def summarize_inference(modo: str | None, result: dict[str, Any]) -> tuple[str, str]:
    """(resumo, severidade) p/ um evento de inferência — reaproveitado no backfill."""
    modo = (modo or "").upper()
    if modo == "CONTAR" or modo == "DETECTAR":
        contagens = result.get("contagens", {}) or {}
        total = int(result.get("total", sum(int(v) for v in contagens.values())) or 0)
        cruz = int(result.get("cruzamentos_linha", 0) or 0)
        partes = ", ".join(f"{v} {k}" for k, v in contagens.items()) or f"{total} objeto(s)"
        titulo = partes + (f" · {cruz} cruzamento(s)" if cruz else "")
        sev = "alerta" if ("pessoa" in contagens or "person" in contagens) else "info"
        return titulo, sev
    if modo == "LER":
        textos = [l.get("texto", "") for l in (result.get("leituras", []) or []) if l.get("texto")]
        return (" · ".join(textos[:4]) if textos else "nenhuma leitura"), "info"
    if modo == "RASTREAR":
        active = int(result.get("active", 0) or 0)
        cross = int(result.get("crossings", 0) or 0)
        wip = int(result.get("wip", 0) or 0)
        dex = int(result.get("dwell_exceeded", 0) or 0)
        titulo = f"{active} track(s) · {cross} cruzamento(s) · WIP {wip}"
        return titulo, ("alerta" if dex else "info")
    if modo == "DESCREVER":
        desc = (result.get("descricao") or "").strip()
        alertas = result.get("alertas", []) or []
        return (desc[:160] if desc else "—"), ("alerta" if alertas else "info")
    if modo == "ANALISAR":
        veredito = (result.get("veredito") or "").strip()
        resumo = (result.get("resumo") or "").strip()
        titulo = (f"{veredito} — {resumo}" if resumo else veredito) or "—"
        up = veredito.upper()
        sev = "ok" if up in ("OK", "APROVADO", "CONFORME") else "nok" if veredito else "info"
        return titulo, sev
    return "evento", "info"


# ── Escrita ──────────────────────────────────────────────────────────
def record(
    category: str,
    action: str,
    *,
    summary: str = "",
    severity: str = "info",
    actor: str | None = None,
    source_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    correlation_id: str | None = None,
    payload: Any = None,
    event_ts: str | None = None,
    event_id: str | None = None,
) -> str | None:
    """Grava 1 evento na trilha. Best-effort (engole erros).

    `event_id` explícito (determinístico) torna o backfill idempotente.
    """
    eid = event_id or f"aud_{uuid.uuid4().hex[:16]}"
    try:
        get_connection().execute(
            "INSERT OR IGNORE INTO audit_event(event_id, event_ts, category, action, severity, actor,"
            " source_id, entity_type, entity_id, summary, correlation_id, payload_json)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (eid, event_ts or _now(), category, action, severity, actor, source_id,
             entity_type, entity_id, summary[:500] if summary else summary, correlation_id,
             json.dumps(payload, ensure_ascii=False, default=str) if payload is not None else None),
        )
        # espelho opcional no PostgreSQL (se DSN configurado) — best-effort.
        from . import audit_pg
        audit_pg.mirror(eid)
        return eid
    except Exception:  # noqa: BLE001 — auditoria nunca quebra o chamador
        return None


def from_inference(result: Any, frame_ref: str | None = None) -> None:
    """Atalho chamado por save_inference: mapeia modo→ação + resumo."""
    try:
        modo = result.mode.value if hasattr(result.mode, "value") else str(result.mode)
        summary, sev = summarize_inference(modo, result.result or {})
        record(
            "INFERENCE", _MODE_ACTION.get(modo, modo),
            summary=summary, severity=sev, actor="visão",
            source_id=result.source_id, entity_type="inference",
            entity_id=result.detection_id, correlation_id=result.detection_id,
            event_ts=getattr(result, "timestamp", None),
            payload={"pipeline": result.pipeline, "latency_ms": result.latency_ms,
                     "confidence": result.confidence, "task_id": result.task_id,
                     "model": result.model_name, "frame_ref": frame_ref},
        )
    except Exception:  # noqa: BLE001
        pass


# ── Leitura ──────────────────────────────────────────────────────────
def _row(r: Any) -> dict[str, Any]:
    d = dict(r)
    raw = d.pop("payload_json", None)
    try:
        d["payload"] = json.loads(raw) if raw else None
    except (json.JSONDecodeError, TypeError):
        d["payload"] = None
    d["icone"] = icon_for(d.get("category", ""), d.get("action"))
    return d


def query(
    category: str | None = None,
    action: str | None = None,
    source_id: str | None = None,
    severity: str | None = None,
    q: str | None = None,
    since: str | None = None,
    limit: int = 300,
) -> list[dict[str, Any]]:
    backfill()  # garante histórico na 1ª leitura
    sql = "SELECT * FROM audit_event"
    clauses: list[str] = []
    p: list[Any] = []
    if category:
        clauses.append("category = ?"); p.append(category.upper())
    if action:
        clauses.append("action = ?"); p.append(action.upper())
    if source_id:
        clauses.append("source_id = ?"); p.append(source_id)
    if severity:
        clauses.append("severity = ?"); p.append(severity)
    if since:
        clauses.append("event_ts >= ?"); p.append(since)
    if q:
        clauses.append("(summary LIKE ? OR entity_id LIKE ? OR action LIKE ?)")
        p += [f"%{q}%"] * 3
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY event_ts DESC LIMIT ?"; p.append(min(limit, 2000))
    return [_row(r) for r in get_connection().execute(sql, p).fetchall()]


def sources() -> list[dict[str, Any]]:
    rows = get_connection().execute(
        "SELECT DISTINCT source_id FROM audit_event WHERE source_id IS NOT NULL ORDER BY source_id"
    ).fetchall()
    return [{"source_id": dict(r)["source_id"]} for r in rows]


def summary(since: str | None = None) -> dict[str, Any]:
    backfill()
    conn = get_connection()
    where = "WHERE event_ts >= ?" if since else ""
    p: list[Any] = [since] if since else []
    total = conn.execute(f"SELECT COUNT(*) AS n FROM audit_event {where}", p).fetchone()["n"]
    by_category = {dict(r)["category"]: dict(r)["n"] for r in conn.execute(
        f"SELECT category, COUNT(*) AS n FROM audit_event {where} GROUP BY category", p).fetchall()}
    by_severity = {dict(r)["severity"]: dict(r)["n"] for r in conn.execute(
        f"SELECT severity, COUNT(*) AS n FROM audit_event {where} GROUP BY severity", p).fetchall()}
    by_day = [{"day": dict(r)["day"], "count": dict(r)["n"]} for r in conn.execute(
        f"SELECT substr(event_ts,1,10) AS day, COUNT(*) AS n FROM audit_event {where} "
        f"GROUP BY day ORDER BY day DESC LIMIT 14", p).fetchall()]
    alerts = by_severity.get("alerta", 0) + by_severity.get("nok", 0) + by_severity.get("warn", 0)
    # compat MiniChart: contagem por modo de inferência (ação→modo PT)
    _amode = {"READ": "LER", "COUNT": "CONTAR", "DETECT": "DETECTAR", "TRACK": "RASTREAR", "DESCRIBE": "DESCREVER", "ANALYZE": "ANALISAR"}
    by_mode: dict[str, int] = {}
    for r in conn.execute(
        f"SELECT action, COUNT(*) AS n FROM audit_event {('WHERE event_ts >= ? AND' if since else 'WHERE')} "
        f"category='INFERENCE' GROUP BY action", p).fetchall():
        d = dict(r)
        by_mode[_amode.get(d["action"], d["action"])] = d["n"]
    return {"total_events": total, "alerts": alerts, "by_category": by_category,
            "by_severity": by_severity, "by_mode": by_mode, "by_day": list(reversed(by_day))}


# ── Backfill (uma vez) a partir dos fatos já existentes ──────────────
_backfilled = False


def backfill(force: bool = False) -> int:
    """Popula audit_event a partir de fatos antigos (detecção/ação/gravação)
    quando a trilha está vazia — para a timeline não nascer vazia."""
    global _backfilled
    if _backfilled and not force:
        return 0
    _backfilled = True
    conn = get_connection()
    try:
        n = conn.execute("SELECT COUNT(*) AS n FROM audit_event").fetchone()["n"]
        if n and not force:
            return 0
    except Exception:  # noqa: BLE001 — tabela ainda não criada
        return 0
    inserted = 0
    # inferências
    try:
        rows = conn.execute(
            "SELECT f.detection_id, f.source_id, f.task_id, f.timestamp, f.pipeline,"
            " f.latency_ms, f.confidence, f.result_json, t.modo AS modo "
            "FROM fact_detection f LEFT JOIN dim_task t ON f.task_id=t.task_id "
            "ORDER BY f.timestamp DESC LIMIT 2000").fetchall()
        for r in rows:
            d = dict(r)
            try:
                res = json.loads(d.get("result_json") or "{}")
            except (json.JSONDecodeError, TypeError):
                res = {}
            s, sev = summarize_inference(d.get("modo"), res)
            record("INFERENCE", _MODE_ACTION.get((d.get("modo") or "").upper(), d.get("modo") or "EVENT"),
                   summary=s, severity=sev, actor="visão", source_id=d.get("source_id"),
                   entity_type="inference", entity_id=d.get("detection_id"),
                   correlation_id=d.get("detection_id"), event_ts=d.get("timestamp"),
                   event_id=f"aud_inf_{d.get('detection_id')}",
                   payload={"pipeline": d.get("pipeline"), "latency_ms": d.get("latency_ms"),
                            "confidence": d.get("confidence")})
            inserted += 1
    except Exception:  # noqa: BLE001
        pass
    # ações (AGIR)
    try:
        for r in conn.execute("SELECT * FROM fact_action ORDER BY timestamp DESC LIMIT 1000").fetchall():
            d = dict(r)
            sev = "ok" if d.get("status") == "success" else "nok" if d.get("status") else "info"
            record("ACTION", (d.get("action_type") or "ACTION").upper(),
                   summary=f"{d.get('action_type')} → {d.get('target') or ''} ({d.get('status')})",
                   severity=sev, actor="agir", entity_type="action", entity_id=d.get("action_id"),
                   correlation_id=d.get("detection_id"), event_ts=d.get("timestamp"),
                   event_id=f"aud_act_{d.get('action_id')}",
                   payload={"http_status": d.get("http_status"), "error": d.get("error_message")})
            inserted += 1
    except Exception:  # noqa: BLE001
        pass
    # gravações
    try:
        for r in conn.execute("SELECT * FROM fact_recording ORDER BY timestamp DESC LIMIT 1000").fetchall():
            d = dict(r)
            record("RECORDING", "RECORD",
                   summary=f"gravação {d.get('trigger') or ''} ({d.get('mode') or ''})",
                   severity="info", actor="sistema", source_id=d.get("source_id"),
                   entity_type="recording", entity_id=d.get("rec_id"), event_ts=str(d.get("timestamp")),
                   event_id=f"aud_rec_{d.get('rec_id')}", payload={"image_uri": d.get("image_uri")})
            inserted += 1
    except Exception:  # noqa: BLE001
        pass
    return inserted
