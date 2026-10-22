"""Seed do projeto 'Teste Sistema' (PostgreSQL) — 10 OPs com TODAS as bases preenchidas
e relacionadas (Fio Dourado: master data → event store → linhagem → projeções →
reconciliação → APS → gold). Idempotente: trunca e recria. Ver VPS_DB_PostgreSQL_Migracao.md.

Uso: .venv/bin/python scripts/seed_teste_sistema.py
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import psycopg
from psycopg.types.json import Json

DB = "dbname=teste_sistema"
SEG = "PANEL"
TPL = "PANEL_ETO_V1"
PHASES = ["ENGINEERING", "PURCHASING", "PICKING", "ASSEMBLY", "TESTING", "SHIPPING", "BILLING"]
EXIT = {"ENGINEERING": "DRAWINGS_APPROVED", "PURCHASING": "SUPPLY_LINKED", "PICKING": "PICK_COMPLETED",
        "ASSEMBLY": "OP_OPERATION_DONE", "TESTING": "MEASUREMENT_APPROVED", "SHIPPING": "SHIPPED", "BILLING": "INVOICE_ISSUED"}
SLA_H = {"ENGINEERING": 24, "PURCHASING": 48, "PICKING": 8, "ASSEMBLY": 40, "TESTING": 8, "SHIPPING": 24, "BILLING": 24}
PHASE_OWNER = {"ENGINEERING": "Engineering", "PURCHASING": "Supply", "PICKING": "Supply",
               "ASSEMBLY": "Operations", "TESTING": "Quality", "SHIPPING": "Operations", "BILLING": "Finance"}
PHASE_VISION = {"PICKING": "CONTAR", "ASSEMBLY": "DESCREVER", "TESTING": "ANALISAR", "ENGINEERING": "LER"}
RES = ["res_eng-01", "res_cel-mont-01", "res_pick-01", "res_qc-01"]
CLIENTS = ["COOP-DEMO", "ALIMENTOS-DEMO", "MOTORES-DEMO", "IMPLEMENTOS-DEMO"]
ITEMS = ["RES-22K", "CAP-100UF", "DISJ-3X63", "CABO-2,5MM", "BORNE-X"]
BASE = datetime(2026, 6, 18, 8, 0, tzinfo=timezone.utc)


def tag(et: str, key: str, inst: str = "01") -> str:
    return f"VPS:{SEG}:{et}:{key}:{inst}"


def main() -> None:
    conn = psycopg.connect(DB)
    cur = conn.cursor()

    # idempotente: limpa dados (TRUNCATE não dispara o trigger append-only de UPDATE/DELETE)
    for t in ["vps_core.vps_event", "vps_core.vps_lineage", "vps_proj.vps_dim_tag", "vps_proj.vps_pending",
              "vps_proj.vps_occurrence", "vps_recon.vps_reconciliation", "vps_aps.glx_fact_vps_schedule",
              "glx.glx_fact_vps_event", "glx.glx_fact_vps_phase", "glx.glx_fact_vps_pending", "glx.glx_dim_phase",
              "glx.glx_dim_date", "vps_md.vps_dim_operator", "vps_md.vps_dim_station", "vps_md.vps_dim_item",
              "vps_md.vps_dim_client", "vps_md.vps_dim_resource", "vps_md.vps_dim_shift", "vps_md.vps_dim_model",
              "vps_md.vps_dim_segment", "vps_md.vps_dim_template", "vps_stg.stg_legacy_order",
              "vps_stg.depara_tagid", "vps_stg.migration_batch",
              "vps_plan.card_dependency", "vps_plan.baseline_card", "vps_plan.baseline",
              "vps_plan.card", "vps_plan.wbs", "vps_plan.project", "vps_plan.project_calendar"]:
        cur.execute(f"TRUNCATE {t} RESTART IDENTITY CASCADE")

    # ── MASTER DATA (SCD2) ──────────────────────────────────────────
    cur.execute("INSERT INTO vps_stg.migration_batch(source, description, status, finished_ts) "
                "VALUES ('SEED','Teste Sistema · 10 OPs','DONE', now()) RETURNING batch_id")
    batch = cur.fetchone()[0]

    ops = [("u123", "J. Silva", "M-123", "QR-U123", "Operador", ["ALMOX-02"], ["picking", "conferencia"], "T1"),
           ("u204", "M. Souza", "M-204", "QR-U204", "Supervisor", ["ALMOX-02", "LINHA-01"], ["supervisao"], "T1"),
           ("u311", "R. Lima", "M-311", "QR-U311", "Operador", ["LINHA-01"], ["montagem"], "T2")]
    cur.executemany("INSERT INTO vps_md.vps_dim_operator(operator_id,nome,matricula,badge_token,role,stations,skills,shift) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", ops)
    cur.executemany("INSERT INTO vps_md.vps_dim_station(station_id,nome,area,segment) VALUES (%s,%s,%s,%s)",
                    [("ALMOX-02", "Almoxarifado 02", "Logística", SEG), ("LINHA-01", "Linha Montagem 01", "Produção", SEG), ("QC-01", "Posto Qualidade", "Qualidade", SEG)])
    cur.executemany("INSERT INTO vps_md.vps_dim_item(item_key,descricao,familia,uom) VALUES (%s,%s,%s,%s)",
                    [(i, f"Item {i}", "Elétrico", "UN") for i in ITEMS])
    cur.executemany("INSERT INTO vps_md.vps_dim_client(client_key,nome,segmento_cli) VALUES (%s,%s,%s)",
                    [(c, c, "Indústria") for c in CLIENTS])
    cur.executemany("INSERT INTO vps_md.vps_dim_resource(resource_key,nome,tipo,capacidade,calendario) VALUES (%s,%s,%s,%s,%s)",
                    [("res_eng-01", "Engenharia 01", "celula", 1, "T1"), ("res_cel-mont-01", "Célula Montagem 01", "celula", 1, "T1"),
                     ("res_pick-01", "Picking 01", "posto", 2, "T1"), ("res_qc-01", "Qualidade 01", "posto", 1, "T1")])
    cur.executemany("INSERT INTO vps_md.vps_dim_shift(shift_key,nome,inicio,fim,dias) VALUES (%s,%s,%s,%s,%s)",
                    [("T1", "Turno 1", "06:00", "14:00", ["seg", "ter", "qua", "qui", "sex"]),
                     ("T2", "Turno 2", "14:00", "22:00", ["seg", "ter", "qua", "qui", "sex"])])
    cur.executemany("INSERT INTO vps_md.vps_dim_model(model_name,model_version,modo,min_confidence) VALUES (%s,%s,%s,%s)",
                    [("yolo-tag", "3.2.1", "CONTAR", 0.95), ("ocr-op", "2.0", "LER", 0.90),
                     ("vlm-desc", "opus-4.8", "DESCREVER", 0.0), ("anomaly", "1.4", "ANALISAR", 0.97)])
    cur.executemany("INSERT INTO vps_md.vps_dim_segment(segment,descricao) VALUES (%s,%s)",
                    [("PANEL", "Painel Elétrico (ETO)"), ("FOOD", "Alimentos"), ("PHARMA", "Farma"), ("GENERIC", "Genérico")])
    tdef = {"phases": [{"id": p, "sla_hours": SLA_H[p]} for p in PHASES]}
    cur.execute("INSERT INTO vps_md.vps_dim_template(template_id,segment,version,definition) VALUES (%s,%s,%s,%s)",
                (TPL, SEG, "v1", Json(tdef)))

    # gold dims
    cur.executemany("INSERT INTO glx.glx_dim_phase(phase,ordem) VALUES (%s,%s)", [(p, i + 1) for i, p in enumerate(PHASES)])
    days = {(BASE + timedelta(days=d)).date() for d in range(40)}
    cur.executemany("INSERT INTO glx.glx_dim_date(date_key,dt,ano,mes,dia,semana,trimestre) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    [(int(dd.strftime("%Y%m%d")), dd, dd.year, dd.month, dd.day, int(dd.strftime("%V")), (dd.month - 1) // 3 + 1) for dd in sorted(days)])

    def dim_tag(et, key, parent, phase, state, recon=None, inst="01"):
        cur.execute("INSERT INTO vps_proj.vps_dim_tag(segment,entity_type,natural_key,instance,parent_tag_id,template_id,current_phase,current_state,recon_status,is_blocked) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (tag_id) DO NOTHING",
                    (SEG, et, key, inst, parent, TPL if et == "OP" else None, phase, state, recon, state == "EXCEPTION"))

    def lineage(parent, child, rel):
        cur.execute("INSERT INTO vps_core.vps_lineage(parent_tag_id,child_tag_id,relation) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING", (parent, child, rel))

    def event(tg, action, phase, ts, owner, *, op=None, st=None, vm=None, conf=None, payload=None, recon=None, erp=None, comp=None):
        eid = uuid.uuid4()
        model = {"CONTAR": ("yolo-tag", "3.2.1"), "LER": ("ocr-op", "2.0"), "DESCREVER": ("vlm-desc", "opus-4.8"), "ANALISAR": ("anomaly", "1.4")}.get(vm or "", (None, None))
        cur.execute("INSERT INTO vps_core.vps_event(event_id,tag_id,action,phase,owner,operator_id,station_id,model_name,model_version,confidence,payload,recon_status,recon_erp_doc,compensates_id,event_ts) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (eid, tg, action, phase, owner, op, st, model[0], model[1], conf, Json(payload or {}), recon, erp, comp, ts))
        # espelho no gold (fact_event)
        cur.execute("INSERT INTO glx.glx_fact_vps_event(event_id,tag_id,segment,entity_type,action,phase,owner,operator_id,station_id,model_version,confidence,recon_status,event_ts,date_key) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (eid, tg, SEG, tg.split(":")[2], action, phase, owner, op, st, model[1], conf, recon, ts, int(ts.strftime("%Y%m%d"))))
        return eid

    # ── 10 OPs (event-sourced + linhagem + projeções + APS + recon + gold) ──
    so_done, proj_done = set(), set()
    for i in range(1, 11):
        g = (i - 1) // 4
        so_k, proj_k = f"PV-2026-90{g+1:02d}", f"PRJ-2026-2{g+1:02d}"
        so, proj = tag("SO", so_k), tag("PROJ", proj_k)
        opk = f"OP-2026-050{i:02d}"
        op = tag("OP", opk)
        client = CLIENTS[i % len(CLIENTS)]
        item = ITEMS[i % len(ITEMS)]
        # estados variados: 1 ARCHIVED, 2-4 COMPLETED, 5-7 IN_PROCESS, 8-10 EXCEPTION
        state = "ARCHIVED" if i == 1 else "COMPLETED" if i <= 4 else "IN_PROCESS" if i <= 7 else "EXCEPTION"
        progress = 7 if i <= 4 else (2 + i % 3) if i <= 7 else 2  # nº de fases concluídas
        cur_phase = PHASES[min(progress, 6)] if state not in ("COMPLETED", "ARCHIVED") else "BILLING"
        recon = "MATCHED" if state in ("COMPLETED", "ARCHIVED") else ("DIVERGENT" if i == 9 else "PENDING")

        if so_k not in so_done:
            dim_tag("SO", so_k, None, "RELEASED", "COMPLETED"); so_done.add(so_k)
        if proj_k not in proj_done:
            dim_tag("PROJ", proj_k, so, "PLANNING", "COMPLETED"); lineage(so, proj, "DERIVES"); proj_done.add(proj_k)
        dim_tag("OP", opk, proj, cur_phase, state, recon)
        lineage(proj, op, "DERIVES")

        t = BASE + timedelta(hours=i * 6)
        event(op, "OP_OPENED", "ENGINEERING", t, "Operations", op="u123", st="LINHA-01", vm="LER", conf=0.99,
              payload={"cliente": client, "item": item}, recon=recon, erp=f"ERP-{opk}")
        for pidx in range(progress):
            ph = PHASES[pidx]; t += timedelta(hours=SLA_H[ph] * 0.6)
            vm = PHASE_VISION.get(ph)
            event(op, EXIT[ph], ph, t, PHASE_OWNER[ph], op="u123", st="LINHA-01", vm=vm,
                  conf=0.96 if vm else None, payload={"total": 12} if ph == "PICKING" else {})
            # gold fact_phase (fase concluída, duração observada)
            dur = int(SLA_H[ph] * 60 * (0.6 if i % 2 else 0.9))
            cur.execute("INSERT INTO glx.glx_fact_vps_phase(tag_id,phase,planned_min,duration_min,delay_min,started_ts,ended_ts) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                        (op, ph, SLA_H[ph] * 60, dur, dur - SLA_H[ph] * 60, t - timedelta(minutes=dur), t))

        # filhos de linhagem + recon + exceções
        pick = tag("PICK", f"PK-{opk[-5:]}")
        dim_tag("PICK", f"PK-{opk[-5:]}", op, "PICKING", "COMPLETED" if progress > 2 else "IN_PROCESS")
        lineage(op, pick, "DERIVES")
        itm = tag("ITEM", item, inst=f"{i:02d}")
        dim_tag("ITEM", item, pick, None, "BOUND", inst=f"{i:02d}"); lineage(pick, itm, "GROUPS")
        po = tag("PO", f"PO-2026-55{i:02d}")
        dim_tag("PO", f"PO-2026-55{i:02d}", None, None, "BOUND"); lineage(itm, po, "SUPPLIES")

        if state in ("COMPLETED", "ARCHIVED"):
            ship = tag("SHIP", f"SH-{opk[-5:]}"); dim_tag("SHIP", f"SH-{opk[-5:]}", op, "TRANSIT", "COMPLETED"); lineage(op, ship, "DERIVES")
            inv = tag("INV", f"NF-2026-3{i:03d}"); dim_tag("INV", f"NF-2026-3{i:03d}", ship, None, "COMPLETED"); lineage(ship, inv, "DERIVES")

        if state == "EXCEPTION":
            ce = event(op, "PICK_SHORT", "PICKING", t + timedelta(hours=1), "Supply", op="u123", st="ALMOX-02",
                       vm="CONTAR", conf=0.93, payload={"total": 11, "alvo": 12})
            cur.execute("INSERT INTO vps_proj.vps_pending(tag_id,cause_event_id,item_key,is_blocking,hourly_cost,opened_ts,aging_hours) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                        (op, ce, item, True, 50.0, t, 18.5))
            cur.execute("INSERT INTO vps_proj.vps_occurrence(tag_id,occ_type,severity,phase,model_version) VALUES (%s,%s,%s,%s,%s)",
                        (op, "LOW_CONFIDENCE", "alerta", "PICKING", "3.2.1"))

        # reconciliação
        div = Json({"motivo": "visão 11 ≠ ERP 12"}) if recon == "DIVERGENT" else None
        cur.execute("INSERT INTO vps_recon.vps_reconciliation(tag_id,erp_doc,status,divergence) VALUES (%s,%s,%s,%s)",
                    (op, f"ERP-{opk}", recon, div))

        # APS — cronograma plano × real
        ps = BASE + timedelta(hours=i * 4)
        for pidx, ph in enumerate(PHASES):
            run = SLA_H[ph] * 60; pe = ps + timedelta(minutes=run + 15)
            done = pidx < progress
            a_start = ps if done else None
            a_end = ps + timedelta(minutes=int(run * (0.6 if i % 2 else 0.9))) if done else None
            cur.execute("INSERT INTO vps_aps.glx_fact_vps_schedule(scenario_id,tag_id,operation,resource_key,planned_start,planned_end,setup_min,run_min,priority,rule_used,actual_start,actual_end) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        ("base", op, ph, RES[pidx % len(RES)], ps, pe, 15, run, i, "prioridade", a_start, a_end))
            ps = pe

        # staging / de-para (rastreabilidade da migração)
        cur.execute("INSERT INTO vps_stg.stg_legacy_order(legacy_key,segment,entity_type,natural_key,client_key,item_key,qty,status_legacy,open_flag,due_date,batch_id) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (f"SAP-{opk}", SEG, "OP", opk, client, item, 12, "RELEASED", state not in ("COMPLETED", "ARCHIVED"), (BASE + timedelta(days=20)).date(), batch))
        cur.execute("INSERT INTO vps_stg.depara_tagid(legacy_key,source,tag_id,batch_id) VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                    (f"SAP-{opk}", "SAP_B1", op, batch))

    # gold fact_pending (espelho)
    cur.execute("INSERT INTO glx.glx_fact_vps_pending(pending_id,tag_id,is_blocking,aging_hours,hourly_cost) "
                "SELECT pending_id,tag_id,is_blocking,aging_hours,hourly_cost FROM vps_proj.vps_pending")

    # ── PLANEJAMENTO (vps_plan) — projeto rege; card = OP liberada (vínculo via linhagem) ──
    cur.execute("INSERT INTO vps_plan.project_calendar(name,work_days,shift_start,shift_end) VALUES ('Padrão T1',ARRAY[1,2,3,4,5],'06:00','14:00') RETURNING calendar_id")
    cal = cur.fetchone()[0]
    cur.execute("SELECT natural_key, tag_id FROM vps_proj.vps_dim_tag WHERE entity_type='PROJ' ORDER BY natural_key")
    projmap, wbsmap = {}, {}
    for nk, ptag in cur.fetchall():
        cur.execute("""INSERT INTO vps_plan.project(code,name,segment,template_id,client_key,calendar_id,resource_pool,state,planned_start,owner,tag_id)
                       VALUES (%s,%s,'PANEL','PANEL_ETO_V1','COOP-DEMO',%s,ARRAY['res_cel-mont-01','res_pick-01'],'IN_EXECUTION',%s,'Projects',%s) RETURNING project_id""",
                    (nk, f"Projeto {nk}", cal, BASE.date(), ptag))
        pid = cur.fetchone()[0]; projmap[ptag] = pid
        cur.execute("INSERT INTO vps_plan.wbs(project_id,code,name,lvl) VALUES (%s,'1','Execução',1) RETURNING wbs_id", (pid,))
        wbsmap[pid] = cur.fetchone()[0]
    cur.execute("""SELECT l.parent_tag_id, l.child_tag_id, t.natural_key, t.current_state
                   FROM vps_core.vps_lineage l JOIN vps_proj.vps_dim_tag t ON t.tag_id=l.child_tag_id
                   WHERE t.entity_type='OP' ORDER BY t.natural_key""")
    proj_cards: dict[int, list[int]] = {}
    for ptag, otag, opk, state in cur.fetchall():
        pid = projmap.get(ptag)
        if not pid:
            continue
        cstate = "DONE" if state in ("COMPLETED", "ARCHIVED") else "IN_EXECUTION"
        cur.execute("""INSERT INTO vps_plan.card(project_id,wbs_id,code,title,card_type,planned_effort,resource_key,assigned_operator,priority,state,tag_id,pct_complete,actual_start)
                       VALUES (%s,%s,%s,%s,'TASK',40,'res_cel-mont-01','u123',100,%s,%s,%s,%s) RETURNING card_id""",
                    (pid, wbsmap[pid], opk, f"Card {opk}", cstate, otag, 100 if cstate == "DONE" else 50, BASE))
        proj_cards.setdefault(pid, []).append(cur.fetchone()[0])
    for pid, cids in proj_cards.items():
        for a, b in zip(cids, cids[1:]):
            cur.execute("INSERT INTO vps_plan.card_dependency(pred_card_id,succ_card_id,dep_type) VALUES (%s,%s,'FS') ON CONFLICT DO NOTHING", (a, b))
        cur.execute("INSERT INTO vps_plan.baseline(project_id,version,created_by) VALUES (%s,1,'seed') RETURNING baseline_id", (pid,))
        bid = cur.fetchone()[0]
        for cid in cids:
            cur.execute("INSERT INTO vps_plan.baseline_card(baseline_id,card_id,planned_effort) VALUES (%s,%s,40)", (bid, cid))

    conn.commit()

    # relatório
    counts = {}
    for sch in ("vps_core", "vps_md", "vps_proj", "vps_aps", "vps_recon", "glx", "vps_stg", "vps_plan"):
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=%s AND table_type='BASE TABLE'", (sch,))
        for (tn,) in cur.fetchall():
            if tn.startswith("vps_event_"):
                continue
            cur.execute(f"SELECT count(*) FROM {sch}.{tn}")
            counts[f"{sch}.{tn}"] = cur.fetchone()[0]
    cur.close(); conn.close()
    print("Seed OK · 10 OPs · contagens por tabela:")
    for k, v in counts.items():
        if v:
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
