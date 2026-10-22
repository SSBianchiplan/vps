"""Espelho da trilha de auditoria no PostgreSQL (base `visiondesk_audit`).

- Runtime grava em SQLite (rápido, sempre on).
- PostgreSQL é o destino durável/escala: schema `audit` append-only (trigger de
  imutabilidade + partições mensais). Ver db/audit_postgres.sql + scripts/setup_audit_db.py.
- `mirror()` (live) só atua se VISIONDESK_AUDIT_PG=1. `sync()` copia em lote sob demanda.
"""
from __future__ import annotations

import os
import threading
from typing import Any

from .db.database import get_connection

_DSN = os.environ.get("VISIONDESK_AUDIT_PG_DSN", "dbname=visiondesk_audit")
_LIVE = os.environ.get("VISIONDESK_AUDIT_PG", "").lower() in ("1", "true", "yes")
_lock = threading.Lock()
_conn: Any = None

_INSERT = (
    "INSERT INTO audit.audit_event(event_id,event_ts,category,action,severity,actor,"
    "source_id,entity_type,entity_id,summary,correlation_id,payload_json)"
    " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
    " ON CONFLICT (event_id, event_ts) DO NOTHING"
)
_COLS = ("event_id", "event_ts", "category", "action", "severity", "actor",
         "source_id", "entity_type", "entity_id", "summary", "correlation_id", "payload_json")


def _connect() -> Any:
    import psycopg  # type: ignore
    return psycopg.connect(_DSN, connect_timeout=2)


def _live_conn() -> Any:
    global _conn
    if _conn is None:
        _conn = _connect()
    return _conn


def mirror(event_id: str) -> None:
    """Espelha 1 evento no PG (só se live habilitado). Best-effort."""
    if not _LIVE:
        return
    try:
        row = get_connection().execute(
            "SELECT event_id,event_ts,category,action,severity,actor,source_id,"
            "entity_type,entity_id,summary,correlation_id,payload_json "
            "FROM audit_event WHERE event_id=?", (event_id,)).fetchone()
        if not row:
            return
        with _lock:
            c = _live_conn()
            c.execute(_INSERT, tuple(dict(row)[k] for k in _COLS))
            c.commit()
    except Exception:  # noqa: BLE001 — nunca quebra o caminho quente
        global _conn
        _conn = None  # força reconexão na próxima


def sync(limit: int = 100_000) -> dict[str, Any]:
    """Copia em lote SQLite→PG (idempotente via ON CONFLICT). Retorna contagens."""
    rows = get_connection().execute(
        "SELECT event_id,event_ts,category,action,severity,actor,source_id,"
        "entity_type,entity_id,summary,correlation_id,payload_json "
        "FROM audit_event ORDER BY event_ts ASC LIMIT ?", (limit,)).fetchall()
    try:
        conn = _connect()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"PG indisponível: {str(exc)[:80]}", "synced": 0}
    n = 0
    try:
        cur = conn.cursor()
        for r in rows:
            cur.execute(_INSERT, tuple(dict(r)[k] for k in _COLS))
            n += cur.rowcount
        conn.commit()
        total = cur.execute("SELECT count(*) FROM audit.audit_event").fetchone()[0]
    finally:
        conn.close()
    return {"ok": True, "synced": n, "scanned": len(rows), "pg_total": int(total)}


def status() -> dict[str, Any]:
    """Inventário p/ o módulo Bases."""
    try:
        conn = _connect()
    except Exception:  # noqa: BLE001
        return {"key": "audit_pg", "name": "Trilha de auditoria (PostgreSQL)", "kind": "PostgreSQL",
                "status": "off", "detail": f"base '{_DSN}' indisponível (rode scripts/setup_audit_db.py)",
                "metrics": {}}
    try:
        cur = conn.cursor()
        total = cur.execute("SELECT count(*) FROM audit.audit_event").fetchone()[0]
        cats = cur.execute("SELECT count(DISTINCT category) FROM audit.audit_event").fetchone()[0]
        parts = cur.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema='audit'").fetchone()[0]
    finally:
        conn.close()
    return {"key": "audit_pg", "name": "Trilha de auditoria (PostgreSQL)", "kind": "PostgreSQL · audit",
            "status": "ok" if total else "warn", "detail": f"{_DSN} · schema audit (append-only, particionado)",
            "metrics": {"eventos": int(total), "categorias": int(cats), "partições": int(parts)}}
