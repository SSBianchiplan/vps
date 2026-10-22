"""Aplica o projeto PostgreSQL 'teste_sistema' ao sistema (DB do cockpit).

Lê os 10 OPs do Postgres (schemas vps_core/vps_proj/vps_md/vps_aps/vps_recon) e
materializa nas tabelas do app (vps_tag/vps_event/vps_lineage/pending/occurrence/
schedule/erp_doc/operator/resource), preservando linhagem e relacionamentos.
Idempotente: reseta as tabelas VPS do app antes de importar.
"""
from __future__ import annotations

from typing import Any

from . import operators, store, templates

_VM = {"OP_OPENED": "LER", "PICK_COMPLETED": "CONTAR", "PICK_SHORT": "CONTAR",
       "OP_OPERATION_DONE": "DESCREVER", "MEASUREMENT_APPROVED": "ANALISAR"}
_DONE = ("COMPLETED", "ARCHIVED")


def import_teste(dbname: str = "teste_sistema") -> dict[str, Any]:
    import psycopg  # type: ignore
    pg = psycopg.connect(f"dbname={dbname}", connect_timeout=3)
    pc = pg.cursor()

    # limpa o estado VPS do app (idempotente)
    store.reset()
    store.clear_erp_docs()
    conn = store.get_connection()
    for t in ("vps_operator", "vps_resource", "vps_schedule"):
        conn.execute(f"DELETE FROM {t}")

    out = {k: 0 for k in ("operators", "resources", "tags", "events", "lineage", "pendings", "occurrences", "schedule", "erp_docs")}

    # ── master data: operadores / recursos ──────────────────────────
    pc.execute("SELECT operator_id,nome,matricula,badge_token,role,stations,skills,shift,status FROM vps_md.vps_dim_operator WHERE is_current")
    for o in pc.fetchall():
        operators.upsert_operator({"operator_id": o[0], "name": o[1], "matricula": o[2], "badge": o[3], "role": o[4],
                               "stations": ",".join(o[5] or []), "skills": ",".join(o[6] or []), "shift": o[7],
                               "status": "ativo" if o[8] == "ATIVO" else "inativo"}); out["operators"] += 1
    pc.execute("SELECT resource_key,nome,capacidade,calendario,status FROM vps_md.vps_dim_resource WHERE is_current")
    for r in pc.fetchall():
        store.upsert_resource({"resource_key": r[0], "name": r[1], "capacity": int(r[2] or 1),
                               "calendar": r[3], "status": "ativo" if r[4] == "ATIVO" else "inativo"}); out["resources"] += 1

    # ── tempos por tag (min/max evento) ─────────────────────────────
    pc.execute("SELECT tag_id, min(event_ts), max(event_ts) FROM vps_core.vps_event GROUP BY tag_id")
    span = {row[0]: (row[1], row[2]) for row in pc.fetchall()}

    # ── tags (projeção de estado) ───────────────────────────────────
    pc.execute("SELECT segment,entity_type,natural_key,instance,tag_id,parent_tag_id,template_id,current_phase,current_state,created_ts FROM vps_proj.vps_dim_tag")
    for t in pc.fetchall():
        seg, et, nk, inst, tag_id, parent, tpl, phase, state, created = t
        mn, mx = span.get(tag_id, (created, created))
        store.upsert_tag({"tag_id": tag_id, "segment": seg, "entity_type": et, "natural_key": nk, "instance": inst,
                          "state": state, "template_id": tpl or templates.resolve_template(seg, et),
                          "current_phase": phase, "parent_tag_id": parent,
                          "opened_ts": _iso(mn), "closed_ts": _iso(mx) if state in _DONE else None,
                          "last_event_ts": _iso(mx)}); out["tags"] += 1

    # ── eventos (event store) ───────────────────────────────────────
    parent_of = _parents(pg.cursor())   # cursor separado p/ não atropelar o resultset de eventos
    pc.execute("SELECT event_id,tag_id,action,phase,owner,operator_id,station_id,model_version,confidence,payload,recon_status,recon_erp_doc,image_uri,event_ts FROM vps_core.vps_event ORDER BY event_ts")
    for e in pc.fetchall():
        eid, tag_id, action, phase, owner, op, stn, mv, conf, payload, recon, erp, img, ets = e
        store.append_event({"event_id": str(eid), "tag_id": tag_id, "parent_tag_id": parent_of.get(tag_id),
                            "action": action, "phase": phase, "domain": templates.domain_of(action),
                            "event_ts": _iso(ets), "source_type": stn, "station_id": stn, "operator_id": op,
                            "vision_mode": _VM.get(action), "model_version": mv,
                            "confidence": float(conf) if conf is not None else None,
                            "payload": payload or {}, "owner": owner, "recon_status": recon or "PENDING",
                            "image_uri": img}); out["events"] += 1

    # ── linhagem ────────────────────────────────────────────────────
    pc.execute("SELECT parent_tag_id, child_tag_id, relation FROM vps_core.vps_lineage")
    for p, c, rel in pc.fetchall():
        store.add_lineage(p, c, rel); out["lineage"] += 1

    # ── pendências ──────────────────────────────────────────────────
    pc.execute("SELECT tag_id,item_key,is_blocking,opened_ts,cleared_ts FROM vps_proj.vps_pending")
    for tag_id, item, blk, op_ts, cl in pc.fetchall():
        pid = store.open_pending(tag_id, "PICKING", f"PICK_SHORT — falta {item}", bool(blk), opened_ts=_iso(op_ts))
        if cl:
            store.clear_pendings(tag_id, "PICKING")
        out["pendings"] += 1

    # ── ocorrências ─────────────────────────────────────────────────
    pc.execute("SELECT tag_id,occ_type,severity,phase,evidence_uri,raised_ts,resolved_ts,resolution FROM vps_proj.vps_occurrence")
    for tag_id, kind, sev, phase, ev, rts, res_ts, res in pc.fetchall():
        oid = store.raise_occurrence(tag_id, phase, kind, sev or "alerta", res or kind, ev, raised_ts=_iso(rts))
        if res_ts:
            store.resolve_occurrence(oid)
        out["occurrences"] += 1

    # ── APS (cronograma) ────────────────────────────────────────────
    pc.execute("SELECT scenario_id,tag_id,operation,resource_key,planned_start,planned_end,setup_min,run_min,priority,rule_used,actual_start,actual_end,variance_min FROM vps_aps.glx_fact_vps_schedule ORDER BY scenario_id,resource_key,planned_start")
    sched: dict[str, list[dict[str, Any]]] = {}
    seqc: dict[str, int] = {}
    for s in pc.fetchall():
        scn, tag_id, oper, rk, ps, pe, setup, run, prio, rule, as_, ae, var = s
        seqc[rk] = seqc.get(rk, 0) + 1
        sched.setdefault(scn or "base", []).append({
            "schedule_id": store.new_id("sch"), "tag_id": tag_id, "operation": oper, "resource_key": rk,
            "seq": seqc[rk], "planned_start": _iso(ps), "planned_end": _iso(pe), "setup_min": setup or 0,
            "run_min": run or 0, "priority": prio or 0, "rule_used": rule,
            "actual_start": _iso(as_), "actual_end": _iso(ae), "variance_min": var, "published": 0})
    for scn, rows in sched.items():
        store.save_schedule(scn, rows); out["schedule"] += len(rows)

    # ── docs ERP (reconciliação) ────────────────────────────────────
    pc.execute("SELECT t.natural_key, r.erp_doc, r.status FROM vps_recon.vps_reconciliation r JOIN vps_proj.vps_dim_tag t ON t.tag_id=r.tag_id")
    docs = [{"natural_key": nk, "doc": doc, "status": st, "source": "teste_sistema"} for nk, doc, st in pc.fetchall()]
    out["erp_docs"] = store.upsert_erp_docs(docs)

    pg.close()
    return {"ok": True, "db": dbname, **out}


def _parents(_cur) -> dict[str, str]:
    # mapa child→parent (1º pai) a partir da linhagem
    _cur.execute("SELECT child_tag_id, parent_tag_id FROM vps_core.vps_lineage")
    out: dict[str, str] = {}
    for child, parent in _cur.fetchall():
        out.setdefault(child, parent)
    return out


def _iso(ts) -> str | None:
    return ts.isoformat() if ts is not None else None
