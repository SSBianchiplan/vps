"""Planejado × realizado por ETAPA — a linha do tempo de cada instância.

O QUE FALTAVA

O card do kanban sabia só duas coisas de tempo: há quanto tempo estava na fase
atual e qual era o SLA dela. Isso responde "está atrasado agora?", mas não
responde nada do que uma operação pergunta o dia inteiro:

  · quando esta OP entrou em cada etapa, e quando saiu?
  · quanto tempo cada etapa levou de verdade?
  · isso bate com o que foi planejado quando a OP abriu?
  · quando ela deve terminar, dado o que já aconteceu?

O tempo por fase até existia — dava para reconstruir varrendo o Event Store de
trás para a frente a cada leitura de tela. Mas reconstruir não é ter: não dá
para comparar com um plano que nunca foi escrito, e o custo cresce com o
histórico.

O QUE ESTA TABELA GUARDA

Uma linha por (instância, fase), com quatro pares de datas:

  baseline_start/end  o plano INICIAL, escrito na gênese a partir dos SLAs do
                      template. Nunca é reescrito — é contra ele que se mede
                      se o processo entregou o que prometeu.
  planned_start/end   o plano VIGENTE. Quando uma etapa atrasa, as seguintes
                      são reprojetadas a partir do agora; senão a previsão de
                      término ficaria congelada num passado que não aconteceu.
  actual_start/end    o REALIZADO — gravado no instante em que o card avançou
                      de etapa, não estimado depois.
  duration_h/variance_h  o que a etapa levou, e o quanto passou do planejado.

Assim "planejado inicial", "planejado atual" e "realizado" convivem sem que um
apague o outro, que é a única forma de a aderência significar alguma coisa.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from ..db.database import get_connection
from . import store, templates

ATIVA, FEITA, PULADA, PENDENTE = "ACTIVE", "DONE", "SKIPPED", "PENDING"


def _p(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None


def _rows(sql: str, params=()) -> list[dict[str, Any]]:
    return [dict(r) for r in get_connection().execute(sql, params).fetchall()]


def _row(sql: str, params=()) -> dict[str, Any] | None:
    r = get_connection().execute(sql, params).fetchone()
    return dict(r) if r else None


def rows(tag_id: str) -> list[dict[str, Any]]:
    return _rows("SELECT * FROM vps_phase_log WHERE tag_id=? ORDER BY seq", (tag_id,))


def get(tag_id: str, phase: str) -> dict[str, Any] | None:
    return _row("SELECT * FROM vps_phase_log WHERE tag_id=? AND phase=?", (tag_id, phase))


# ── Plano inicial ───────────────────────────────────────────────────
def seed(tag: dict[str, Any]) -> int:
    """Escreve o plano da instância a partir dos SLAs do template.

    Só na primeira vez: o baseline é a promessa feita na abertura, e uma
    promessa reescrita depois do fato não serve para medir nada.
    """
    tag_id = tag["tag_id"]
    if rows(tag_id):
        return 0
    tpl = templates.get(tag.get("template_id") or "") or {}
    fases = tpl.get("phases", [])
    if not fases:
        return 0
    inicio = _p(tag.get("opened_ts")) or datetime.now().astimezone()
    conn = get_connection()
    cursor = inicio
    n = 0
    for i, f in enumerate(fases, 1):
        sla = float(f.get("sla_hours") or 0)
        fim = cursor + timedelta(hours=sla)
        conn.execute(
            """INSERT INTO vps_phase_log(phase_log_id, tag_id, phase, seq, baseline_start, baseline_end,
                 planned_start, planned_end, actual_start, actual_end, duration_h, sla_h,
                 variance_h, state, entered_event, exited_event, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("phl_" + uuid.uuid4().hex[:12], tag_id, f["id"], i,
             cursor.isoformat(), fim.isoformat(), cursor.isoformat(), fim.isoformat(),
             None, None, None, sla or None, None, PENDENTE, None, None, store.now_iso()))
        cursor = fim
        n += 1
    return n


