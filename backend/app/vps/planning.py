"""Planejamento — Projetos e Cards (VPS_Projetos_Planejamento_Cards.md).

O Projeto REGE: habilita planejar cards. Card é plano; ao liberar vira Tag-ID
(gênese) e a visão realimenta o avanço. CPM orienta, APS (capacidade finita)
sequencia. Vínculos: espinha VPS (linhagem/eventos), APS (vps_schedule), Operadores.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from . import engine, store, tagid, templates

_PROJ_STATES = ("DRAFT", "PLANNING", "BASELINED", "IN_EXECUTION", "CLOSING", "CLOSED")
_CARD_STATES = ("PLANNED", "SCHEDULED", "RELEASED", "IN_EXECUTION", "BLOCKED", "DONE")


def _conn():
    return store.get_connection()


def _rows(sql: str, params=()) -> list[dict[str, Any]]:
    return [dict(r) for r in _conn().execute(sql, params).fetchall()]


def _row(sql: str, params=()) -> dict[str, Any] | None:
    r = _conn().execute(sql, params).fetchone()
    return dict(r) if r else None


def _parse(ts: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else None
    except (ValueError, AttributeError):
        return None


# ── PROJETO ──────────────────────────────────────────────────────────
def _evento(project_id: str, action: str, payload: dict[str, Any]) -> None:
    # Toda mutacao de planejamento vira evento no Event Store E na trilha de
    # auditoria. Antes so criacao de projeto, baseline e release geravam evento;
    # WBS, card, dependencia, atribuicao e cronograma mudavam o banco em
    # silencio — um plano podia ser reescrito sem deixar rastro.
    # Best-effort: nunca derruba a mutacao.
    try:
        proj = get_project(project_id)
        tag = (proj or {}).get("tag_id")
        if tag:
            store.append_event({"tag_id": tag, "action": action, "phase": "PLANNING", "domain": "PROJECT",
                                "event_ts": store.now_iso(), "owner": "Projects", "payload": payload})
        from .. import audit
        ref = payload.get("code") or payload.get("card_id") or ""
        audit.record("VPS", action, actor="planning", entity_type="project", entity_id=project_id,
                     summary=f"{action} · {(proj or {}).get('code', project_id)} · {ref}".rstrip(" ·"),
                     payload=payload, correlation_id=tag)
    except Exception:  # noqa: BLE001
        pass


def create_project(d: dict[str, Any]) -> dict[str, Any]:
    code = d["code"].strip()
    seg = (d.get("segment") or "PANEL").upper()
    tpl = d.get("template_id") or templates.resolve_template(seg, "OP")
    pid = store.new_id("prj")
    proj_tag = tagid.build(seg, "PROJ", code)
    _conn().execute(
        """INSERT INTO vps_project(project_id,code,name,segment,template_id,client_key,resource_pool,
             state,planned_start,planned_end,owner,tag_id,created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (pid, code, d.get("name", code), seg, tpl, d.get("client_key"), d.get("resource_pool"),
         "PLANNING", d.get("planned_start"), d.get("planned_end"), d.get("owner", "Projects"),
         proj_tag, store.now_iso()))
    # nó PROJ na espinha (linhagem/eventos) — o projeto vira parte do Fio
    store.upsert_tag({"tag_id": proj_tag, "segment": seg, "entity_type": "PROJ", "natural_key": code,
                      "instance": "01", "state": "IN_PROCESS", "template_id": "PROJ_V1",
                      "current_phase": "PLANNING", "parent_tag_id": None, "opened_ts": store.now_iso(),
                      "last_event_ts": store.now_iso()})
    store.append_event({"tag_id": proj_tag, "action": "PROJECT_CREATED", "phase": "PLANNING",
                        "domain": "PROJECT", "event_ts": store.now_iso(), "owner": d.get("owner", "Projects"),
                        "payload": {"name": d.get("name"), "segment": seg}})
    return get_project(pid)  # type: ignore[return-value]


def list_projects() -> list[dict[str, Any]]:
    out = _rows("SELECT * FROM vps_project ORDER BY created_at DESC")
    for p in out:
        # pelo NOME da coluna: a linha do psycopg é um dicionário e não aceita
        # índice — `fetchone()[0]` funcionava no SQLite e virou KeyError no PG.
        p["cards"] = int(dict(_conn().execute("SELECT COUNT(*) AS c FROM vps_card WHERE project_id=?", (p["project_id"],)).fetchone())["c"])
    return out


def get_project(project_id: str) -> dict[str, Any] | None:
    return _row("SELECT * FROM vps_project WHERE project_id=?", (project_id,))


