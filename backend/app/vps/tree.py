"""Árvore do planejamento — Visual Planning, APS e Fio Dourado num só desenho.

O QUE ESTE MÓDULO RESPONDE

"De onde veio esta OP, quem a planejou, em que recurso ela está sequenciada e
qual tabela guarda cada pedaço disso." Hoje essa resposta exige abrir quatro
telas e cruzar de cabeça: Visual Planning tem o projeto e os cards, o APS tem
a programação, o cockpit tem o Fio, e Bases tem os números soltos.

A árvore é montada dos DADOS, não de um desenho fixo: cada nó traz a tabela de
origem e a contagem, então o que aparece é o que existe no banco. Nó sem dado
não é inventado — some.

TRÊS RAMOS

  Visual Planning  projeto → WBS → card → (card liberado vira OP no Fio)
  APS              cenário → recurso → operação sequenciada → (tag da OP)
  Fio Dourado      raiz (SO/PROJ) → filhos por linhagem, recursivo

Os três se encontram: o card liberado e a operação do APS apontam para o mesmo
Tag-ID que o Fio Dourado governa. É esse encontro que a árvore torna visível.
"""
from __future__ import annotations

from typing import Any

from ..db.database import get_connection
from . import store

_MAX_FILHOS = 40        # um ramo com 500 irmãos vira ruído, não informação
_MAX_PROFUNDIDADE = 6


