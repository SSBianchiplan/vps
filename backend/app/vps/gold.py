"""Camada Gold / modelo semântico GLX_ (SPEC_VPS §9.4) — projeções p/ BI/Power BI.

Fatos e dimensões derivados do Event Store, prontos p/ exportação (CSV/JSON) e
consumo no modelo `GLX_`. Sem dependência extra (csv/json stdlib).
"""
from __future__ import annotations

import csv
import io
from typing import Any

from . import engine, store, templates


def _hours(a: str | None, b: str | None) -> float | None:
    da, db = engine._parse_ts(a), engine._parse_ts(b)  # noqa: SLF001 — reuso do parser
    if not da or not db:
        return None
    return round(max(0.0, (db - da).total_seconds() / 3600.0), 2)


def dim_phase() -> list[dict[str, Any]]:
    """GLX_DIM_PHASE — fases declaradas por template (ordem, SLA, modo de visão)."""
    rows = []
    for tpl in templates.TEMPLATES.values():
        for i, p in enumerate(tpl["phases"]):
            rows.append({"template_id": tpl["template_id"], "segment": tpl["segment"],
                         "phase": p["id"], "phase_order": i + 1, "sla_hours": p.get("sla_hours"),
                         "vision_mode": (p.get("vision") or {}).get("mode")})
    return rows


def dim_tag() -> list[dict[str, Any]]:
    """GLX_DIM_TAG — dimensão do Fio (estado atual + lead time)."""
    rows = []
    for t in store.all_tags(include_archived=True):
        rows.append({"tag_id": t["tag_id"], "segment": t["segment"], "entity_type": t["entity_type"],
                     "natural_key": t["natural_key"], "state": t["state"], "template_id": t["template_id"],
                     "current_phase": t["current_phase"], "parent_tag_id": t.get("parent_tag_id"),
                     "opened_ts": t.get("opened_ts"), "closed_ts": t.get("closed_ts"),
                     "lead_time_h": _hours(t.get("opened_ts"), t.get("closed_ts"))})
    return rows


def fact_event() -> list[dict[str, Any]]:
    """GLX_FACT_VPS_EVENT — grão = evento."""
    rows = []
    for e in store.recent_events(100000):
        rows.append({"event_id": e["event_id"], "tag_id": e["tag_id"], "parent_tag_id": e.get("parent_tag_id"),
                     "action": e["action"], "phase": e.get("phase"), "domain": e.get("domain"),
                     "event_ts": e["event_ts"], "vision_mode": e.get("vision_mode"),
                     "confidence": e.get("confidence"), "model_version": e.get("model_version"),
                     "owner": e.get("owner"), "recon_status": e.get("recon_status")})
    return rows


def fact_phase() -> list[dict[str, Any]]:
    """GLX_FACT_VPS_PHASE — grão = fase percorrida por Fio (duração, SLA, aderência)."""
    rows = []
    for t in store.all_tags(include_archived=True):
        seq = [(e["phase"], e["event_ts"]) for e in store.events_for(t["tag_id"]) if e.get("phase")]
        comp: list[list[str]] = []
        for ph, ts in seq:
            if not comp or comp[-1][0] != ph:
                comp.append([ph, ts, ts])
            else:
                comp[-1][2] = ts
        for i, (ph, entered, _last) in enumerate(comp):
            exited = comp[i + 1][1] if i + 1 < len(comp) else t.get("closed_ts")
            dur = _hours(entered, exited)
            sla = (engine._phase_def(t["template_id"], ph) or {}).get("sla_hours")  # noqa: SLF001
            rows.append({"tag_id": t["tag_id"], "template_id": t["template_id"], "phase": ph,
                         "entered_ts": entered, "exited_ts": exited, "duration_h": dur,
                         "sla_hours": sla, "adherent": (dur <= sla) if (dur is not None and sla) else None})
    return rows


MODELS = {
    "fact_event": ("GLX_FACT_VPS_EVENT", fact_event),
    "fact_phase": ("GLX_FACT_VPS_PHASE", fact_phase),
    "dim_tag": ("GLX_DIM_TAG", dim_tag),
    "dim_phase": ("GLX_DIM_PHASE", dim_phase),
}


def to_csv(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    cols: list[str] = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols)
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()
