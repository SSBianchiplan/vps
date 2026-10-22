"""Process Engine — avança a instância (Tag-ID) conforme o Process Template.

Cada evento de visão dispara uma transição; transição inválida vira ocorrência.
Implementa: resolve, capture (máquina de estados §5.3), board, thread (Fio Dourado),
KPIs CLD_ e seed de demonstração.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from . import store, tagid, templates
from . import guards
from . import phases as etapas   # log planejado x realizado por etapa

# máquina de estados §5.3
STATES = ["CAPTURED", "RESOLVED", "BOUND", "IN_PROCESS", "EXCEPTION", "COMPLETED", "ARCHIVED"]
DONE_STATES = ("COMPLETED", "ARCHIVED")


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _hours_since(ts: str | None) -> float:
    d = _parse_ts(ts)
    if not d:
        return 0.0
    return max(0.0, (datetime.now(timezone.utc) - d).total_seconds() / 3600.0)


def _phase_ids(template_id: str | None) -> list[str]:
    tpl = templates.get(template_id or "")
    return [p["id"] for p in tpl["phases"]] if tpl else []


def _phase_def(template_id: str | None, phase_id: str | None) -> dict[str, Any] | None:
    tpl = templates.get(template_id or "")
    if not tpl or not phase_id:
        return None
    return next((p for p in tpl["phases"] if p["id"] == phase_id), None)


def _phase_times(events: list[dict[str, Any]]) -> dict[str, float]:
    """Horas acumuladas por fase = soma dos deltas entre eventos consecutivos."""
    out: dict[str, float] = {}
    seq = [(e["phase"], _parse_ts(e["event_ts"])) for e in events if e.get("phase") and _parse_ts(e["event_ts"])]
    for i in range(len(seq) - 1):
        ph, t0 = seq[i]
        _, t1 = seq[i + 1]
        out[ph] = out.get(ph, 0.0) + max(0.0, (t1 - t0).total_seconds() / 3600.0)
    return out


# ── Ações disponíveis na estação (o que registrar ao ler) ────────────
def available_actions(tag_id: str) -> dict[str, Any]:
    """Ações válidas p/ a fase atual do Fio (o operador escolhe o que registrar)."""
    tag = store.get_tag(tag_id)
    parsed = tagid.parse(tag_id)
    if not tag:
        ga = templates.genesis_action(parsed.entity_type if parsed else "OP")
        return {"genesis": True, "state": None, "phase": None,
                "actions": [{"action": ga, "label": f"Abrir instância (gênese) · {ga}", "kind": "genesis"}]}
    phase = tag.get("current_phase")
    phdef = _phase_def(tag["template_id"], phase) or {}
    acts: list[dict[str, str]] = []
    for a in phdef.get("exit", []):
        acts.append({"action": a, "label": f"Concluir {phase} · {a}", "kind": "advance"})
    for a in phdef.get("blocking_on", []):
        acts.append({"action": a, "label": f"Registrar problema · {a}", "kind": "block"})
    vm = (phdef.get("vision") or {}).get("mode")
    if vm:
        act = "VISION_COUNT" if vm == "CONTAR" else "VISION_CHECK"
        acts.append({"action": act, "label": f"Verificação por visão ({vm})", "kind": "observe"})
    acts.append({"action": "OCCURRENCE_RAISED", "label": "Abrir ocorrência (desvio)", "kind": "occurrence"})
    acts.append({"action": "LER_SCAN", "label": "Apenas registrar leitura (carimbo da estação)", "kind": "observe"})
    return {"genesis": False, "state": tag["state"], "phase": phase, "actions": acts}


# ── RESOLUÇÃO ────────────────────────────────────────────────────────
def resolve(tag_id: str) -> dict[str, Any]:
    """Tag-ID → entidade de negócio + template + estado (cria mínimo se novo)."""
    parsed = tagid.parse(tag_id)
    existing = store.get_tag(tag_id)
    if existing:
        return {"tag_id": tag_id, "entity_type": existing["entity_type"],
                "natural_key": existing["natural_key"], "segment": existing["segment"],
                "template_id": existing["template_id"], "state": existing["state"], "known": True}
    if not parsed:
        return {"tag_id": tag_id, "known": False, "resolvable": False,
                "message": "Tag-ID fora do formato VPS:segment:entity:key:instance"}
    tpl = templates.resolve_template(parsed.segment, parsed.entity_type)
    return {"tag_id": tag_id, "entity_type": parsed.entity_type, "natural_key": parsed.natural_key,
            "segment": parsed.segment, "template_id": tpl, "state": "RESOLVED",
            "known": False, "resolvable": True}


def _ensure_tag(tag_id: str, event_ts: str, parent_tag_id: str | None = None) -> dict[str, Any]:
    """Gênese: cria a instância (CAPTURED→RESOLVED→BOUND) se não existir."""
    tag = store.get_tag(tag_id)
    if tag:
        return tag
    parsed = tagid.parse(tag_id)
    seg = parsed.segment if parsed else "GENERIC"
    et = parsed.entity_type if parsed else "OP"
    tpl = templates.resolve_template(seg, et)
    phases = _phase_ids(tpl)
    tag = {
        "tag_id": tag_id, "segment": seg,
        "entity_type": parsed.entity_type if parsed else "UNKNOWN",
        "natural_key": parsed.natural_key if parsed else tag_id,
        "instance": parsed.instance if parsed else "01",
        "state": "BOUND" if parsed else "CAPTURED",
        "template_id": tpl, "current_phase": phases[0] if phases else None,
        "parent_tag_id": parent_tag_id, "opened_ts": event_ts,
        "closed_ts": None, "last_event_ts": event_ts,
    }
    store.upsert_tag(tag)
    # O plano da instância nasce com ela: uma linha por fase, com o baseline
    # contado dos SLAs do template a partir de agora. A primeira fase já entra.
    etapas.seed(tag)
    if phases_ids := _phase_ids(tpl):
        etapas.entrar(tag_id, phases_ids[0], event_ts)
    return tag


# ── CAPTURE (ingestão + transição) ───────────────────────────────────
def capture(ev: dict[str, Any]) -> dict[str, Any]:
    tag_id = ev["tag_id"]
    event_ts = ev.get("event_ts") or store.now_iso()
    action = ev["action"]
    parent = ev.get("parent_tag_id")

    tag = _ensure_tag(tag_id, event_ts, parent)
    tpl_id = tag["template_id"]
    phases = _phase_ids(tpl_id)
    cur_phase = tag.get("current_phase")

    # linhagem: amarra ao pai (cria pai mínimo) e grava relação
    if parent and parent != tag_id:
        _ensure_tag(parent, event_ts)
        pp, cp = tagid.parse(parent), tagid.parse(tag_id)
        rel = f"{pp.entity_type}->{cp.entity_type}" if pp and cp else "REL"
        store.add_lineage(parent, tag_id, rel)
        tag["parent_tag_id"] = parent

    touched = templates.phase_for_action(tpl_id, action)
    phase = (touched or {}).get("id") or cur_phase
    domain = templates.domain_of(action)
    owner = ev.get("owner") or templates.owner_of(action)

    occ: list[str] = []
    pend: list[str] = []
    new_state = tag["state"] if tag["state"] != "BOUND" else "IN_PROCESS"
    new_phase = cur_phase
    closed_ts = tag.get("closed_ts")

    # verificação por visão: confiança abaixo do mínimo da fase → ocorrência
    vmin = (touched or {}).get("vision", {}).get("min_confidence")
    conf = ev.get("confidence")
    if vmin is not None and conf is not None and conf < vmin:
        occ.append(store.raise_occurrence(tag_id, phase, "LOW_CONFIDENCE", "alerta",
                   f"Confiança {conf:.2f} < mínimo {vmin} da fase {phase}", ev.get("image_uri"), raised_ts=event_ts))

    # 1) fecha o fluxo?
    if action in (templates.get(tpl_id) or {}).get("closes_on", []):
        new_state = "COMPLETED"
        new_phase = phases[-1] if phases else cur_phase
        closed_ts = event_ts
        store.clear_pendings(tag_id)
    # 2) ação bloqueante → pendência + EXCEPTION
    elif touched and action in touched.get("blocking_on", []):
        pend.append(store.open_pending(tag_id, phase, f"{action} em {phase}", blocking=True, opened_ts=event_ts))
        new_state = "EXCEPTION"
        new_phase = phase
    # 3) ação de saída de fase → avança p/ próxima, SE a fase cumpriu o que devia
    elif touched and action in touched.get("exit", []):
        # A ação de saída é uma DECLARAÇÃO ("terminei"); a guarda é a
        # verificação. Sem ela, uma OP sem estrutura nenhuma atravessava PCP,
        # separação, montagem e faturamento e fechava como concluída — medido.
        # Ver vps/guards.py.
        impedimento = guards.verificar(tag_id, touched.get("requires"))
        if impedimento:
            pend.append(store.open_pending(tag_id, phase, impedimento, blocking=True, opened_ts=event_ts))
            occ.append(store.raise_occurrence(
                tag_id, phase, "PHASE_PRECONDITION_UNMET", "nok",
                f"Saída de {phase} recusada: {impedimento}", raised_ts=event_ts))
            new_state = "EXCEPTION"
            new_phase = phase
        else:
            store.clear_pendings(tag_id, phase)
            idx = phases.index(phase) if phase in phases else -1
            cur_idx = phases.index(cur_phase) if cur_phase in phases else -1
            if idx >= 0 and idx < cur_idx:  # saída fora de ordem (fase anterior)
                occ.append(store.raise_occurrence(tag_id, phase, "INVALID_TRANSITION", "nok",
                           f"Saída de {phase} fora de ordem (atual: {cur_phase})", raised_ts=event_ts))
            new_phase = phases[idx + 1] if 0 <= idx < len(phases) - 1 else phase
            new_state = "IN_PROCESS"
    # 4) ação de entrada / progresso → fixa fase tocada
    elif touched:
        new_phase = phase
        new_state = "IN_PROCESS"

    # se não havia pendências bloqueantes abertas, sai de EXCEPTION
    if new_state == "IN_PROCESS" and store.open_pending_count(tag_id) > 0:
        new_state = "EXCEPTION"

    eid = store.append_event({**ev, "event_ts": event_ts, "phase": phase,
                              "domain": domain, "owner": owner})

    tag.update({"state": new_state, "current_phase": new_phase,
                "last_event_ts": event_ts, "closed_ts": closed_ts})
    store.upsert_tag(tag)

    # Realizado por etapa, gravado AGORA — não reconstruído depois. É o que
    # torna "quando entrou / quando saiu / quanto levou" um dado, e não uma
    # varredura do histórico a cada abertura de tela.
    if new_phase != cur_phase:
        etapas.avancar(tag_id, cur_phase, new_phase, event_ts, eid)
    if new_state == "COMPLETED":
        etapas.fechar(tag_id, event_ts)

    from .. import audit  # trilha unificada: captura VPS é rastreabilidade
    audit.record("VPS", str(action).upper(),
                 summary=f"{action} · {tag_id} → {new_phase} [{new_state}]",
                 severity="nok" if occ else "alerta" if pend else "info",
                 actor=ev.get("operator_id") or "sistema", source_id=ev.get("source_id"),
                 entity_type=tagid.parse(tag_id).entity_type if tagid.parse(tag_id) else "tag",
                 entity_id=tag_id, correlation_id=tag_id, event_ts=event_ts,
                 payload={"phase": phase, "domain": domain, "owner": owner,
                          "occurrences": occ, "pendings": pend, "confidence": conf})

    return {"event_id": eid, "tag_id": tag_id, "state": new_state, "phase": new_phase,
            "domain": domain, "owner": owner, "occurrences": occ, "pendings": pend}


# ── THREAD (Fio Dourado) ─────────────────────────────────────────────
def thread(tag_id: str) -> dict[str, Any] | None:
    tag = store.get_tag(tag_id)
    if not tag:
        return None
    events = store.events_for(tag_id)
    phase_times = _phase_times(events)
    tss = [_parse_ts(e["event_ts"]) for e in events if _parse_ts(e["event_ts"])]
    lead = 0.0
    g0 = _parse_ts(tag.get("opened_ts")) or (tss[0] if tss else None)
    g1 = _parse_ts(tag.get("closed_ts")) or (tss[-1] if tss else None)
    if g0 and g1:
        lead = max(0.0, (g1 - g0).total_seconds() / 3600.0)
    bottleneck = max(phase_times, key=phase_times.get) if phase_times else None

    return {
        "tag": tag,
        "timeline": events,
        "lineage": {"parents": store.parents_of(tag_id), "children": store.children_of(tag_id)},
        "pendencies": store.pendings_for(tag_id, open_only=True),
        "occurrences": store.occurrences_for(tag_id, open_only=False),
        "kpis": {"lead_time_h": round(lead, 1), "phase_times_h": {k: round(v, 1) for k, v in phase_times.items()},
                 "bottleneck": bottleneck, "events": len(events)},
        "phase_log": etapas.rows(tag_id),
        "plano": etapas.resumo(tag_id),
    }


# ── BOARD (Visual Planning Board) ────────────────────────────────────
def _risk_level(state: str, sla: float | None, aging: float, pendings: int) -> str:
    """Forecast de risco da fase: bloqueado > estourado > iminente > alerta > ok."""
    if state in DONE_STATES:
        return "done"
    if state == "EXCEPTION" or pendings > 0:
        return "blocked"
    if not sla:
        return "ok"
    eta = sla - aging
    if eta < 0:
        return "late"
    if eta < 0.25 * sla:
        return "high"      # vai estourar em breve
    if eta < 0.5 * sla:
        return "warn"
    return "ok"


# Ordem canônica das fases (ciclo de vida ponta a ponta, SPEC_VPS §8) — templates
# percorridos em ordem lógica de fluxo p/ o kanban sair sempre na sequência do processo.
_CANON_TEMPLATES = ["SO_OTC_V1", "PROJ_V1", "PANEL_ETO_V1", "GENERIC_V1", "FOOD_V1", "PHARMA_V1", "SHIP_V1"]


def _phase_entered_ts(tag: dict[str, Any]) -> str | None:
    """Instante em que a instância ENTROU na fase atual.

    Percorre a linha do tempo de trás para a frente: enquanto os eventos forem da
    fase atual, ainda estamos "dentro" dela; o primeiro evento de outra fase é a
    transição — o relógio da fase começa ali. Se todos os eventos são da fase
    atual, a fase começou na gênese (opened_ts).
    """
    cur = tag.get("current_phase")
    events = store.events_for(tag["tag_id"])
    entrada = None
    for e in reversed(events):
        ph = e.get("phase")
        if ph and ph != cur:
            return entrada or e.get("event_ts")
        entrada = e.get("event_ts")
    return tag.get("opened_ts") or entrada or tag.get("last_event_ts")


def _canonical_phases() -> list[str]:
    order: list[str] = []
    for tid in _CANON_TEMPLATES:
        for p in _phase_ids(tid):
            if p not in order:
                order.append(p)
    return order


def _columns_for(tags: list[dict[str, Any]]) -> list[str]:
    """Colunas na ORDEM CANÔNICA do processo (não na ordem de iteração das tags) + DONE."""
    present: set[str] = set()
    for t in tags:
        present.update(_phase_ids(t.get("template_id")))
    if not present:
        present.update(_phase_ids(templates.resolve_template("PANEL", "OP")))
    canon = _canonical_phases()
    cols = [p for p in canon if p in present]
    cols += [p for p in present if p not in cols]   # fases fora do canônico (segurança)
    cols.append("DONE")
    return cols


def board(segment: str | None = None, entity: str | None = None) -> dict[str, Any]:
    tags = store.all_tags()
    if entity:
        tags = [t for t in tags if (t.get("entity_type") or "").upper() == entity.upper()]
    if segment:
        tags = [t for t in tags if (t.get("segment") or "").upper() == segment.upper()]
    cols = _columns_for(tags)
    cards: list[dict[str, Any]] = []
    wip: dict[str, int] = {c: 0 for c in cols}
    alerts: list[dict[str, Any]] = []

    for t in tags:
        done = t["state"] in ("COMPLETED", "ARCHIVED")
        first = (_phase_ids(t.get("template_id")) or [cols[0]])[0]   # fase inicial do próprio template
        col = "DONE" if done else (t.get("current_phase") or first)
        if col not in wip:
            col = first if first in wip else cols[0]
        # "Tempo na fase" conta desde a ENTRADA na fase. Antes contava desde o
        # último evento: qualquer registro dentro da mesma fase zerava o relógio
        # e o SLA parecia cumprido sem a fase ter andado.
        aging = 0.0 if done else _hours_since(_phase_entered_ts(t))
        phdef = _phase_def(t["template_id"], t.get("current_phase"))
        sla = (phdef or {}).get("sla_hours")
        sla_status = "ok"
        if sla and not done:
            sla_status = "late" if aging > sla else "warn" if aging > 0.7 * sla else "ok"
        opc = store.open_pending_count(t["tag_id"])
        ooc = store.open_occurrence_count(t["tag_id"])
        eta = round(sla - aging, 1) if (sla and not done) else None      # horas até estourar o SLA (neg = estourado)
        risk = _risk_level(t["state"], sla, aging, opc)
        card = {
            "tag_id": t["tag_id"], "entity_type": t["entity_type"], "natural_key": t["natural_key"],
            "segment": t["segment"], "state": t["state"], "phase": col,
            "template_id": t.get("template_id"), "phases": _phase_ids(t.get("template_id")),
            "phase_entered_ts": None if done else _phase_entered_ts(t),
            "aging_h": round(aging, 1), "sla_h": sla, "sla_status": sla_status,
            "eta_breach_h": eta, "risk": risk, "pendings": opc, "occurrences": ooc,
            "plano": etapas.resumo(t["tag_id"]),
            "opened_ts": t.get("opened_ts"), "closed_ts": t.get("closed_ts"),
            "parent_tag_id": t.get("parent_tag_id"),
        }
        cards.append(card)
        wip[col] = wip.get(col, 0) + 1
        if risk in ("blocked", "late", "high"):
            alerts.append({"tag_id": t["tag_id"], "natural_key": t["natural_key"], "phase": col,
                           "reason": "EXCEPTION" if t["state"] == "EXCEPTION" else ("SLA_LATE" if risk == "late" else "RISCO"),
                           "risk": risk, "eta_breach_h": eta, "pendings": opc, "occurrences": ooc})

    active_wip = {c: n for c, n in wip.items() if c != "DONE"}
    bottleneck = max(active_wip, key=active_wip.get) if active_wip and max(active_wip.values()) > 0 else None
    return {"columns": cols, "cards": cards, "wip": wip, "bottleneck": bottleneck,
            "alerts": alerts, "total": len(tags)}


# ── KPIs (CLD_) ──────────────────────────────────────────────────────
def kpis() -> dict[str, Any]:
    from ..config import get_settings
    s = get_settings()
    cph = s.vps_pending_cost_per_hour
    tags = store.all_tags(include_archived=True)
    events = store.recent_events(5000)

    lead_times: list[float] = []
    otif_total = otif_ok = adh_total = adh_ok = 0
    for t in tags:
        done = t["state"] in DONE_STATES
        g0, g1 = _parse_ts(t.get("opened_ts")), _parse_ts(t.get("closed_ts"))
        if g0 and g1:
            lt = (g1 - g0).total_seconds() / 3600.0
            lead_times.append(lt)
            slat = templates.sla_total(t["template_id"])
            if done and slat > 0:                       # OTIF: concluído dentro do SLA total
                otif_total += 1
                otif_ok += 1 if lt <= slat else 0
        for ph, hrs in _phase_times(store.events_for(t["tag_id"])).items():
            sla = (_phase_def(t["template_id"], ph) or {}).get("sla_hours")
            if sla:                                     # aderência de cronograma por fase
                adh_total += 1
                adh_ok += 1 if hrs <= sla else 0

    cost = sum(_hours_since(p["opened_ts"]) * cph for p in store.all_open_pendings())
    open_pend = sum(store.open_pending_count(t["tag_id"]) for t in tags)
    open_occ = sum(store.open_occurrence_count(t["tag_id"]) for t in tags)
    # Reconciliação é atributo da INSTÂNCIA (tag × documento ERP), não do evento:
    # contar eventos MATCHED sobre todos os eventos dava 7% num cockpit em que
    # a tela de reconciliação mostrava 100% das OPs casadas.
    tags_recon = {e["tag_id"] for e in events if e.get("recon_status") == "MATCHED"}
    tags_com_evento = {e["tag_id"] for e in events}
    vision_events = sum(1 for e in events if e.get("vision_mode"))
    return {
        "CLD_Thread_LeadTime_h": round(sum(lead_times) / len(lead_times), 1) if lead_times else None,
        "CLD_Active_Threads": sum(1 for t in tags if t["state"] not in DONE_STATES),
        "CLD_Completed_Threads": sum(1 for t in tags if t["state"] in DONE_STATES),
        "CLD_OTIF": round(100 * otif_ok / otif_total, 1) if otif_total else None,
        "CLD_Schedule_Adherence": round(100 * adh_ok / adh_total, 1) if adh_total else None,
        "CLD_Pending_Open": open_pend,
        "CLD_Occurrence_Open": open_occ,
        "CLD_Cost_of_Pendencies": round(cost, 2),
        "CLD_Currency": s.vps_currency,
        "CLD_Reconciliation_Rate": round(100 * len(tags_recon) / len(tags_com_evento), 1) if tags_com_evento else 0.0,
        "CLD_Vision_Coverage": round(100 * vision_events / len(events), 1) if events else 0.0,
        "CLD_Events_Total": len(events),
    }


# ── SEED (demonstração) ──────────────────────────────────────────────
# ── Inteligência preditiva (risco/forecast) ──────────────────────────
_RISK_RANK = {"blocked": 0, "late": 1, "high": 2, "warn": 3, "ok": 4, "done": 5}


def risks() -> dict[str, Any]:
    """Fios em risco ordenados por severidade (bloqueado→estouro iminente)."""
    b = board()
    risky = [c for c in b["cards"] if c["risk"] in ("blocked", "late", "high")]
    risky.sort(key=lambda c: (_RISK_RANK.get(c["risk"], 9), c["eta_breach_h"] if c["eta_breach_h"] is not None else 1e9))
    return {"risks": risky, "predicted_bottleneck": b["bottleneck"], "count": len(risky)}


# ── Ações de governança (cockpit operacional) ────────────────────────
def clear_pending(pending_id: str) -> dict[str, Any] | None:
    p = store.get_pending(pending_id)
    if not p:
        return None
    store.clear_pending_by_id(pending_id)
    tag = store.get_tag(p["tag_id"])
    if tag and tag["state"] == "EXCEPTION" and store.open_pending_count(p["tag_id"]) == 0:
        tag["state"] = "IN_PROCESS"           # sem mais bloqueios → volta a fluir
        store.upsert_tag(tag)
    return {"ok": True, "tag_id": p["tag_id"], "state": tag["state"] if tag else None}


def resolve_occurrence(occ_id: str) -> dict[str, Any]:
    return {"ok": store.resolve_occurrence(occ_id)}


def advance(tag_id: str, reason: str | None = None, actor: str | None = None) -> dict[str, Any] | None:
    """Empurra a ação de saída da fase atual (avanço manual pelo cockpit).

    `reason` é a justificativa do usuário e `actor` quem mandou — os dois vão
    para o payload do evento e para a trilha. Avanço manual sem autor era
    "cockpit" para todo mundo: ninguém sabia quem moveu o quê.
    """
    tag = store.get_tag(tag_id)
    if not tag:
        return None
    if tag["state"] in DONE_STATES:
        return {"ok": False, "message": "instância concluída — não avança"}
    if store.open_pending_count(tag_id) > 0:
        return {"ok": False, "message": "fase BLOQUEADA por pendência — resolva a pendência antes de avançar"}
    exits = (_phase_def(tag["template_id"], tag.get("current_phase")) or {}).get("exit", [])
    if not exits:
        return {"ok": False, "message": "fase sem ação de saída definida"}
    out = capture({"tag_id": tag_id, "action": exits[0], "event_ts": store.now_iso(),
                   "source_type": "MANUAL", "operator_id": actor or "cockpit",
                   "payload": {"manual": True, "reason": reason, "moved_by": actor}})
    return {"ok": True, **out}


def correct(tag_id: str, note: str, actor: str | None = None) -> dict[str, Any] | None:
    """Correção por evento COMPENSATÓRIO (imutabilidade §15) — auditável, não destrói."""
    tag = store.get_tag(tag_id)
    if not tag:
        return None
    eid = store.append_event({"tag_id": tag_id, "action": "COMPENSATION", "phase": tag.get("current_phase"),
                              "domain": "AUDIT", "event_ts": store.now_iso(), "source_type": "MANUAL",
                              "operator_id": actor or "cockpit", "payload": {"note": note}, "owner": "Quality"})
    from .. import audit
    audit.record("VPS", "COMPENSATION", actor=actor or "cockpit", entity_type="tag", entity_id=tag_id,
                 correlation_id=tag_id, summary=f"correção compensatória em {tag.get('natural_key')}: {note[:120]}",
                 payload={"note": note, "phase": tag.get("current_phase")})
    return {"ok": True, "event_id": eid}


def move(tag_id: str, to_phase: str, reason: str, actor: str | None = None) -> dict[str, Any] | None:
    """Move a instância para uma fase do kanban COM JUSTIFICATIVA (arrastar e soltar).

    Três casos, todos auditáveis e nenhum destrutivo:
      adiante   → dispara a ação de saída de cada fase intermediária, em ordem
                  (o Event Store fica consistente; pular >1 fase abre uma
                  ocorrência PHASE_SKIPPED para a qualidade olhar);
      DONE      → idem até a última fase, cuja saída fecha a instância;
      para trás → retrabalho: evento REWORK, ocorrência REWORK e a fase atual
                  volta. O passado não é apagado — a volta é um evento a mais.
    Bloqueada por pendência → recusa: a pendência precisa ser resolvida no Fio.
    """
    tag = store.get_tag(tag_id)
    if not tag:
        return None
    reason = (reason or "").strip()
    if len(reason) < 5:
        return {"ok": False, "message": "justificativa obrigatória (mínimo 5 caracteres)"}
    phases = _phase_ids(tag.get("template_id"))
    cur = tag.get("current_phase")
    if tag["state"] in DONE_STATES:
        return {"ok": False, "message": "instância concluída — reabra com uma correção compensatória, não movendo o card"}
    if to_phase != "DONE" and to_phase not in phases:
        # O kanban mostra a UNIÃO das fases de todos os templates em uso, então
        # existe coluna que não pertence a esta instância. Dizer só "não existe"
        # deixa o usuário sem saída: a recusa carrega para onde ELA pode ir.
        return {"ok": False, "phases": phases,
                "message": (f"'{to_phase}' não é fase do template {tag.get('template_id')} desta instância. "
                            f"Fases possíveis: {', '.join(phases)} ou DONE.")}
    if to_phase == cur:
        return {"ok": False, "message": "a instância já está nesta fase"}
    if store.open_pending_count(tag_id) > 0:
        return {"ok": False, "message": "fase BLOQUEADA por pendência — resolva a pendência no Fio antes de mover"}

    actor = actor or "cockpit"
    cur_idx = phases.index(cur) if cur in phases else 0
    to_idx = len(phases) if to_phase == "DONE" else phases.index(to_phase)
    payload = {"manual": True, "reason": reason, "moved_by": actor, "from": cur, "to": to_phase, "via": "kanban"}
    fired: list[str] = []
    occ: list[str] = []

    if to_idx > cur_idx:
        # adiante: saída de cada fase entre a atual e o destino
        for i in range(cur_idx, to_idx):
            exits = (_phase_def(tag["template_id"], phases[i]) or {}).get("exit", [])
            if not exits:
                return {"ok": False, "message": f"fase {phases[i]} sem ação de saída — não dá para atravessá-la pelo kanban",
                        "fired": fired}
            capture({"tag_id": tag_id, "action": exits[0], "event_ts": store.now_iso(),
                     "source_type": "MANUAL", "operator_id": actor, "payload": payload})
            fired.append(exits[0])
        if to_idx - cur_idx > 1:
            occ.append(store.raise_occurrence(tag_id, to_phase if to_phase != "DONE" else phases[-1], "PHASE_SKIPPED", "alerta",
                       f"{to_idx - cur_idx - 1} fase(s) puladas no kanban por {actor}: {reason[:120]}"))
    else:
        # para trás: retrabalho — evento + ocorrência, fase volta, passado fica
        store.append_event({"tag_id": tag_id, "action": "REWORK", "phase": to_phase, "domain": "AUDIT",
                            "event_ts": store.now_iso(), "source_type": "MANUAL", "operator_id": actor,
                            "payload": payload, "owner": "Quality"})
        occ.append(store.raise_occurrence(tag_id, to_phase, "REWORK", "alerta",
                   f"retorno de {cur} para {to_phase} por {actor}: {reason[:120]}"))
        t = store.get_tag(tag_id)
        t["current_phase"] = to_phase
        t["state"] = "EXCEPTION" if store.open_pending_count(tag_id) > 0 else "IN_PROCESS"
        t["last_event_ts"] = store.now_iso()
        store.upsert_tag(t)
        etapas.retroceder(tag_id, cur, to_phase, t["last_event_ts"])
        fired.append("REWORK")

    novo = store.get_tag(tag_id)
    from .. import audit
    audit.record("VPS", "CARD_MOVED", actor=actor, entity_type="tag", entity_id=tag_id, correlation_id=tag_id,
                 severity="alerta" if occ else "info",
                 summary=f"{novo.get('natural_key')}: {cur} → {to_phase} por {actor} — {reason[:100]}",
                 payload={**payload, "fired": fired, "occurrences": occ, "state": novo.get("state")})
    return {"ok": True, "tag_id": tag_id, "from": cur, "to": to_phase, "state": novo.get("state"),
            "phase": novo.get("current_phase"), "fired": fired, "occurrences": occ}


def seed(reset: bool = False) -> dict[str, Any]:
    """Gera um Fio Dourado de exemplo (segmento PANEL) p/ popular o cockpit."""
    if reset:
        store.reset()
    base = datetime.now(timezone.utc) - timedelta(hours=60)

    def ts(h: float) -> str:
        return (base + timedelta(hours=h)).isoformat()

    so = tagid.build("PANEL", "SO", "SO-2026-7781")
    proj = tagid.build("PANEL", "PROJ", "PRJ-2026-118")
    n = 0

    def cap(tag, action, h, **extra):
        nonlocal n
        n += 1
        capture({"tag_id": tag, "action": action, "event_ts": ts(h), **extra})

    cap(so, "SO_CREATED", 0)
    cap(so, "SO_RELEASED", 1)
    cap(proj, "MILESTONE_REACHED", 2, parent_tag_id=so)

    # 3 OPs em fases diferentes (board com colunas povoadas)
    flows = [
        ("OP-2026-04412", [("OP_OPENED", 3, {"vision_mode": "LER", "confidence": 0.99}),
                           ("DRAWINGS_APPROVED", 6), ("SUPPLY_LINKED", 12),
                           ("PICK_COMPLETED", 20, {"vision_mode": "CONTAR", "confidence": 0.97}),
                           ("OP_OPERATION_DONE", 44, {"vision_mode": "DESCREVER", "confidence": 0.9}),
                           ("MEASUREMENT_APPROVED", 50, {"vision_mode": "ANALISAR", "confidence": 0.95}),
                           ("SHIPPED", 56), ("INVOICE_ISSUED", 58)]),
        ("OP-2026-04413", [("OP_OPENED", 4, {"vision_mode": "LER", "confidence": 0.98}),
                           ("DRAWINGS_APPROVED", 8), ("SUPPLY_LINKED", 16),
                           ("PICK_SHORT", 24, {"vision_mode": "CONTAR", "confidence": 0.93,
                                               "payload": {"sku": "RES-22K", "faltam": 5}})]),
        ("OP-2026-04414", [("OP_OPENED", 6, {"vision_mode": "LER", "confidence": 0.99}),
                           ("DRAWINGS_APPROVED", 10), ("SUPPLY_LINKED", 20),
                           ("PICK_COMPLETED", 30, {"vision_mode": "CONTAR", "confidence": 0.96,
                                                   "payload": {"total": 10, "contagens": {"resistor": 10}}})]),
    ]
    for key, steps in flows:
        op = tagid.build("PANEL", "OP", key)
        for action, h, *extra in steps:
            cap(op, action, h, parent_tag_id=proj if action == "OP_OPENED" else None, **(extra[0] if extra else {}))

    return {"seeded_events": n, "tags": len(store.all_tags(include_archived=True))}
