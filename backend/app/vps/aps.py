"""APS — Advanced Planning & Scheduling (ref. Siemens Opcenter APS).

Capacidade finita (A01) + skills + capacidade>1 + expedite. Diferencial VPS (A03):
durações REAIS da visão (GLX_FACT_VPS_PHASE) realimentam o plano (variance). Publicar
emite SCHEDULE_PUBLISHED no Fio Dourado (vínculo). What-if, CTP/ATP, utilização/gargalo.
Ver VPS_APS_Planejamento_Avancado.md.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from . import gold, store, templates

DONE = ("COMPLETED", "ARCHIVED")
RULES = {"prioridade": "Prioridade (gargalo/aging)", "menor_prazo": "Menor prazo (run)", "fifo": "FIFO (abertura)"}
_priority: dict[str, int] = {}   # expedite: tag_id → -1 (prioritário)


def _p(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _csv(s: str | None) -> list[str]:
    return [x.strip().lower() for x in (s or "").split(",") if x.strip()]


def _default_resources() -> list[dict[str, Any]]:
    if not store.resources(status="ativo"):
        for n in ("Centro A", "Centro B", "Centro C"):
            store.upsert_resource({"name": n, "capacity": 1, "calendar": "T1"})
    return store.resources(status="ativo")


def expedite(tag_id: str) -> None:
    _priority[tag_id] = -1


def clear_expedite() -> None:
    _priority.clear()


def _rule_key(rule: str, op: dict[str, Any], rank: dict[str, int]):
    if rule == "menor_prazo":
        return (op["run_min"], rank.get(op["tag"], 99))
    if rule == "fifo":
        return (op["opened"] or "", rank.get(op["tag"], 99))
    return (rank.get(op["tag"], 99), op["run_min"])


def _candidates(phase: str, res: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Recursos elegíveis: sem skills declaradas = geral; com skills = precisa cobrir a fase."""
    skilled = [r for r in res if phase.lower() in _csv(r.get("skills"))]
    if skilled:
        return skilled
    return [r for r in res if not _csv(r.get("skills"))] or res


def generate(scenario: str = "base", rule: str = "prioridade") -> dict[str, Any]:
    base = datetime.now(timezone.utc).replace(microsecond=0)
    res = _default_resources()
    tags = [t for t in store.all_tags() if t.get("entity_type") == "OP" and t["state"] not in DONE]
    # rank: expedite primeiro, depois ordem do board (aging/gargalo)
    rank = {t["tag_id"]: i for i, t in enumerate(sorted(tags, key=lambda t: (_priority.get(t["tag_id"], 0), 0)))}
    obs = {(r["tag_id"], r["phase"]): r for r in gold.fact_phase()}

    ops: list[dict[str, Any]] = []
    for t in tags:
        for i, ph in enumerate(templates.get(t["template_id"])["phases"]):
            sla = ph.get("sla_hours") or 1
            ops.append({"tag": t["tag_id"], "phase": ph["id"], "lvl": i, "run_min": int(sla * 60),
                        "setup_min": 15, "opened": t.get("opened_ts")})

    lanes: dict[str, list[datetime]] = {r["resource_key"]: [base] * max(1, int(r["capacity"] or 1)) for r in res}
    res_lasttag: dict[str, str] = {}
    tag_end: dict[str, datetime] = {}
    seqc: dict[str, int] = {}
    rows: list[dict[str, Any]] = []
    maxlvl = max((o["lvl"] for o in ops), default=-1) + 1

    for lvl in range(maxlvl):
        for o in sorted([x for x in ops if x["lvl"] == lvl], key=lambda x: _rule_key(rule, x, rank)):
            cands = _candidates(o["phase"], res)
            best = None  # (resource_key, lane_idx, est)
            for r in cands:
                rk = r["resource_key"]
                for li, free in enumerate(lanes[rk]):
                    est = max(free, tag_end.get(o["tag"], base))
                    if best is None or est < best[2]:
                        best = (rk, li, est)
            rk, li, est = best  # type: ignore[misc]
            setup = o["setup_min"] if res_lasttag.get(rk) not in (None, o["tag"]) else 0
            start = est + timedelta(minutes=setup)
            end = start + timedelta(minutes=o["run_min"])
            lanes[rk][li] = end; res_lasttag[rk] = o["tag"]; tag_end[o["tag"]] = end
            seqc[rk] = seqc.get(rk, 0) + 1
            ob = obs.get((o["tag"], o["phase"]))
            variance = int(ob["duration_h"] * 60) - o["run_min"] if (ob and ob.get("duration_h") is not None) else None
            rows.append({
                "schedule_id": "sch_" + uuid.uuid4().hex[:12], "tag_id": o["tag"], "operation": o["phase"],
                "resource_key": rk, "seq": seqc[rk], "planned_start": start.isoformat(),
                "planned_end": end.isoformat(), "setup_min": setup, "run_min": o["run_min"],
                "priority": rank.get(o["tag"], 0), "rule_used": rule,
                "actual_start": ob["entered_ts"] if ob else None, "actual_end": ob["exited_ts"] if ob else None,
                "variance_min": variance,
            })
    store.save_schedule(scenario, rows)
    return {"scenario": scenario, "rule": rule, "operations": len(rows),
            "expedited": [t for t in _priority], "load": load(scenario),
            "resources": [{"resource_key": r["resource_key"], "name": r["name"], "capacity": r["capacity"]} for r in res]}


