"""Persistência do VPS — Event Store append-only + projeções (tag/lineage/exceções)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from ..db.database import get_connection


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ── EVENT STORE (append-only) ────────────────────────────────────────
def append_event(ev: dict[str, Any]) -> str:
    eid = ev.get("event_id") or new_id("vev")
    get_connection().execute(
        """INSERT INTO vps_event(event_id, tag_id, parent_tag_id, action, phase, domain,
             event_ts, source_type, station_id, operator_id, vision_mode, model_version,
             confidence, payload_json, owner, recon_status, image_uri, ingested_ts)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (eid, ev["tag_id"], ev.get("parent_tag_id"), ev["action"], ev.get("phase"),
         ev.get("domain"), ev["event_ts"], ev.get("source_type"), ev.get("station_id"),
         ev.get("operator_id"), ev.get("vision_mode"), ev.get("model_version"),
         ev.get("confidence"), json.dumps(ev.get("payload") or {}, ensure_ascii=False),
         ev.get("owner"), ev.get("recon_status", "PENDING"), ev.get("image_uri"), now_iso()),
    )
    return eid


def events_for(tag_id: str) -> list[dict[str, Any]]:
    rows = get_connection().execute(
        "SELECT * FROM vps_event WHERE tag_id=? ORDER BY event_ts, ingested_ts", (tag_id,)
    ).fetchall()
    return [_event_row(r) for r in rows]


def recent_events(limit: int = 100) -> list[dict[str, Any]]:
    rows = get_connection().execute(
        "SELECT * FROM vps_event ORDER BY event_ts DESC LIMIT ?", (limit,)
    ).fetchall()
    return [_event_row(r) for r in rows]


def max_event_rowid() -> int:
    """Marca d'água do WebSocket do cockpit (e das cargas incrementais).

    No PostgreSQL é a coluna `seq` (BIGSERIAL), garantida por
    `db.database._pg_contrato_eventos`; no SQLite, o rowid, que `traduz_sql`
    reescreve para `seq`.
    """
    r = get_connection().execute("SELECT MAX(rowid) m FROM vps_event").fetchone()
    return int(dict(r)["m"]) if r and dict(r)["m"] is not None else 0


def events_after(rowid: int, limit: int = 200) -> list[dict[str, Any]]:
    """Eventos novos (rowid > ?) p/ push incremental no WS — sem cross-thread."""
    rows = get_connection().execute(
        "SELECT rowid AS _rowid, * FROM vps_event WHERE rowid > ? ORDER BY rowid LIMIT ?", (rowid, limit)
    ).fetchall()
    out = []
    for r in rows:
        d = _event_row(r)
        out.append(d)
    return out


def _event_row(r: Any) -> dict[str, Any]:
    d = dict(r)
    try:
        d["payload"] = json.loads(d.pop("payload_json") or "{}")
    except (json.JSONDecodeError, TypeError):
        d["payload"] = {}
    return d


# ── DIM TAG (estado atual) ───────────────────────────────────────────
def get_tag(tag_id: str) -> dict[str, Any] | None:
    r = get_connection().execute("SELECT * FROM vps_tag WHERE tag_id=?", (tag_id,)).fetchone()
    return dict(r) if r else None


def upsert_tag(tag: dict[str, Any]) -> None:
    get_connection().execute(
        """INSERT INTO vps_tag(tag_id, segment, entity_type, natural_key, instance, state,
             template_id, current_phase, parent_tag_id, opened_ts, closed_ts, last_event_ts)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(tag_id) DO UPDATE SET
             state=excluded.state, template_id=excluded.template_id,
             current_phase=excluded.current_phase, parent_tag_id=excluded.parent_tag_id,
             closed_ts=excluded.closed_ts, last_event_ts=excluded.last_event_ts""",
        (tag["tag_id"], tag.get("segment"), tag.get("entity_type"), tag.get("natural_key"),
         tag.get("instance"), tag["state"], tag.get("template_id"), tag.get("current_phase"),
         tag.get("parent_tag_id"), tag.get("opened_ts"), tag.get("closed_ts"), tag.get("last_event_ts")),
    )


def all_tags(include_archived: bool = False) -> list[dict[str, Any]]:
    sql = "SELECT * FROM vps_tag"
    if not include_archived:
        sql += " WHERE state != 'ARCHIVED'"
    sql += " ORDER BY last_event_ts DESC"
    return [dict(r) for r in get_connection().execute(sql).fetchall()]


# ── LINHAGEM ─────────────────────────────────────────────────────────
def add_lineage(parent: str, child: str, relation: str) -> None:
    get_connection().execute(
        "INSERT OR IGNORE INTO vps_lineage(parent_tag_id, child_tag_id, relation) VALUES (?,?,?)",
        (parent, child, relation),
    )


def children_of(tag_id: str) -> list[dict[str, Any]]:
    return [dict(r) for r in get_connection().execute(
        "SELECT * FROM vps_lineage WHERE parent_tag_id=?", (tag_id,)).fetchall()]