def set_window(
    tag_id: str,
    phase: str,
    planned_start: str | None,
    planned_end: str | None,
    *,
    actor: str = "planner",
    cascata: bool = True,
) -> dict[str, Any]:
    """Planeja à mão a janela VIGENTE de uma etapa.

    POR QUE ISTO EXISTE

    Até aqui as datas de etapa só tinham dois autores, e nenhum era humano: o
    `seed`, que escreve o baseline pelos SLAs do template na abertura, e o
    `_reprojetar`, que empurra o que vem depois quando algo atrasa. Quem
    planeja não tinha por onde dizer "esta etapa é na semana que vem" — a
    gaveta mostrava as datas e não deixava tocar. Planejar era, na prática,
    aceitar o SLA genérico do template.

    O QUE ESTA FUNÇÃO NÃO FAZ

    Não encosta no `baseline_*`. O baseline é a promessa da abertura; reescrevê-lo
    ao replanejar apagaria justamente a régua contra a qual a aderência é medida
    — a OP passaria a estar sempre em dia, por construção. Replanejar move o
    plano vigente e o desvio aparece.

    A cascata mantém as etapas seguintes coerentes com a nova data (cada uma
    pelo seu SLA), que é o comportamento que o planejador espera ao empurrar uma
    etapa: o resto do fluxo anda junto, não fica sobreposto.
    """
    r = get(tag_id, phase)
    if r is None:
        return {"ok": False, "message": f"etapa {phase} não existe em {tag_id}"}

    ini = _p(planned_start) or _p(r["planned_start"])
    fim = _p(planned_end) or _p(r["planned_end"])
    if ini and fim and fim < ini:
        return {"ok": False, "message": "o fim planejado é anterior ao início"}

    conn = get_connection()
    conn.execute(
        "UPDATE vps_phase_log SET planned_start=?, planned_end=?, updated_at=? WHERE phase_log_id=?",
        (ini.isoformat() if ini else None, fim.isoformat() if fim else None,
         store.now_iso(), r["phase_log_id"]),
    )
    if cascata and fim:
        _reprojetar(tag_id, int(r["seq"]) + 1, fim)

    # O replanejamento é um FATO do processo, não um ajuste silencioso de tela:
    # vai para o Event Store com autor, e o gatilho de change_log guarda o
    # antes/depois da linha. Quem olhar a OP amanhã sabe que a data mudou, quando
    # e por quem.
    store.append_event({
        "tag_id": tag_id, "action": "PHASE_REPLANNED", "phase": phase,
        "domain": "PLANNING", "event_ts": store.now_iso(), "owner": actor,
        "payload": {"phase": phase, "de": {"planned_start": r["planned_start"], "planned_end": r["planned_end"]},
                    "para": {"planned_start": ini.isoformat() if ini else None,
                             "planned_end": fim.isoformat() if fim else None},
                    "cascata": bool(cascata and fim), "actor": actor},
    })
    return {"ok": True, "rows": rows(tag_id), "resumo": resumo(tag_id)}


def _reprojetar(tag_id: str, a_partir_de: int, quando: datetime) -> None:
    """Empurra o plano VIGENTE das etapas seguintes, mantendo o baseline.

    Sem isto a previsão de término fica presa ao plano da abertura: uma OP com
    três dias de atraso continuaria "prevista para ontem", que é a mesma coisa
    que não ter previsão.
    """
    conn = get_connection()
    cursor = quando
    for r in rows(tag_id):
        if r["seq"] < a_partir_de:
            continue
        sla = float(r["sla_h"] or 0)
        fim = cursor + timedelta(hours=sla)
        conn.execute(
            "UPDATE vps_phase_log SET planned_start=?, planned_end=?, updated_at=? WHERE phase_log_id=?",
            (cursor.isoformat(), fim.isoformat(), store.now_iso(), r["phase_log_id"]))
        cursor = fim


