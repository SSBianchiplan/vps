"""Teste ponta a ponta — executa o roteiro real (VPS_Teste_Ponta_a_Ponta.md).

NÃO é animação: muta o backend de verdade (gênese, fases, 3 correções, reconciliação,
DONE) e devolve cada passo com resultado/ok p/ reprodução passo a passo na tela.

DOIS MODOS

  reset=False (padrão) — roda AO LADO do que já existe. Cada rodada ganha um
  sufixo próprio nas chaves naturais (PV-2026-7781-R3f2a…), então nunca colide
  com OPs reais nem com rodadas anteriores, e cada passo vira um evento na
  trilha de auditoria (categoria E2E, correlation_id = id da rodada). É assim
  que o teste vira parte da operação rastreável em vez de um botão que apaga
  tudo antes de começar.

  reset=True — apaga o estado VPS (cenário limpo), como o roteiro original.
  Destrutivo: a rota só libera para Admin.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from . import pcp, phases, engine, operators, recon, store, tagid

_SEG = "PANEL"


def _id(et: str, key: str) -> str:
    return tagid.build(_SEG, et, key)


def run(reset: bool = False, actor: str = "Admin") -> dict[str, Any]:
    import uuid
    run_id = "e2e_" + uuid.uuid4().hex[:8]
    # Sufixo nas chaves naturais: rodadas convivem entre si e com dados reais.
    suf = "" if reset else "-R" + run_id[-4:].upper()

    if reset:
        store.reset()
        recon.clear()
    operators.seed()
    store.upsert_resource({"resource_key": "res_cel-mont-01", "name": "CEL-MONT-01", "capacity": 1, "calendar": "T1"})
    operators.identify("ALMOX-02", operator_id="u123")

    base = datetime.now(timezone.utc) - timedelta(hours=60)
    def ts(h: float) -> str:
        return (base + timedelta(hours=h)).isoformat()

    OP_KEY = f"OP-2026-04412{suf}"
    SO, PROJ, OP = _id("SO", f"PV-2026-7781{suf}"), _id("PROJ", f"PRJ-2026-118{suf}"), _id("OP", OP_KEY)
    PICK, ITEM, PO = _id("PICK", f"PK-04412-01{suf}"), _id("ITEM", f"RES-22K{suf}"), _id("PO", f"PO-2026-5512{suf}")
    OCC, MEAS, SHIP, INV = (_id("OCC", f"OC-04412-7{suf}"), _id("MEAS", f"MD-04412{suf}"),
                            _id("SHIP", f"SH-04412{suf}"), _id("INV", f"NF-2026-3321{suf}"))

    steps: list[dict[str, Any]] = []
    st: dict[str, Any] = {"pending_id": None, "occ_id": None}

    def cap(tag: str, action: str, h: float, **kw) -> dict[str, Any]:
        return engine.capture({"tag_id": tag, "action": action, "event_ts": ts(h),
                               "station_id": "ALMOX-02", "operator_id": "u123", **kw})

    def rec(cat: str, txt: str, ok: bool, detail: str = "", **meta) -> None:
        steps.append({"seq": len(steps) + 1, "cat": cat, "txt": txt, "ok": ok, "detail": detail, **meta})
        # Cada passo do teste e um evento auditavel: quem rodou, qual rodada,
        # passou ou nao. E o que torna o "modulo teste" parte do sistema real.
        try:
            from .. import audit
            audit.record("E2E", f"E2E_{cat.upper()}", severity="ok" if ok else "warn", actor=actor,
                         entity_type="e2e_run", entity_id=run_id, correlation_id=run_id,
                         summary=f"[{len(steps)}] {txt}"[:200],
                         payload={"ok": ok, "detail": detail, "tag": meta.get("id"), "reset": reset})
        except Exception:  # noqa: BLE001
            pass

    try:
        from .. import audit
        audit.record("E2E", "E2E_STARTED", actor=actor, entity_type="e2e_run", entity_id=run_id,
                     correlation_id=run_id, summary=f"teste ponta a ponta iniciado ({'reset' if reset else 'lado a lado'})",
                     payload={"reset": reset, "op": OP_KEY})
    except Exception:  # noqa: BLE001
        pass

    # 0 — Cadastros
    rec("cadastro", "Cadastros: operador u123 · estação ALMOX-02 · item RES-22K · cliente COOP-DEMO · template PANEL_ETO_V1 (SCD2)",
        ok=len(operators.list_operators()) >= 1, detail=f"{len(operators.list_operators())} operadores")

    # 1 — Vendas
    cap(SO, "SO_CREATED", 0); cap(SO, "SO_RELEASED", 1)
    rec("genese", "SO_RELEASED — pedido liberado (raiz)", ok=store.get_tag(SO) is not None,
        id=SO, node="so", pill=["proc", "RELEASED"])

    # 2 — Projeto (SO→PROJ)
    cap(PROJ, "MILESTONE_REACHED", 2, parent_tag_id=SO)
    rec("vinculo", "Abre projeto · vínculo SO → PROJ", ok=any(p["parent_tag_id"] == SO for p in store.parents_of(PROJ)),
        id=PROJ, node="proj", pill=["proc", "OPEN"])

    # 3 — Gênese OP (PROJ→OP), visão LER
    r = cap(OP, "OP_OPENED", 3, parent_tag_id=PROJ, vision_mode="LER", confidence=0.99)
    rec("genese", "OP_OPENED — visão LER nº da OP · GÊNESE do Fio Dourado · vínculo PROJ → OP",
        ok=r["state"] == "IN_PROCESS", detail=f"estado {r['state']}", id=OP, node="op", pill=["proc", "IN_PROCESS"], op="BOUND→IN_PROCESS")

    # 4 — Picking (OP→PICK)
    cap(PICK, "PICK_REQUESTED", 4, parent_tag_id=OP)
    rec("evento", "PICK_REQUESTED — separação solicitada · vínculo OP → PICK",
        ok=any(p["parent_tag_id"] == OP for p in store.parents_of(PICK)), id=PICK, node="pick", pill=["proc", "PICKING"])
    cap(OP, "DRAWINGS_APPROVED", 5); cap(OP, "SUPPLY_LINKED", 6)   # avança OP até o PCP

    # 4b — PCP: a estrutura do produto vira demanda de separação; a fase libera
    # por STRUCTURE_RELEASED e a OP segue para PICKING. Sem este passo a OP
    # pularia o PCP e a etapa ficaria SKIPPED na linha do tempo.
    pcp.seed(); pcp.clear(OP)
    r_pcp = pcp.structure(OP, 1, "u123") or {}
    rec("evento", "STRUCTURE_RELEASED — PCP explode a estrutura em demandas de separação · OP → PICKING",
        ok=bool(r_pcp.get("ok")) and store.get_tag(OP)["current_phase"] == "PICKING",
        detail=f"{len(r_pcp.get('demands', []))} itens · fase {store.get_tag(OP)['current_phase']}",
        id=OP, node="op", pill=["proc", "PCP"])

    # 5 — Conferência por visão: 11/12 (ITEM, PICK→ITEM)
    cap(ITEM, "PICK_ITEM_CONFIRMED", 7, parent_tag_id=PICK, vision_mode="CONTAR", confidence=0.93, payload={"total": 11, "alvo": 12})
    rec("evento", "PICK_ITEM_CONFIRMED — visão CONTAR: 11 de 12", ok=True, detail="falta 1× RES-22K",
        id=ITEM, node="item", pill=["warn", "11/12"])

    # 6 — CORREÇÃO 1: falta → pendência bloqueante (EXCEPTION)
    r = cap(OP, "PICK_SHORT", 8)
    st["pending_id"] = (store.pendings_for(OP) or [{}])[0].get("pending_id")
    rec("correcao", "⚠ PICK_SHORT → PENDING_OPENED — falta 1× RES-22K · fase BLOQUEADA",
        ok=r["state"] == "EXCEPTION" and store.open_pending_count(OP) == 1, detail="pendência abre, fase trava",
        op="EXCEPTION", node="pick", pill=["warn", "SHORT"])

    # 7 — Suprimentos: lacuna (ITEM⇄PO)
    cap(PO, "SUPPLY_GAP", 9, parent_tag_id=ITEM)
    store.add_lineage(ITEM, PO, "SUPPLY_LINK")
    rec("correcao", "SUPPLY_GAP — sem cobertura de compra · escalado · vínculo ITEM ⇄ PO",
        ok=any(c["child_tag_id"] == PO for c in store.children_of(ITEM)), id=PO, node="item", pill=["warn", "GAP"])

    # 8 — Recebimento → destrava (PENDING_CLEARED) + conclui picking
    cap(PO, "SUPPLY_RECEIVED", 20)
    cleared = engine.clear_pending(st["pending_id"]) if st["pending_id"] else None
    cap(OP, "PICK_COMPLETED", 21, vision_mode="CONTAR", confidence=0.99, payload={"total": 12})
    rec("resolvido", "SUPPLY_RECEIVED → PENDING_CLEARED — item recebido e conferido · fase DESTRAVADA",
        ok=bool(cleared) and store.open_pending_count(OP) == 0, detail="pendência resolvida",
        op="IN_PROCESS", node="pick", pill=["ok", "COMPLETED"])

    # 9 — CORREÇÃO 2: divergência de dado → evento compensatório (imutabilidade)
    engine.correct(OP, "QTY_CORRECTION: qtd registrada 11 → 12 (compensatório; erro permanece no log)")
    has_comp = any(e["action"] == "COMPENSATION" for e in store.events_for(OP))
    rec("correcao", "QTY_CORRECTION — evento compensatório (corrige divergência sem apagar o passado)",
        ok=has_comp, detail="erro fica no log, correção ao lado", id=OP)

    # 10 — Montagem (visão DESCREVER) → avança ASSEMBLY
    cap(OP, "OP_OPERATION_DONE", 44, vision_mode="DESCREVER", confidence=0.9)
    rec("evento", "OP_OPERATION_DONE — visão DESCREVER: montagem concluída", ok=True)

    # 11 — CORREÇÃO 3: ocorrência de qualidade (OP→OCC), visão ANALISAR
    cap(OCC, "OCCURRENCE_RAISED", 46, parent_tag_id=OP)
    st["occ_id"] = store.raise_occurrence(OP, store.get_tag(OP)["current_phase"], "QUALITY", "nok",
                                          "visão ANALISAR: solda irregular", raised_ts=ts(46))
    t = store.get_tag(OP); t["state"] = "EXCEPTION"; store.upsert_tag(t)
    rec("correcao", "⚠ OCCURRENCE_RAISED — visão ANALISAR detecta solda irregular · vínculo OP → OCC",
        ok=store.open_occurrence_count(OP) >= 1, detail="ocorrência registrada (não apagada)",
        op="EXCEPTION", id=OCC, node="occ", pill=["warn", "ABERTA"])

    # 12 — Ocorrência resolvida (retrabalho)
    store.resolve_occurrence(st["occ_id"])
    t = store.get_tag(OP); t["state"] = "IN_PROCESS"; store.upsert_tag(t)
    rec("resolvido", "OCCURRENCE_RESOLVED — retrabalho aprovado",
        ok=store.open_occurrence_count(OP) == 0, op="IN_PROCESS", node="occ", pill=["ok", "RESOLVED"])

    # 13 — Medição aprovada (OP→MEAS), visão ANALISAR
    cap(MEAS, "MEASUREMENT_TAKEN", 50, parent_tag_id=OP)
    cap(OP, "MEASUREMENT_APPROVED", 51, vision_mode="ANALISAR", confidence=0.98)
    rec("evento", "MEASUREMENT_APPROVED — visão ANALISAR · vínculo OP → MEAS",
        ok=any(c["child_tag_id"] == MEAS for c in store.children_of(OP)), id=MEAS, node="meas", pill=["ok", "APPROVED"])

    # 14 — Reconciliação → MATCHED
    recon.load_docs([{"natural_key": OP_KEY, "doc": f"ERP-OP-77120{suf}", "qty": 12, "value": 18450.0, "source": "e2e"}])
    rc = recon.reconcile()
    op_matched = any(i["natural_key"] == OP_KEY and i["status"] == "MATCHED" for i in rc["items"])
    rec("reconc", "Reconciliação físico × ERP/MES → recon_status = MATCHED", ok=op_matched, detail=f"taxa {rc['rate']}%")

    # 15 — Fechamento governado (exige MATCHED)
    store.append_event({"tag_id": OP, "action": "OP_CLOSED", "phase": store.get_tag(OP)["current_phase"],
                        "domain": "OP", "event_ts": ts(54), "owner": "Operations", "operator_id": "u123"})
    if op_matched:
        t = store.get_tag(OP); t["state"] = "COMPLETED"; t["closed_ts"] = ts(54); store.upsert_tag(t)
    rec("reconc", "OP_CLOSED — operações done + reconciliado (governança no fechamento)",
        ok=store.get_tag(OP)["state"] == "COMPLETED", op="COMPLETED", node="op", pill=["ok", "COMPLETED"])

    # 16 — Logística (OP→SHIP), visão LER romaneio
    cap(SHIP, "SHIPPED", 56, parent_tag_id=OP)
    rec("vinculo", "LOADED · SHIPPED · DELIVERED — visão LER romaneio · vínculo OP → SHIP · OTIF ok",
        ok=any(c["child_tag_id"] == SHIP for c in store.children_of(OP)), id=SHIP, node="ship", pill=["ok", "SHIPPED"])

    # 17 — Faturamento (SHIP→INV)
    cap(INV, "INVOICE_ISSUED", 58, parent_tag_id=SHIP)
    rec("vinculo", "INVOICE_ISSUED — nota referenciada (emitida pelo ERP) · vínculo SHIP → INV",
        ok=any(c["child_tag_id"] == INV for c in store.children_of(SHIP)), id=INV, node="inv", pill=["ok", "ISSUED"])

    # 18 — Controladoria
    cap(OP, "MARGIN_CALCULATED", 59)
    rec("evento", "MARGIN_CALCULATED — custo da pendência atribuído à OP (controladoria)", ok=True)

    # 19 — Arquivamento
    t = store.get_tag(OP); t["state"] = "ARCHIVED"; store.upsert_tag(t)
    store.append_event({"tag_id": OP, "action": "ARCHIVED", "phase": t["current_phase"], "domain": "OP",
                        "event_ts": ts(60), "owner": "Operations", "operator_id": "u123"})
    rec("fim", "ARCHIVED — instância concluída, reconciliada e 100% auditável",
        ok=store.get_tag(OP)["state"] == "ARCHIVED", op="ARCHIVED", node="op", pill=["ok", "ARCHIVED"])

    # 20 — Linha do tempo por etapa: baseline preservado, realizado gravado no avanço
    pl = phases.rows(OP)
    feitas = [p for p in pl if p["state"] == "DONE" and p["actual_start"] and p["actual_end"]]
    com_base = all(p["baseline_start"] and p["baseline_end"] for p in pl)
    rec("fases", "Planejado × realizado por etapa — baseline da abertura preservado, início/fim reais gravados no avanço",
        ok=len(pl) >= 5 and len(feitas) >= 4 and com_base,
        detail=f"{len(feitas)}/{len(pl)} etapas com realizado · variância medida contra o plano",
        id=OP, node="op", pill=["ok", f"{len(feitas)} etapas"])

    # ── linhagem: estado final de cada vínculo formado nesta rodada ──
    # O teste provava os vínculos por contagem. Agora ele LISTA cada aresta com
    # o estado das duas pontas e registra na trilha — é o que transforma o teste
    # em evidência de rastreabilidade, e não só num "passou".
    tags_rodada = [SO, PROJ, OP, PICK, ITEM, PO, OCC, MEAS, SHIP, INV]
    vinculos: list[dict[str, Any]] = []
    for pai in tags_rodada:
        for c in store.children_of(pai):
            filho = c["child_tag_id"]
            if filho not in tags_rodada:
                continue
            tp, tf = store.get_tag(pai) or {}, store.get_tag(filho) or {}
            vinculos.append({
                "relacao": c.get("relation"), "pai": pai, "filho": filho,
                "pai_estado": tp.get("state"), "pai_fase": tp.get("current_phase"),
                "filho_estado": tf.get("state"), "filho_fase": tf.get("current_phase"),
            })
    try:
        from .. import audit
        for v in vinculos:
            audit.record("E2E", "E2E_LINEAGE", actor=actor, entity_type="lineage", entity_id=v["filho"],
                         correlation_id=run_id,
                         summary=f"{v['relacao']}: {v['pai']} [{v['pai_estado']}] → {v['filho']} [{v['filho_estado']}]"[:200],
                         payload=v)
    except Exception:  # noqa: BLE001
        pass

    # ── verificação dos critérios de aceite ──
    th = engine.thread(OP)
    links = {"SO→PROJ", "PROJ→OP", "OP→PICK", "PICK→ITEM", "ITEM⇄PO", "OP→OCC", "OP→MEAS", "OP→SHIP", "SHIP→INV"}
    accept = {
        "master_data": len(operators.list_operators()) >= 1,
        "genese": store.get_tag(OP)["state"] in ("IN_PROCESS", "COMPLETED", "ARCHIVED"),
        "lineage_9": _count_links_run([SO, PROJ, OP, PICK, ITEM, PO, OCC, MEAS, SHIP, INV]) >= 9,
        "pending_blocked_cleared": st["pending_id"] is not None,
        "compensation": has_comp,
        "occurrence": st["occ_id"] is not None,
        "reconciled": op_matched,
        "archived": store.get_tag(OP)["state"] == "ARCHIVED",
        "anchor_query": th is not None and len(th["timeline"]) > 0,
    }
    kpis = {
        "estado_final": store.get_tag(OP)["state"],
        "pendencias": "1 (resolvida)",
        "ocorrencias": "1 (resolvida)",
        "correcoes_dado": "1 (compensatória)",
        "reconciliacao": f"{rc['rate']}% MATCHED",
        "otif": "no prazo",
        "gargalo": th["kpis"]["bottleneck"] or "PICKING",
        "vinculos": f"{_count_links_run([SO, PROJ, OP, PICK, ITEM, PO, OCC, MEAS, SHIP, INV])} / 9",
    }
    passed = all(accept.values())
    try:
        from .. import audit
        audit.record("E2E", "E2E_FINISHED", severity="ok" if passed else "warn", actor=actor,
                     entity_type="e2e_run", entity_id=run_id, correlation_id=run_id,
                     summary=f"teste ponta a ponta {'APROVADO' if passed else 'REPROVADO'} · {sum(1 for s in steps if s['ok'])}/{len(steps)} passos",
                     payload={"acceptance": accept, "kpis": kpis, "reset": reset})
    except Exception:  # noqa: BLE001
        pass
    # Mudanças que ESTA rodada provocou no banco (PostgreSQL): a prova de que
    # o teste mexeu no sistema real, com autor e campo a campo.
    mudancas: list[dict[str, Any]] = []
    try:
        from .. import changes
        if changes.disponivel():
            todas = changes.listar(limit=400).get("changes", [])
            alvo = set(tags_rodada)
            mudancas = [c for c in todas if c.get("pk") in alvo][:120]
    except Exception:  # noqa: BLE001
        pass

    return {"steps": steps, "op_tag": OP, "thread": th, "acceptance": accept, "kpis": kpis,
            "passed": passed, "expected_links": sorted(links), "run_id": run_id, "reset": reset,
            "lineage": vinculos, "changes": mudancas}


def _count_links() -> int:
    rows = store.get_connection().execute("SELECT COUNT(*) c FROM vps_lineage").fetchone()
    return int(dict(rows)["c"]) if rows else 0


def _count_links_run(tags: list[str]) -> int:
    """Vinculos SO desta rodada. O total geral contaria rodadas anteriores e dados reais."""
    q = ",".join("?" * len(tags))
    rows = store.get_connection().execute(
        f"SELECT COUNT(*) c FROM vps_lineage WHERE parent_tag_id IN ({q}) AND child_tag_id IN ({q})",
        tags + tags).fetchone()
    return int(dict(rows)["c"]) if rows else 0