def load(scenario: str = "base") -> list[dict[str, Any]]:
    """Utilização por recurso (capacidade finita) + gargalo."""
    rows = store.schedule(scenario)
    if not rows:
        return []
    t0 = min(_p(r["planned_start"]) for r in rows)
    t1 = max(_p(r["planned_end"]) for r in rows)
    span = max(1.0, (t1 - t0).total_seconds() / 60)
    by: dict[str, dict[str, Any]] = {}
    for r in rows:
        d = by.setdefault(r["resource_key"], {"resource_key": r["resource_key"], "busy_min": 0, "ops": 0, "cap": 1})
        d["busy_min"] += r["run_min"] + r["setup_min"]; d["ops"] += 1
    for rk in by:
        cap = next((int(x["capacity"] or 1) for x in store.resources() if x["resource_key"] == rk), 1)
        by[rk]["cap"] = cap
        by[rk]["util"] = round(100 * by[rk]["busy_min"] / (span * cap), 1)
    out = list(by.values())
    mx = max((d["util"] for d in out), default=0)
    for d in out:
        d["bottleneck"] = d["util"] == mx and mx > 0
    return sorted(out, key=lambda d: -d["util"])


def kpis(scenario: str = "base") -> dict[str, Any]:
    rows = store.schedule(scenario)
    if not rows:
        return {"scenario": scenario, "empty": True}
    starts = [_p(r["planned_start"]) for r in rows]
    ends = [_p(r["planned_end"]) for r in rows]
    span = (max(ends) - min(starts)).total_seconds() / 60
    busy = sum(r["run_min"] for r in rows)
    n_res = len({r["resource_key"] for r in rows})
    setup = sum(r["setup_min"] for r in rows)
    var = [r["variance_min"] for r in rows if r["variance_min"] is not None]
    adher = [v for v in var if abs(v) <= 30]
    breached = [v for v in var if v > 30]
    return {
        "scenario": scenario,
        "CLD_Capacity_Utilization": round(100 * busy / (span * n_res), 1) if span and n_res else 0.0,
        "CLD_Changeover_Time_min": setup,
        "CLD_Schedule_Variance_min": sum(var) if var else 0,
        "CLD_Schedule_Adherence_APS": round(100 * len(adher) / len(var), 1) if var else None,
        "CLD_Operations": len(rows),
        "CLD_Resources": n_res,
        "CLD_Makespan_h": round(span / 60, 1),
        "CLD_Replan_Suggested": len(breached) > 0,        # real estourou → sugere replano
        "CLD_Breached_Ops": len(breached),
    }


def compare(rules: list[str]) -> list[dict[str, Any]]:
    """What-if: gera cada regra num cenário e devolve os KPIs p/ comparar."""
    out = []
    for rl in rules:
        if rl not in RULES:
            continue
        scn = f"whatif_{rl}"
        generate(scn, rl)
        out.append({"rule": rl, "label": RULES[rl], "scenario": scn, "kpis": kpis(scn)})
    return out


def ctp(qty: int = 1, due: str | None = None) -> dict[str, Any]:
    """CTP/ATP: data prometida p/ uma nova OP (capacidade finita, rota PANEL)."""
    base = datetime.now(timezone.utc).replace(microsecond=0)
    sched = store.schedule("base")
    # início ≈ quando o chão começa a vagar (menor fim entre recursos), respeitando 'agora'
    if sched:
        earliest_free = min(_p(r["planned_end"]) for r in sched)
        start = max(base, earliest_free)
    else:
        start = base
    phases = templates.get(templates.resolve_template("PANEL", "OP"))["phases"]
    factor = max(1.0, qty / 12.0)
    total = sum(int((p.get("sla_hours") or 1) * 60 * factor) + 15 for p in phases)
    end = start + timedelta(minutes=total)
    on_time = None
    if due:
        try:
            on_time = end <= _p(due)
        except ValueError:
            on_time = None
    return {"ctp_start": start.isoformat(), "ctp_end": end.isoformat(),
            "lead_h": round(total / 60, 1), "qty": qty, "due": due, "on_time": on_time}


def publish(scenario: str = "base") -> dict[str, Any]:
    """Publica o cronograma p/ execução e EMITE SCHEDULE_PUBLISHED no Fio (vínculo §8)."""
    n = store.publish_schedule(scenario)
    ts = store.now_iso()
    tags = {r["tag_id"] for r in store.schedule(scenario)}
    for t in tags:
        tag = store.get_tag(t)
        store.append_event({"tag_id": t, "action": "SCHEDULE_PUBLISHED",
                            "phase": (tag or {}).get("current_phase"), "domain": "PLANNING",
                            "event_ts": ts, "owner": "Operations", "payload": {"scenario": scenario}})
    return {"published": n, "scenario": scenario, "events": len(tags)}