# ── Realizado ───────────────────────────────────────────────────────
def entrar(tag_id: str, phase: str, quando: str, event_id: str | None = None) -> None:
    """Marca a ENTRADA na etapa — o instante em que o card avançou."""
    r = get(tag_id, phase)
    if r is None or r["actual_start"]:
        return
    ts = _p(quando) or datetime.now().astimezone()
    get_connection().execute(
        "UPDATE vps_phase_log SET actual_start=?, state=?, entered_event=?, updated_at=? WHERE phase_log_id=?",
        (ts.isoformat(), ATIVA, event_id, store.now_iso(), r["phase_log_id"]))
    _reprojetar(tag_id, int(r["seq"]), ts)


def sair(tag_id: str, phase: str, quando: str, event_id: str | None = None) -> None:
    """Fecha a etapa: realizado, duração e variância contra o plano vigente."""
    r = get(tag_id, phase)
    if r is None or r["actual_end"]:
        return
    fim = _p(quando) or datetime.now().astimezone()
    ini = _p(r["actual_start"]) or fim
    dur = round((fim - ini).total_seconds() / 3600, 2)
    plan = _p(r["planned_end"])
    var = round((fim - plan).total_seconds() / 3600, 2) if plan else None
    get_connection().execute(
        """UPDATE vps_phase_log SET actual_end=?, actual_start=?, duration_h=?, variance_h=?,
             state=?, exited_event=?, updated_at=? WHERE phase_log_id=?""",
        (fim.isoformat(), ini.isoformat(), dur, var, FEITA, event_id, store.now_iso(), r["phase_log_id"]))
    _reprojetar(tag_id, int(r["seq"]) + 1, fim)


def avancar(tag_id: str, de: str | None, para: str | None, quando: str,
            event_id: str | None = None) -> None:
    """Transição de fase: fecha a que saiu, abre a que entrou.

    Etapas atravessadas no caminho (salto de fase) ficam SKIPPED com data — um
    buraco silencioso na linha do tempo é pior que uma etapa marcada como pulada.
    """
    if de == para:
        if para:
            entrar(tag_id, para, quando, event_id)
        return
    todas = rows(tag_id)
    if not todas:
        return
    idx = {r["phase"]: int(r["seq"]) for r in todas}
    if de:
        sair(tag_id, de, quando, event_id)
    if de and para and de in idx and para in idx:
        conn = get_connection()
        for r in todas:
            if idx[de] < int(r["seq"]) < idx[para] and not r["actual_start"]:
                conn.execute(
                    """UPDATE vps_phase_log SET actual_start=?, actual_end=?, duration_h=0,
                         state=?, updated_at=? WHERE phase_log_id=?""",
                    (quando, quando, PULADA, store.now_iso(), r["phase_log_id"]))
    if para:
        entrar(tag_id, para, quando, event_id)


def retroceder(tag_id: str, de: str | None, para: str, quando: str) -> None:
    """Retrabalho: fecha a fase atual e REABRE a de destino.

    A fase reaberta mantém o actual_start original e perde o actual_end — a
    duração passa a cobrir as duas visitas, que é o custo real do retrabalho.
    Apagar a primeira passagem esconderia exatamente o que se quer medir.
    """
    if de:
        sair(tag_id, de, quando)
    r = get(tag_id, para)
    if r is None:
        return
    get_connection().execute(
        """UPDATE vps_phase_log SET actual_end=NULL, duration_h=NULL, variance_h=NULL,
             state=?, exited_event=NULL, updated_at=? WHERE phase_log_id=?""",
        (ATIVA, store.now_iso(), r["phase_log_id"]))
    if not r["actual_start"]:
        entrar(tag_id, para, quando)
    _reprojetar(tag_id, int(r["seq"]), _p(quando) or datetime.now().astimezone())