def _linhas(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    try:
        return [dict(r) for r in get_connection().execute(sql, params).fetchall()]
    except Exception:  # noqa: BLE001
        return []


def _n(sql: str, params: tuple = ()) -> int:
    r = _linhas(sql, params)
    return int(r[0].get("n") or 0) if r else 0


def _no(id_: str, label: str, tipo: str, **extra: Any) -> dict[str, Any]:
    no = {"id": id_, "label": label, "tipo": tipo, "filhos": []}
    no.update({k: v for k, v in extra.items() if v is not None})
    return no


# ── Ramo 1: Visual Planning (projetos e cards) ───────────────────────
def _ramo_projetos() -> dict[str, Any]:
    projetos = _linhas("SELECT * FROM vps_project ORDER BY created_at DESC")
    raiz = _no("mod:planning", "Visual Planning", "modulo", tabela="vps_project",
               n=len(projetos), modulo="planejamento",
               desc="Projetos, WBS, cards, dependências, CPM e baseline")
    for p in projetos[:_MAX_FILHOS]:
        pid = p["project_id"]
        cards = _linhas("SELECT * FROM vps_card WHERE project_id=? ORDER BY priority, code", (pid,))
        wbs = _linhas("SELECT * FROM vps_wbs WHERE project_id=? ORDER BY code", (pid,))
        deps = _linhas("SELECT * FROM vps_card_dep WHERE project_id=?", (pid,))
        no_p = _no(f"proj:{pid}", f"{p['code']} · {p.get('name') or ''}".strip(" ·"), "projeto",
                   tabela="vps_project", pk=pid, estado=p.get("state"),
                   tag_id=p.get("tag_id"), meta={"cards": len(cards), "wbs": len(wbs), "dependencias": len(deps)})
        # WBS agrupa os cards; card sem WBS entra direto no projeto
        por_wbs: dict[str | None, list[dict[str, Any]]] = {}
        for c in cards:
            por_wbs.setdefault(c.get("wbs_id"), []).append(c)

        def no_card(c: dict[str, Any]) -> dict[str, Any]:
            return _no(f"card:{c['card_id']}", f"{c['code']} · {c.get('title') or ''}".strip(" ·"), "card",
                       tabela="vps_card", pk=c["card_id"], estado=c.get("state"),
                       tag_id=c.get("tag_id"),
                       meta={"esforço_h": c.get("planned_effort"), "recurso": c.get("resource_key"),
                             "operador": c.get("assigned_operator"), "%": c.get("pct_complete")})

        for w in wbs[:_MAX_FILHOS]:
            filhos = [no_card(c) for c in por_wbs.get(w["wbs_id"], [])[:_MAX_FILHOS]]
            no_w = _no(f"wbs:{w['wbs_id']}", f"{w['code']} · {w['name']}", "wbs",
                       tabela="vps_wbs", pk=w["wbs_id"], n=len(filhos))
            no_w["filhos"] = filhos
            no_p["filhos"].append(no_w)
        for c in por_wbs.get(None, [])[:_MAX_FILHOS]:
            no_p["filhos"].append(no_card(c))
        raiz["filhos"].append(no_p)
    return raiz


# ── Ramo 2: APS (cenários, recursos, operações) ──────────────────────
def _ramo_aps() -> dict[str, Any]:
    cenarios = _linhas("SELECT scenario_id AS s, COUNT(*) AS n FROM vps_schedule GROUP BY scenario_id ORDER BY 2 DESC")
    recursos = _linhas("SELECT * FROM vps_resource ORDER BY resource_key")
    raiz = _no("mod:aps", "APS — sequenciamento", "modulo", tabela="vps_schedule",
               n=sum(c["n"] for c in cenarios), modulo="aps",
               desc="Capacidade finita: cenário → recurso → operação, com gargalo e CTP",
               meta={"cenários": len(cenarios), "recursos": len(recursos)})
    for c in cenarios[:_MAX_FILHOS]:
        cen = c["s"] or "(sem cenário)"
        no_c = _no(f"aps:{cen}", cen, "cenario", tabela="vps_schedule", n=c["n"])
        # o cenário "proj:CODIGO" é o cronograma de um projeto: o elo com o ramo 1
        if cen.startswith("proj:"):
            no_c["vinculo"] = {"tipo": "projeto", "codigo": cen.split(":", 1)[1]}
        porrec = _linhas("SELECT resource_key AS r, COUNT(*) AS n FROM vps_schedule WHERE scenario_id=? GROUP BY 1 ORDER BY 2 DESC", (cen,))
        for r in porrec[:_MAX_FILHOS]:
            rk = r["r"] or "—"
            info = next((x for x in recursos if x["resource_key"] == rk), {})
            no_r = _no(f"aps:{cen}:{rk}", rk, "recurso", tabela="vps_resource", pk=rk, n=r["n"],
                       meta={"capacidade": info.get("capacity"), "skills": info.get("skills")})
            ops = _linhas(
                "SELECT schedule_id, tag_id, operation, seq, planned_start, planned_end, rule_used"
                " FROM vps_schedule WHERE scenario_id=? AND resource_key=? ORDER BY seq LIMIT ?",
                (cen, rk, _MAX_FILHOS))
            for o in ops:
                no_r["filhos"].append(_no(
                    f"sch:{o['schedule_id']}", f"{o.get('operation') or '?'} · {o.get('tag_id') or ''}".strip(" ·"),
                    "operacao", tabela="vps_schedule", pk=o["schedule_id"], tag_id=o.get("tag_id"),
                    meta={"seq": o.get("seq"), "início": o.get("planned_start"), "fim": o.get("planned_end"),
                          "regra": o.get("rule_used")}))
            no_c["filhos"].append(no_r)
        raiz["filhos"].append(no_c)
    return raiz


# ── Ramo 3: Fio Dourado (linhagem) ───────────────────────────────────
def _ramo_linhagem(segmento: str | None = None) -> dict[str, Any]:
    tags = store.all_tags(include_archived=True)
    if segmento:
        tags = [t for t in tags if (t.get("segment") or "").upper() == segmento.upper()]
    por_id = {t["tag_id"]: t for t in tags}
    filhos_de: dict[str, list[str]] = {}
    for e in _linhas("SELECT parent_tag_id, child_tag_id, relation FROM vps_lineage"):
        filhos_de.setdefault(e["parent_tag_id"], []).append(e["child_tag_id"])
    com_pai = {c for f in filhos_de.values() for c in f}
    raizes = [t for t in tags if t["tag_id"] not in com_pai]

    raiz = _no("mod:fio", "Fio Dourado — linhagem", "modulo", tabela="vps_lineage",
               n=len(com_pai), modulo="vps",
               desc="Cada instância e de onde ela veio: SO → PROJ → OP → PICK/ITEM/OCC/MEAS/SHIP/INV",
               meta={"instâncias": len(tags), "vínculos": _n("SELECT COUNT(*) AS n FROM vps_lineage"),
                     "raízes": len(raizes)})

    vistos: set[str] = set()

    def monta(tag_id: str, nivel: int) -> dict[str, Any] | None:
        if tag_id in vistos or nivel > _MAX_PROFUNDIDADE:
            return None      # ciclo ou fundo: para em vez de recursar sem fim
        vistos.add(tag_id)
        t = por_id.get(tag_id)
        if not t:
            return None
        pend = store.open_pending_count(tag_id)
        occ = store.open_occurrence_count(tag_id)
        no = _no(f"tag:{tag_id}", f"{t.get('entity_type')} {t.get('natural_key')}", "tag",
                 tabela="vps_tag", pk=tag_id, estado=t.get("state"), tag_id=tag_id,
                 meta={"fase": t.get("current_phase"), "template": t.get("template_id"),
                       "pendências": pend, "ocorrências": occ})
        for c in filhos_de.get(tag_id, [])[:_MAX_FILHOS]:
            f = monta(c, nivel + 1)
            if f:
                no["filhos"].append(f)
        return no

    for r in sorted(raizes, key=lambda t: (t.get("entity_type") or "", t.get("natural_key") or ""))[:_MAX_FILHOS]:
        n = monta(r["tag_id"], 0)
        if n:
            raiz["filhos"].append(n)
    return raiz


# ── Bases ligadas a cada ramo ────────────────────────────────────────
def _bases() -> list[dict[str, Any]]:
    tabelas = [
        ("vps_project", "Projetos", "planning"), ("vps_wbs", "WBS", "planning"),
        ("vps_card", "Cards", "planning"), ("vps_card_dep", "Dependências", "planning"),
        ("vps_baseline", "Baselines", "planning"),
        ("vps_schedule", "Programação APS", "aps"), ("vps_resource", "Recursos", "aps"),
        ("vps_tag", "Instâncias (Tag-ID)", "fio"), ("vps_event", "Event Store", "fio"),
        ("vps_lineage", "Vínculos de linhagem", "fio"), ("vps_pending", "Pendências", "fio"),
        ("vps_occurrence", "Ocorrências", "fio"), ("vps_erp_doc", "Documentos ERP", "fio"),
        ("vps_operator", "Operadores", "pessoas"), ("vps_access", "Usuários (acesso)", "pessoas"),
        ("audit_event", "Trilha de auditoria", "governanca"),
    ]
    out = []
    for t, label, ramo in tabelas:
        out.append({"tabela": t, "label": label, "ramo": ramo,
                    "linhas": _n(f"SELECT COUNT(*) AS n FROM {t}")})
    # o change_log só existe no PostgreSQL
    try:
        from .. import changes
        if changes.disponivel():
            out.append({"tabela": "change_log", "label": "Log de mudanças", "ramo": "governanca",
                        "linhas": _n("SELECT COUNT(*) AS n FROM change_log")})
    except Exception:  # noqa: BLE001
        pass
    return out


def arvore(segmento: str | None = None) -> dict[str, Any]:
    """A árvore inteira + as bases que a sustentam."""
    ramos = [_ramo_projetos(), _ramo_aps(), _ramo_linhagem(segmento)]
    def conta(no: dict[str, Any]) -> int:
        return 1 + sum(conta(f) for f in no.get("filhos", []))
    raiz = _no("raiz", "Planejamento & Rastreabilidade", "raiz",
               desc="Visual Planning, APS e Fio Dourado — e onde os três se encontram")
    raiz["filhos"] = ramos
    return {
        "gerado_em": store.now_iso(),
        "segmento": segmento,
        "arvore": raiz,
        "bases": _bases(),
        "resumo": {"nos": conta(raiz) - 1, "ramos": len(ramos),
                   "limite_filhos": _MAX_FILHOS, "limite_profundidade": _MAX_PROFUNDIDADE},
    }