def parents_of(tag_id: str) -> list[dict[str, Any]]:
    return [dict(r) for r in get_connection().execute(
        "SELECT * FROM vps_lineage WHERE child_tag_id=?", (tag_id,)).fetchall()]


# ── PENDÊNCIAS ───────────────────────────────────────────────────────
def open_pending(tag_id: str, phase: str | None, reason: str, blocking: bool = True, opened_ts: str | None = None) -> str:
    pid = new_id("vpd")
    get_connection().execute(
        "INSERT INTO vps_pending(pending_id, tag_id, phase, reason, blocking, opened_ts) VALUES (?,?,?,?,?,?)",
        (pid, tag_id, phase, reason, 1 if blocking else 0, opened_ts or now_iso()),
    )
    return pid


def clear_pendings(tag_id: str, phase: str | None = None) -> int:
    sql = "UPDATE vps_pending SET cleared_ts=? WHERE tag_id=? AND cleared_ts IS NULL"
    params: list[Any] = [now_iso(), tag_id]
    if phase:
        sql += " AND phase=?"
        params.append(phase)
    cur = get_connection().execute(sql, params)
    return cur.rowcount or 0


def get_pending(pending_id: str) -> dict[str, Any] | None:
    r = get_connection().execute("SELECT * FROM vps_pending WHERE pending_id=?", (pending_id,)).fetchone()
    return dict(r) if r else None


def clear_pending_by_id(pending_id: str) -> bool:
    cur = get_connection().execute(
        "UPDATE vps_pending SET cleared_ts=? WHERE pending_id=? AND cleared_ts IS NULL",
        (now_iso(), pending_id))
    return bool(cur.rowcount)


def pendings_for(tag_id: str, open_only: bool = True) -> list[dict[str, Any]]:
    sql = "SELECT * FROM vps_pending WHERE tag_id=?" + (" AND cleared_ts IS NULL" if open_only else "")
    rows = get_connection().execute(sql + " ORDER BY opened_ts DESC", (tag_id,)).fetchall()
    return [dict(r) for r in rows]


def all_open_pendings() -> list[dict[str, Any]]:
    rows = get_connection().execute(
        "SELECT * FROM vps_pending WHERE cleared_ts IS NULL ORDER BY opened_ts").fetchall()
    return [dict(r) for r in rows]


def open_pending_count(tag_id: str) -> int:
    r = get_connection().execute(
        "SELECT COUNT(*) c FROM vps_pending WHERE tag_id=? AND cleared_ts IS NULL", (tag_id,)).fetchone()
    return int(dict(r)["c"]) if r else 0


# ── OCORRÊNCIAS ──────────────────────────────────────────────────────
def raise_occurrence(tag_id: str, phase: str | None, kind: str, severity: str,
                     note: str, evidence_uri: str | None = None, raised_ts: str | None = None) -> str:
    oid = new_id("voc")
    get_connection().execute(
        """INSERT INTO vps_occurrence(occ_id, tag_id, phase, kind, severity, note, evidence_uri, raised_ts)
           VALUES (?,?,?,?,?,?,?,?)""",
        (oid, tag_id, phase, kind, severity, note, evidence_uri, raised_ts or now_iso()),
    )
    return oid


def occurrences_for(tag_id: str, open_only: bool = False) -> list[dict[str, Any]]:
    sql = "SELECT * FROM vps_occurrence WHERE tag_id=?" + (" AND resolved_ts IS NULL" if open_only else "")
    rows = get_connection().execute(sql + " ORDER BY raised_ts DESC", (tag_id,)).fetchall()
    return [dict(r) for r in rows]


def open_occurrence_count(tag_id: str) -> int:
    r = get_connection().execute(
        "SELECT COUNT(*) c FROM vps_occurrence WHERE tag_id=? AND resolved_ts IS NULL", (tag_id,)).fetchone()
    return int(dict(r)["c"]) if r else 0


def get_occurrence(occ_id: str) -> dict[str, Any] | None:
    r = get_connection().execute("SELECT * FROM vps_occurrence WHERE occ_id=?", (occ_id,)).fetchone()
    return dict(r) if r else None


def resolve_occurrence(occ_id: str) -> bool:
    cur = get_connection().execute(
        "UPDATE vps_occurrence SET resolved_ts=? WHERE occ_id=? AND resolved_ts IS NULL",
        (now_iso(), occ_id))
    return bool(cur.rowcount)


def has_open_occurrence(tag_id: str, kind: str) -> bool:
    r = get_connection().execute(
        "SELECT 1 FROM vps_occurrence WHERE tag_id=? AND kind=? AND resolved_ts IS NULL LIMIT 1",
        (tag_id, kind)).fetchone()
    return r is not None


def set_recon_status(tag_id: str, status: str) -> None:
    get_connection().execute("UPDATE vps_event SET recon_status=? WHERE tag_id=?", (status, tag_id))


def reset() -> None:
    """Limpa as tabelas de processo VPS (mantém docs ERP). Usado por seed?reset=true."""
    conn = get_connection()
    for t in ("vps_event", "vps_tag", "vps_lineage", "vps_pending", "vps_occurrence",
              "vps_phase_log", "vps_pick_demand"):
        conn.execute(f"DELETE FROM {t}")