def set_project_state(project_id: str, state: str) -> None:
    if state in _PROJ_STATES:
        _conn().execute("UPDATE vps_project SET state=? WHERE project_id=?", (state, project_id))


# ── WBS ──────────────────────────────────────────────────────────────
def add_wbs(project_id: str, code: str, name: str, parent: str | None = None, lvl: int = 1) -> dict[str, Any]:
    wid = store.new_id("wbs")
    _conn().execute("INSERT INTO vps_wbs(wbs_id,project_id,parent_wbs_id,code,name,lvl) VALUES (?,?,?,?,?,?)",
                    (wid, project_id, parent, code, name, lvl))
    _evento(project_id, "WBS_ADDED", {"wbs_id": wid, "code": code, "name": name, "lvl": lvl})
    return {"wbs_id": wid, "project_id": project_id, "code": code, "name": name, "lvl": lvl}


def list_wbs(project_id: str) -> list[dict[str, Any]]:
    return _rows("SELECT * FROM vps_wbs WHERE project_id=? ORDER BY code", (project_id,))


# ── CARD ─────────────────────────────────────────────────────────────
def add_card(project_id: str, d: dict[str, Any]) -> dict[str, Any]:
    cid = store.new_id("card")
    _conn().execute(
        """INSERT INTO vps_card(card_id,project_id,wbs_id,code,title,card_type,planned_effort,resource_key,
             assigned_operator,priority,state,pct_complete,created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (cid, project_id, d.get("wbs_id"), d["code"], d.get("title", d["code"]), d.get("card_type", "TASK"),
         float(d.get("planned_effort", 8)), d.get("resource_key"), d.get("assigned_operator"),
         int(d.get("priority", 100)), "PLANNED", 0, store.now_iso()))
    _evento(project_id, "CARD_CREATED", {"card_id": cid, "code": d["code"], "card_type": d.get("card_type", "TASK"),
                                         "planned_effort": float(d.get("planned_effort", 8))})
    return get_card(cid)  # type: ignore[return-value]


def list_cards(project_id: str) -> list[dict[str, Any]]:
    return _rows("SELECT * FROM vps_card WHERE project_id=? ORDER BY priority, code", (project_id,))


def get_card(card_id: str) -> dict[str, Any] | None:
    return _row("SELECT * FROM vps_card WHERE card_id=?", (card_id,))


def assign_card(card_id: str, operator: str | None, resource: str | None) -> dict[str, Any] | None:
    c = get_card(card_id)
    if not c:
        return None
    _conn().execute("UPDATE vps_card SET assigned_operator=COALESCE(?,assigned_operator), resource_key=COALESCE(?,resource_key) WHERE card_id=?",
                    (operator, resource, card_id))
    _evento(c["project_id"], "CARD_ASSIGNED", {"card_id": card_id, "code": c["code"], "operator": operator, "resource": resource})
    return get_card(card_id)


# ── DEPENDÊNCIAS ─────────────────────────────────────────────────────
def add_dependency(project_id: str, pred: str, succ: str, dep_type: str = "FS", lag_min: int = 0) -> dict[str, Any] | None:
    if pred == succ:
        return None
    did = store.new_id("dep")
    _conn().execute("INSERT INTO vps_card_dep(dep_id,project_id,pred_card_id,succ_card_id,dep_type,lag_min) VALUES (?,?,?,?,?,?)",
                    (did, project_id, pred, succ, dep_type, lag_min))
    _evento(project_id, "DEPENDENCY_ADDED", {"dep_id": did, "pred": pred, "succ": succ, "type": dep_type, "lag_min": lag_min})
    return {"dep_id": did, "pred_card_id": pred, "succ_card_id": succ, "dep_type": dep_type, "lag_min": lag_min}


def list_deps(project_id: str) -> list[dict[str, Any]]:
    return _rows("SELECT * FROM vps_card_dep WHERE project_id=?", (project_id,))


# ── CPM + capacidade finita (planejamento avançado) ──────────────────
def _cpm(cards: list[dict[str, Any]], deps: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """ES/EF/LS/LF/slack em horas (capacidade infinita) — orienta o caminho crítico."""
    dur = {c["card_id"]: float(c["planned_effort"] or 1) for c in cards}
    ids = list(dur)
    es = {i: 0.0 for i in ids}
    # forward pass por relaxação (FS/SS/FF/SF + lag)
    for _ in range(len(ids) + 1):
        changed = False
        for d in deps:
            p, s = d["pred_card_id"], d["succ_card_id"]
            if p not in dur or s not in dur:
                continue
            lag = (d.get("lag_min") or 0) / 60.0
            t = d["dep_type"]
            req = es[p] + dur[p] + lag if t in ("FS", "FF") else es[p] + lag  # SS/SF a partir do start do pred
            if t == "FF":
                req -= dur[s]
            if req > es[s] + 1e-9:
                es[s] = req; changed = True
        if not changed:
            break
    ef = {i: es[i] + dur[i] for i in ids}
    proj_end = max(ef.values(), default=0.0)
    lf = {i: proj_end for i in ids}
    for _ in range(len(ids) + 1):
        changed = False
        for d in deps:
            p, s = d["pred_card_id"], d["succ_card_id"]
            if p not in dur or s not in dur:
                continue
            lag = (d.get("lag_min") or 0) / 60.0
            cand = lf[s] - dur[s] - lag
            if cand < lf[p] - 1e-9:
                lf[p] = cand; changed = True
        if not changed:
            break
    ls = {i: lf[i] - dur[i] for i in ids}
    return {i: {"es": es[i], "ef": ef[i], "ls": ls[i], "lf": lf[i], "slack": round(ls[i] - es[i], 2)} for i in ids}


def schedule(project_id: str, respeitar_janelas: bool = True) -> dict[str, Any]:
    """CPM → capacidade finita por recurso → grava datas + estado SCHEDULED + vps_schedule.

    RESPEITAR O QUE JÁ FOI PLANEJADO

    Antes o agendamento recalculava TODAS as datas a partir do início do projeto
    e sobrescrevia o que houvesse. Quem abrisse uma OP com entrega combinada
    (14/09 → 21/09, digitada no assistente) via essas datas desaparecerem no
    primeiro "Agendar" — trocadas por `agora + esforço`, porque o projeto nem
    janela própria tinha. O planejador perdia o trabalho sem aviso.

    Agora um card com janela explícita é uma ÂNCORA: entra no cálculo como data
    dada, não como resultado. O CPM e a capacidade finita continuam valendo para
    os demais, que é o que o agendamento existe para resolver. Para replanejar
    tudo do zero — o "reagendar de verdade" —, chame com
    `respeitar_janelas=False`.
    """
    proj = get_project(project_id)
    if not proj:
        return {"ok": False}
    cards = [c for c in list_cards(project_id) if c["state"] in ("PLANNED", "SCHEDULED")]
    deps = list_deps(project_id)
    cpm = _cpm(cards, deps)
    # Sem janela no projeto, a base era `agora` — e todo o cronograma nascia
    # colado no instante do clique. A primeira data já planejada é uma origem
    # muito melhor: é a intenção de quem planejou.
    inicios = [d for d in (_parse(c.get("planned_start")) for c in cards) if d]
    base = (_parse(proj.get("planned_start"))
            or (min(inicios) if respeitar_janelas and inicios else None)
            or datetime.now(timezone.utc).replace(microsecond=0))
    res_free: dict[str, float] = {}
    sched_rows: list[dict[str, Any]] = []
    ancorados = 0
    for c in sorted(cards, key=lambda x: (cpm.get(x["card_id"], {}).get("es", 0), x["priority"])):
        cid = c["card_id"]; dur = float(c["planned_effort"] or 1)
        rk = c.get("resource_key") or "—"
        j_ini, j_fim = _parse(c.get("planned_start")), _parse(c.get("planned_end"))
        if respeitar_janelas and j_ini and j_fim:
            ps, pe = j_ini, j_fim
            ancorados += 1
            # O recurso segue ocupado pela âncora: senão o próximo card seria
            # agendado por cima dela e a capacidade finita viraria ficção.
            res_free[rk] = max(res_free.get(rk, 0.0), (pe - base).total_seconds() / 3600.0)
        else:
            start_h = max(cpm.get(cid, {}).get("es", 0.0), res_free.get(rk, 0.0))  # finito: respeita CPM + recurso livre
            end_h = start_h + dur
            res_free[rk] = end_h
            ps, pe = base + timedelta(hours=start_h), base + timedelta(hours=end_h)
        _conn().execute("UPDATE vps_card SET planned_start=?, planned_end=?, state=CASE WHEN state='PLANNED' THEN 'SCHEDULED' ELSE state END WHERE card_id=?",
                        (ps.isoformat(), pe.isoformat(), cid))
        sched_rows.append({"schedule_id": store.new_id("sch"), "tag_id": c.get("tag_id") or proj["tag_id"],
                           "operation": c["code"], "resource_key": rk, "seq": len(sched_rows) + 1,
                           "planned_start": ps.isoformat(), "planned_end": pe.isoformat(), "setup_min": 0,
                           "run_min": int(dur * 60), "priority": c["priority"], "rule_used": "cpm+finite",
                           "actual_start": c.get("actual_start"), "actual_end": c.get("actual_end"), "variance_min": None})
    store.save_schedule(f"proj:{proj['code']}", sched_rows)   # vínculo c/ APS (cenário do projeto)
    set_project_state(project_id, "PLANNING")
    janela = sincronizar_janela(project_id)
    criticos = [cid for cid, v in cpm.items() if v["slack"] <= 0.01]
    _evento(project_id, "PROJECT_SCHEDULED", {"scheduled": len(sched_rows), "critical": len(criticos),
                                              "ancorados": ancorados, "janela": janela,
                                              "aps_scenario": f"proj:{proj['code']}"})
    return {"ok": True, "scheduled": len(sched_rows), "critical": criticos,
            "ancorados": ancorados, "janela": janela}


def sincronizar_janela(project_id: str) -> dict[str, str | None]:
    """A janela do projeto é a envoltória das janelas dos seus cards.

    O projeto nascia com `planned_start`/`planned_end` nulos e assim ficava,
    mesmo depois de ter ordens com datas: a coluna existia e ninguém a
    preenchia. Isso não é só um campo em branco na tela — é o `schedule` sem
    origem, caindo em `agora`, e o portfólio sem como responder "quando este
    projeto entrega?" sem abrir card por card.

    Derivar em vez de pedir de novo: a data do projeto não é um dado
    independente, é o que suas ordens dizem. Perguntar duas vezes é convidar as
    duas respostas a divergirem.
    """
    linhas = _rows(
        "SELECT MIN(planned_start) AS ini, MAX(planned_end) AS fim FROM vps_card "
        "WHERE project_id=? AND planned_start IS NOT NULL", (project_id,))
    r = linhas[0] if linhas else {}
    ini, fim = r.get("ini"), r.get("fim")
    if ini or fim:
        _conn().execute("UPDATE vps_project SET planned_start=?, planned_end=? WHERE project_id=?",
                        (ini, fim, project_id))
    return {"planned_start": ini, "planned_end": fim}


def critical_path(project_id: str) -> dict[str, Any]:
    cards = list_cards(project_id)
    cpm = _cpm(cards, list_deps(project_id))
    items = []
    for c in cards:
        v = cpm.get(c["card_id"], {})
        items.append({"card_id": c["card_id"], "code": c["code"], "title": c["title"],
                      "es": round(v.get("es", 0), 1), "ef": round(v.get("ef", 0), 1),
                      "slack": v.get("slack", 0), "critical": v.get("slack", 1) <= 0.01})
    return {"cards": items, "makespan_h": round(max((v["ef"] for v in cpm.values()), default=0), 1)}


# ── BASELINE (snapshot do plano) ─────────────────────────────────────
def set_baseline(project_id: str, by: str = "planner") -> dict[str, Any]:
    proj = get_project(project_id)
    if not proj:
        return {"ok": False}
    ver = int(proj.get("baseline_version") or 0) + 1
    bid = store.new_id("bl")
    _conn().execute("INSERT INTO vps_baseline(baseline_id,project_id,version,created_at,created_by) VALUES (?,?,?,?,?)",
                    (bid, project_id, ver, store.now_iso(), by))
    for c in list_cards(project_id):
        _conn().execute("INSERT INTO vps_baseline_card(baseline_id,card_id,planned_start,planned_end,planned_effort) VALUES (?,?,?,?,?)",
                        (bid, c["card_id"], c.get("planned_start"), c.get("planned_end"), c.get("planned_effort")))
    _conn().execute("UPDATE vps_project SET baseline_version=?, state='BASELINED' WHERE project_id=?", (ver, project_id))
    store.append_event({"tag_id": proj["tag_id"], "action": "BASELINE_SET", "phase": "PLANNING", "domain": "PROJECT",
                        "event_ts": store.now_iso(), "owner": "Projects", "payload": {"version": ver}})
    return {"ok": True, "version": ver, "baseline_id": bid}


def _baseline_map(project_id: str) -> dict[str, dict[str, Any]]:
    proj = get_project(project_id)
    if not proj or not proj.get("baseline_version"):
        return {}
    bl = _row("SELECT baseline_id FROM vps_baseline WHERE project_id=? AND version=?", (project_id, proj["baseline_version"]))
    if not bl:
        return {}
    return {r["card_id"]: r for r in _rows("SELECT * FROM vps_baseline_card WHERE baseline_id=?", (bl["baseline_id"],))}


# ── LIBERAÇÃO (gênese) + progresso observado ─────────────────────────
ESTADOS = ("PLANNED", "SCHEDULED", "RELEASED", "IN_EXECUTION", "BLOCKED", "DONE")


def _viola_dependencia(card: dict[str, Any], ini: datetime, fim: datetime) -> list[dict[str, Any]]:
    """FS: o sucessor comeca depois do fim do predecessor (mais o lag).

    Nao bloqueia — devolve marcado. Quem planeja as vezes antecipa de proposito
    e assume o risco; o que nao pode e a violacao passar despercebida.
    """
    avisos: list[dict[str, Any]] = []
    deps = _rows("SELECT * FROM vps_card_dep WHERE succ_card_id=? OR pred_card_id=?",
                 (card["card_id"], card["card_id"]))
    for d in deps:
        outro = get_card(d["pred_card_id"] if d["succ_card_id"] == card["card_id"] else d["succ_card_id"])
        if not outro:
            continue
        lag = timedelta(minutes=int(d.get("lag_min") or 0))
        if d["succ_card_id"] == card["card_id"]:
            pe = _parse(outro.get("planned_end"))
            if pe and ini < pe + lag:
                avisos.append({"tipo": "predecessor", "card": outro["code"],
                               "mensagem": f"comeca antes de {outro['code']} terminar"})
        else:
            ps = _parse(outro.get("planned_start"))
            if ps and fim > ps - lag:
                avisos.append({"tipo": "sucessor", "card": outro["code"],
                               "mensagem": f"termina depois de {outro['code']} comecar"})
    return avisos


def set_card_window(card_id: str, planned_start: str, planned_end: str,
                    reason: str = "", actor: str = "planner") -> dict[str, Any] | None:
    """Arrastar/esticar um card no cronograma do projeto."""
    card = get_card(card_id)
    if card is None:
        return None
    if len((reason or "").strip()) < 5:
        return {"ok": False, "message": "justificativa obrigatoria (minimo 5 caracteres)"}
    ini, fim = _parse(planned_start), _parse(planned_end)
    if not ini or not fim or fim <= ini:
        return {"ok": False, "message": "janela invalida (o fim precisa ser depois do inicio)"}
    if card["state"] == "DONE":
        return {"ok": False, "message": "card concluido nao se replaneja — use uma correcao"}

    avisos = _viola_dependencia(card, ini, fim)
    horas = round((fim - ini).total_seconds() / 3600, 2)
    estado = "SCHEDULED" if card["state"] == "PLANNED" else card["state"]
    _conn().execute(
        "UPDATE vps_card SET planned_start=?, planned_end=?, planned_effort=?, state=? WHERE card_id=?",
        (ini.isoformat(), fim.isoformat(), horas, estado, card_id))
    _evento(card["project_id"], "CARD_RESCHEDULED", {
        "card_id": card_id, "code": card["code"], "reason": reason.strip(), "actor": actor,
        "de": {"planned_start": card.get("planned_start"), "planned_end": card.get("planned_end")},
        "para": {"planned_start": ini.isoformat(), "planned_end": fim.isoformat()},
        "avisos": avisos,
    })
    return {"ok": True, "card": get_card(card_id), "warnings": avisos}


def set_card_state(card_id: str, state: str, reason: str = "",
                   actor: str = "planner") -> dict[str, Any] | None:
    """Kanban do projeto: mover o card de raia com justificativa."""
    card = get_card(card_id)
    if card is None:
        return None
    state = (state or "").upper()
    if state not in ESTADOS:
        return {"ok": False, "message": f"estado invalido. Possiveis: {', '.join(ESTADOS)}"}
    if len((reason or "").strip()) < 5:
        return {"ok": False, "message": "justificativa obrigatoria (minimo 5 caracteres)"}
    if state == card["state"]:
        return {"ok": True, "card": card, "warnings": []}
    # RELEASED tem porta propria (gera o Tag-ID, a genese do Fio Dourado).
    if state == "RELEASED" and not card.get("tag_id"):
        r = release_card(card_id)
        if r is not None:
            return {"ok": True, "card": get_card(card_id), "warnings": [], "released": r}
    _conn().execute("UPDATE vps_card SET state=? WHERE card_id=?", (state, card_id))
    _evento(card["project_id"], "CARD_STATE_CHANGED", {
        "card_id": card_id, "code": card["code"], "de": card["state"], "para": state,
        "reason": reason.strip(), "actor": actor})
    return {"ok": True, "card": get_card(card_id), "warnings": []}


def release_card(card_id: str) -> dict[str, Any] | None:
    c = get_card(card_id)
    if not c:
        return None
    proj = get_project(c["project_id"])
    seg = proj["segment"]
    op_tag = tagid.build(seg, "OP", c["code"])
    # gênese: card → Tag-ID (OP), vínculo PROJ→OP, modo LER
    engine.capture({"tag_id": op_tag, "action": "OP_OPENED", "parent_tag_id": proj["tag_id"],
                    "vision_mode": "LER", "confidence": 1.0, "event_ts": store.now_iso(),
                    "operator_id": c.get("assigned_operator"), "owner": "Operations",
                    "payload": {"card": c["code"], "released": True}})
    store.append_event({"tag_id": proj["tag_id"], "action": "CARD_RELEASED", "phase": "EXECUTION",
                        "domain": "PROJECT", "event_ts": store.now_iso(), "owner": "Projects",
                        "payload": {"card": c["code"], "tag_id": op_tag}})
    _conn().execute("UPDATE vps_card SET tag_id=?, state='IN_EXECUTION', actual_start=? WHERE card_id=?",
                    (op_tag, store.now_iso(), card_id))
    set_project_state(c["project_id"], "IN_EXECUTION")
    return get_card(card_id)


def _card_progress(card: dict[str, Any]) -> dict[str, Any]:
    """Avanço FÍSICO observado do card a partir do Tag-ID (fases vistas)."""
    if not card.get("tag_id"):
        return {"pct": float(card.get("pct_complete") or 0), "state": card["state"], "actual_start": card.get("actual_start"), "actual_end": card.get("actual_end")}
    tag = store.get_tag(card["tag_id"])
    if not tag:
        return {"pct": 0, "state": card["state"], "actual_start": card.get("actual_start"), "actual_end": None}
    phases = [p["id"] for p in (templates.get(tag["template_id"]) or {}).get("phases", [])]
    done_states = tag["state"] in ("COMPLETED", "ARCHIVED")
    idx = phases.index(tag["current_phase"]) if tag.get("current_phase") in phases else 0
    pct = 100.0 if done_states else round(100 * idx / max(1, len(phases) - 1), 1)
    state = "DONE" if done_states else "IN_EXECUTION"
    return {"pct": pct, "state": state, "actual_start": tag.get("opened_ts"), "actual_end": tag.get("closed_ts")}


def refresh_progress(project_id: str) -> int:
    n = 0
    for c in list_cards(project_id):
        if not c.get("tag_id"):
            continue
        pr = _card_progress(c)
        _conn().execute("UPDATE vps_card SET pct_complete=?, state=?, actual_start=COALESCE(?,actual_start), actual_end=? WHERE card_id=?",
                        (pr["pct"], pr["state"], pr["actual_start"], pr["actual_end"], c["card_id"]))
        n += 1
    return n


def plan_vs_actual(project_id: str) -> dict[str, Any]:
    refresh_progress(project_id)
    bl = _baseline_map(project_id)
    cards = list_cards(project_id)
    rows = []
    for c in cards:
        b = bl.get(c["card_id"], {})
        rows.append({"card_id": c["card_id"], "code": c["code"], "title": c["title"], "state": c["state"],
                     "resource_key": c.get("resource_key"), "operator": c.get("assigned_operator"),
                     "planned_start": c.get("planned_start"), "planned_end": c.get("planned_end"),
                     "baseline_end": b.get("planned_end"), "actual_start": c.get("actual_start"),
                     "actual_end": c.get("actual_end"), "pct": float(c.get("pct_complete") or 0), "tag_id": c.get("tag_id")})
    return {"cards": rows, "kpis": kpis(project_id, cards, bl)}


def seed_demo() -> dict[str, Any]:
    """Projeto de demonstração completo (WBS + cards + deps + schedule + baseline + liberações)."""
    code = "PRJ-2026-300"
    existing = _row("SELECT project_id FROM vps_project WHERE code=?", (code,))
    if existing:  # idempotente: limpa o anterior
        pid0 = existing["project_id"]
        for t in ("vps_card_dep", "vps_card", "vps_wbs", "vps_baseline", "vps_baseline_card"):
            col = "project_id" if t != "vps_baseline_card" else None
            if col:
                _conn().execute(f"DELETE FROM {t} WHERE project_id=?", (pid0,))
        _conn().execute("DELETE FROM vps_project WHERE project_id=?", (pid0,))

    proj = create_project({"code": code, "name": "Painel Elétrico · COOP-DEMO", "segment": "PANEL",
                           "client_key": "COOP-DEMO", "resource_pool": "res_eng-01,res_cel-mont-01,res_pick-01",
                           "planned_start": datetime.now(timezone.utc).replace(microsecond=0).isoformat()})
    pid = proj["project_id"]
    w_eng = add_wbs(pid, "1", "Engenharia")
    w_sup = add_wbs(pid, "2", "Suprimentos")
    w_prod = add_wbs(pid, "3", "Produção")
    defs = [
        ("C1", "Projeto elétrico", "DELIVERABLE", 16, "res_eng-01", "u123", w_eng["wbs_id"]),
        ("C2", "Compras / suprimentos", "TASK", 24, "res_pick-01", "u123", w_sup["wbs_id"]),
        ("C3", "Picking de materiais", "TASK", 8, "res_pick-01", "u123", w_sup["wbs_id"]),
        ("C4", "Montagem do painel", "TASK", 40, "res_cel-mont-01", "u311", w_prod["wbs_id"]),
        ("C5", "Testes / QC", "TASK", 8, "res_cel-mont-01", "u204", w_prod["wbs_id"]),
        ("C6", "Expedição", "MILESTONE", 4, "res_pick-01", "u123", w_prod["wbs_id"]),
    ]
    cards = {d[0]: add_card(pid, {"code": d[0], "title": d[1], "card_type": d[2], "planned_effort": d[3],
                                  "resource_key": d[4], "assigned_operator": d[5], "wbs_id": d[6]}) for d in defs}
    chain = [("C1", "C2"), ("C2", "C3"), ("C3", "C4"), ("C4", "C5"), ("C5", "C6")]
    for p, s in chain:
        add_dependency(pid, cards[p]["card_id"], cards[s]["card_id"], "FS")
    schedule(pid)
    set_baseline(pid)
    release_card(cards["C1"]["card_id"])   # gênese → Tag-ID
    release_card(cards["C3"]["card_id"])
    refresh_progress(pid)
    return {"ok": True, "project_id": pid, "code": code, "cards": len(cards)}


GPSIS_CODE = "GPSIS_001_DEMO"


def _detalhe(pid: str) -> dict[str, Any]:
    """Projeto com cards, WBS e dependencias — o mesmo que GET /vps/project/{id}."""
    return {**(get_project(pid) or {}), "cards": list_cards(pid), "wbs": list_wbs(pid), "deps": list_deps(pid)}


def seed_gpsis_demo(actor: str = "planner") -> dict[str, Any]:
    """Projeto demonstrativo persistido: GPSIS_001_DEMO.

    Nao e um mock apagado no fim do teste — e um projeto real no banco, com WBS,
    cards, dependencias, baseline, cronograma e duas OPs liberadas, uma delas
    ja estruturada pelo PCP. Serve para quem abre o sistema ver o fluxo inteiro
    (projeto → card → OP → etapas) sem precisar construir nada antes.

    Idempotente: se o projeto ja existe, devolve o que esta la.
    """
    from . import pcp

    existente = _row("SELECT * FROM vps_project WHERE code=?", (GPSIS_CODE,))
    if existente:
        pid = existente["project_id"]
        cards_ex = {c["code"]: c["card_id"] for c in list_cards(pid)}
        liberadas = [c for c in list_cards(pid) if c.get("tag_id")]
        if cards_ex and not liberadas and "MON-01" in cards_ex:
            # rodada anterior parou antes de liberar as OPs: completa daqui
            return _gpsis_liberar(pid, cards_ex, actor, {"scheduled": None}, {"version": None})
        return {"ok": True, "ja_existia": True, "project": _detalhe(pid)}

    proj = create_project({
        "code": GPSIS_CODE, "segment": "PANEL", "owner": "Projects", "client_key": "GPLANSIS",
        "name": "Painel de comando — linha de envase (demonstrativo GPSIS)",
    })
    pid = proj["project_id"]

    wbs = {}
    for code, nome in [("1", "Engenharia"), ("2", "Suprimentos"), ("3", "PCP"),
                       ("4", "Montagem"), ("5", "Testes"), ("6", "Expedicao")]:
        wbs[code] = add_wbs(pid, code, nome, None, 1)["wbs_id"]

    recursos = [r["resource_key"] for r in store.resources(status="ativo")] or [None]

    def res(i: int) -> str | None:
        return recursos[i % len(recursos)] if recursos[0] else None

    cards_def = [
        ("ENG-01", "Projeto eletrico e diagramas", "1", 16, "DELIVERABLE"),
        ("ENG-02", "Lista de materiais (BOM) aprovada", "1", 8, "TASK"),
        ("SUP-01", "Compra de componentes criticos (CLP, disjuntores)", "2", 24, "TASK"),
        ("PCP-01", "Estruturacao do produto e programacao", "3", 8, "TASK"),
        ("MON-01", "Montagem mecanica do painel", "4", 24, "TASK"),
        ("MON-02", "Cablagem e identificacao", "4", 32, "TASK"),
        ("TST-01", "Testes funcionais e ponto a ponto", "5", 16, "TASK"),
        ("EXP-01", "Embalagem e expedicao", "6", 8, "MILESTONE"),
    ]
    cards = {}
    for i, (code, titulo, w, horas, tipo) in enumerate(cards_def):
        cards[code] = add_card(pid, {"code": code, "title": titulo, "wbs_id": wbs[w], "planned_effort": horas,
                                     "card_type": tipo, "resource_key": res(i), "priority": 100 - i * 5})["card_id"]

    for pred, succ in [("ENG-01", "ENG-02"), ("ENG-02", "SUP-01"), ("ENG-02", "PCP-01"), ("SUP-01", "PCP-01"),
                       ("PCP-01", "MON-01"), ("MON-01", "MON-02"), ("MON-02", "TST-01"), ("TST-01", "EXP-01")]:
        add_dependency(pid, cards[pred], cards[succ], "FS", 0)

    agenda = schedule(pid)
    base = set_baseline(pid, actor)
    return _gpsis_liberar(pid, cards, actor, agenda, base)


def _gpsis_liberar(pid: str, cards: dict[str, str], actor: str, agenda: dict[str, Any],
                   base: dict[str, Any]) -> dict[str, Any]:
    """Segunda metade do demonstrativo: libera as OPs e anda uma delas ate o PCP."""
    from . import pcp

    # duas OPs liberadas: uma fica em engenharia, a outra anda ate a separacao
    release_card(cards["ENG-01"])
    release_card(cards["MON-01"])
    op_mon = get_card(cards["MON-01"])["tag_id"]
    engine.capture({"tag_id": op_mon, "action": "DRAWINGS_APPROVED", "operator_id": actor,
                    "payload": {"demo": GPSIS_CODE}})
    engine.capture({"tag_id": op_mon, "action": "SUPPLY_LINKED", "operator_id": actor,
                    "payload": {"demo": GPSIS_CODE}})
    pcp.seed()
    estrutura = pcp.structure(op_mon, 1, actor) or {}

    _evento(pid, "DEMO_SEEDED", {"code": GPSIS_CODE, "cards": len(cards), "scheduled": agenda.get("scheduled"),
                                 "baseline_version": base.get("version"), "op_estruturada": op_mon,
                                 "demandas": len(estrutura.get("demands", [])), "actor": actor})
    return {"ok": True, "ja_existia": False, "project": _detalhe(pid), "schedule": agenda,
            "baseline": base, "ops": [get_card(cards["ENG-01"])["tag_id"], op_mon],
            "pcp": {"ok": estrutura.get("ok"), "demands": len(estrutura.get("demands", []))}}


def kpis(project_id: str, cards: list[dict[str, Any]] | None = None, bl: dict | None = None) -> dict[str, Any]:
    cards = cards if cards is not None else list_cards(project_id)
    bl = bl if bl is not None else _baseline_map(project_id)
    n = len(cards) or 1
    pct_avg = round(sum(float(c.get("pct_complete") or 0) for c in cards) / n, 1)
    done = [c for c in cards if c["state"] == "DONE"]
    # on-time: concluídos cujo actual_end <= baseline_end
    ontime = adher = adher_tot = 0
    for c in cards:
        b = bl.get(c["card_id"], {})
        be, ae = _parse(b.get("planned_end")), _parse(c.get("actual_end"))
        if be:
            adher_tot += 1
            if ae and ae <= be:
                adher += 1; ontime += 1
    # SPI ≈ avanço físico médio / avanço planejado esperado (proporção de cards iniciados)
    started = sum(1 for c in cards if c["state"] in ("IN_EXECUTION", "DONE"))
    planned_expect = round(100 * started / n, 1) or 1
    spi = round((pct_avg or 0) / planned_expect, 2)
    return {
        "CLD_Project_Pct_Complete": pct_avg,
        "CLD_Project_SPI": spi,
        "CLD_Cards_Total": len(cards),
        "CLD_Cards_Done": len(done),
        "CLD_Cards_OnTime": ontime,
        "CLD_Baseline_Adherence": round(100 * adher / adher_tot, 1) if adher_tot else None,
    }