def fechar(tag_id: str, quando: str) -> None:
    """Instância concluída: o que ficou aberto fecha na data do fechamento."""
    for r in rows(tag_id):
        if r["actual_start"] and not r["actual_end"]:
            sair(tag_id, r["phase"], quando)


# ── Leitura para o card e para o Fio ────────────────────────────────
def resumo(tag_id: str) -> dict[str, Any]:
    """O que o card do kanban precisa mostrar sem abrir a instância."""
    rs = rows(tag_id)
    if not rs:
        return {}
    feitas = [r for r in rs if r["state"] in (FEITA, PULADA)]
    ativa = next((r for r in rs if r["state"] == ATIVA), None)
    ultimo = rs[-1]
    base_fim = _p(ultimo["baseline_end"])
    prev_fim = _p(ultimo["planned_end"])
    desvio = round((prev_fim - base_fim).total_seconds() / 3600, 2) if (prev_fim and base_fim) else None
    reais = [r for r in rs if r["duration_h"] is not None and r["state"] == FEITA]
    no_prazo = [r for r in reais if (r["variance_h"] or 0) <= 0]
    return {
        "fases_total": len(rs),
        "fases_feitas": len(feitas),
        "fase_atual": ativa["phase"] if ativa else None,
        "fase_inicio": ativa["actual_start"] if ativa else None,
        "fase_previsto_fim": ativa["planned_end"] if ativa else None,
        "fase_baseline_fim": ativa["baseline_end"] if ativa else None,
        "proxima_fase": next((r["phase"] for r in rs if r["state"] == PENDENTE), None),
        "baseline_fim": ultimo["baseline_end"],
        "previsao_fim": ultimo["planned_end"],
        "desvio_h": desvio,
        "aderencia_pct": round(100 * len(no_prazo) / len(reais)) if reais else None,
        "realizado_h": round(sum(float(r["duration_h"] or 0) for r in reais), 2) if reais else 0.0,
    }


def kpis() -> dict[str, Any]:
    todas = _rows("SELECT * FROM vps_phase_log")
    feitas = [r for r in todas if r["state"] == FEITA and r["duration_h"] is not None]
    atrasadas = [r for r in feitas if (r["variance_h"] or 0) > 0]
    puladas = [r for r in todas if r["state"] == PULADA]
    return {
        "CLD_Phase_Rows": len(todas),
        "CLD_Phase_Done": len(feitas),
        "CLD_Phase_OnTime_Pct": round(100 * (len(feitas) - len(atrasadas)) / len(feitas), 1) if feitas else None,
        "CLD_Phase_Skipped": len(puladas),
        "CLD_Phase_Avg_Duration_h": round(sum(float(r["duration_h"]) for r in feitas) / len(feitas), 2) if feitas else None,
    }


def backfill() -> dict[str, Any]:
    """Reconstrói o histórico de fases das instâncias que nasceram antes desta
    tabela existir, a partir do Event Store.

    Sem isto o kanban ficaria dividido em dois: instâncias novas com linha do
    tempo, antigas com um traço. O baseline delas é o SLA do template contado da
    gênese — a promessa que valia quando abriram.
    """
    criadas = tags = 0
    for t in store.all_tags(include_archived=True):
        if rows(t["tag_id"]):
            continue
        if not seed(t):
            continue
        tags += 1
        fases = [r["phase"] for r in rows(t["tag_id"])]
        anterior: str | None = None
        for e in store.events_for(t["tag_id"]):
            ph = e.get("phase")
            if not ph or ph not in fases:
                continue
            if ph != anterior:
                avancar(t["tag_id"], anterior, ph, e.get("event_ts") or store.now_iso(), e.get("event_id"))
                anterior = ph
            criadas += 1
        if t["state"] in ("COMPLETED", "ARCHIVED"):
            fechar(t["tag_id"], t.get("closed_ts") or t.get("last_event_ts") or store.now_iso())
    return {"ok": True, "instancias": tags, "eventos": criadas}