# ── DOCUMENTOS ERP/MES (conector) ────────────────────────────────────
def upsert_erp_docs(docs: list[dict[str, Any]]) -> int:
    conn = get_connection()
    n = 0
    for d in docs:
        nk = (d.get("natural_key") or "").strip()
        if not nk:
            continue
        conn.execute(
            """INSERT INTO vps_erp_doc(natural_key, doc, qty, value, status, source, ingested_ts)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(natural_key) DO UPDATE SET
                 doc=excluded.doc, qty=excluded.qty, value=excluded.value,
                 status=excluded.status, source=excluded.source, ingested_ts=excluded.ingested_ts""",
            (nk, d.get("doc"), d.get("qty"), d.get("value"), d.get("status", "OPEN"),
             d.get("source", "manual"), now_iso()),
        )
        n += 1
    return n


def erp_docs() -> list[dict[str, Any]]:
    return [dict(r) for r in get_connection().execute("SELECT * FROM vps_erp_doc ORDER BY natural_key").fetchall()]


def get_erp_doc(natural_key: str) -> dict[str, Any] | None:
    r = get_connection().execute("SELECT * FROM vps_erp_doc WHERE natural_key=?", (natural_key,)).fetchone()
    return dict(r) if r else None


def clear_erp_docs() -> None:
    get_connection().execute("DELETE FROM vps_erp_doc")


# ── RECURSOS (APS) ───────────────────────────────────────────────────
def upsert_resource(d: dict[str, Any]) -> dict[str, Any]:
    rk = d.get("resource_key") or ("res_" + d["name"].strip().lower().replace(" ", "_"))
    get_connection().execute(
        """INSERT INTO vps_resource(resource_key, name, capacity, skills, calendar, status, created_at)
           VALUES (?,?,?,?,?,?,?)
           ON CONFLICT(resource_key) DO UPDATE SET name=excluded.name, capacity=excluded.capacity,
             skills=excluded.skills, calendar=excluded.calendar, status=excluded.status""",
        (rk, d["name"], int(d.get("capacity", 1)), d.get("skills"), d.get("calendar"),
         d.get("status", "ativo"), now_iso()))
    r = get_connection().execute("SELECT * FROM vps_resource WHERE resource_key=?", (rk,)).fetchone()
    return dict(r)


def resources(status: str | None = None) -> list[dict[str, Any]]:
    sql = "SELECT * FROM vps_resource" + (" WHERE status=?" if status else "")
    return [dict(r) for r in get_connection().execute(sql + " ORDER BY name", ([status] if status else [])).fetchall()]


# ── CRONOGRAMA (APS) ─────────────────────────────────────────────────
def save_schedule(scenario_id: str, rows: list[dict[str, Any]]) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM vps_schedule WHERE scenario_id=?", (scenario_id,))
    for r in rows:
        conn.execute(
            """INSERT INTO vps_schedule(schedule_id, scenario_id, tag_id, operation, resource_key, seq,
                 planned_start, planned_end, setup_min, run_min, priority, rule_used,
                 actual_start, actual_end, variance_min, published, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (r["schedule_id"], scenario_id, r["tag_id"], r["operation"], r["resource_key"], r["seq"],
             r["planned_start"], r["planned_end"], r.get("setup_min", 0), r.get("run_min", 0),
             r.get("priority", 0), r.get("rule_used"), r.get("actual_start"), r.get("actual_end"),
             r.get("variance_min"), r.get("published", 0), now_iso()))


def schedule(scenario_id: str) -> list[dict[str, Any]]:
    rows = get_connection().execute(
        "SELECT * FROM vps_schedule WHERE scenario_id=? ORDER BY resource_key, seq", (scenario_id,)).fetchall()
    return [dict(r) for r in rows]


def schedule_row(schedule_id: str) -> dict[str, Any] | None:
    r = get_connection().execute(
        "SELECT * FROM vps_schedule WHERE schedule_id=?", (schedule_id,)).fetchone()
    return dict(r) if r else None


def update_schedule_row(schedule_id: str, patch: dict[str, Any]) -> None:
    """UPDATE de uma operacao. O arrasto no Gantt mexe em UMA linha; reescrever
    o cenario inteiro (save_schedule) apagaria e recriaria todas as outras, e o
    change_log registraria dezenas de mudancas que ninguem fez."""
    if not patch:
        return
    campos = ", ".join(f"{k}=?" for k in patch)
    get_connection().execute(
        f"UPDATE vps_schedule SET {campos} WHERE schedule_id=?",
        (*patch.values(), schedule_id))


def scenarios() -> list[str]:
    rows = get_connection().execute("SELECT DISTINCT scenario_id FROM vps_schedule ORDER BY scenario_id").fetchall()
    return [dict(r)["scenario_id"] for r in rows]


def publish_schedule(scenario_id: str) -> int:
    cur = get_connection().execute("UPDATE vps_schedule SET published=1 WHERE scenario_id=?", (scenario_id,))
    return cur.rowcount or 0
