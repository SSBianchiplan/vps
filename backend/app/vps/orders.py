"""Ordens de produção — a porta de entrada do processo.

O QUE FALTAVA

O sistema sabia tudo sobre uma OP depois que ela existia: fases, SLA, separação,
reconciliação, Fio Dourado. Só não sabia ABRIR uma. A gênese acontecia por dois
caminhos e nenhum servia para o dia a dia: os seeds de demonstração e uma
captura de evento crua, que exige saber montar o Tag-ID e escolher a ação de
gênese na mão. Na tela dava para criar PROJETO, não ordem — então o PCP tinha o
que explodir só quando alguém rodava a demonstração.

O QUE ESTE MÓDULO FAZ

`abrir()` é o único lugar por onde uma OP nasce, e nasce ligada:

  Tag-ID          VPS:{segmento}:OP:{código}:{instância} — a chave do resto
  Fio Dourado     ação de gênese do template (OP_OPENED), que por sua vez cria
                  a instância, semeia as fases pelos SLAs e entra na primeira
  Linhagem        filha do nó PROJ do projeto, quando a OP nasce dentro de um
  Estrutura       com produto escolhido, o PCP explode a BOM em demandas de
                  separação e abre o Tag-ID filho da separação (PICK)
  Cronograma      um card no projeto já apontando para o Tag-ID, para a OP
                  aparecer no APS/Visual Planning sem um segundo cadastro
  Plano           quando vêm datas, a janela vigente das fases é ajustada
                  (o baseline dos SLAs continua registrado, para medir desvio)

DOIS CAMINHOS, DE PROPÓSITO

Com `product_key` a OP puxa a estrutura e o PCP tem o que separar — é o caminho
normal. Sem ele a OP abre mesmo assim, porque a planta real tem produto sem BOM
cadastrada e recusar a abertura empurraria o operador de volta para a planilha.
O que não acontece é fingir: sem estrutura, o PCP declara `BOM_INCOMPLETE` e a
pendência aparece no cockpit, em vez de uma lista de separação inventada.
"""
from __future__ import annotations

from typing import Any

from ..db.database import get_connection
from . import engine, pcp, phases, planning, store, tagid, templates

# Ação de gênese por tipo de entidade — quem sabe disso é o template.
_GENESE = templates.genesis_action


def _row(sql: str, params=()) -> dict[str, Any] | None:
    r = get_connection().execute(sql, params).fetchone()
    return dict(r) if r else None


def proximo_codigo(segment: str = "GENERIC", ano: int | None = None) -> str:
    """Sugere o próximo número de OP do segmento — OP-2026-0007.

    Sugestão, não reserva: o operador pode trocar. Quem garante unicidade é o
    Tag-ID (chave primária de `vps_tag`), conferido em `abrir()`.
    """
    from datetime import datetime

    ano = ano or datetime.now().year
    prefixo = f"OP-{ano}-"
    linhas = get_connection().execute(
        "SELECT natural_key FROM vps_tag WHERE entity_type='OP' AND natural_key LIKE ?",
        (prefixo + "%",),
    ).fetchall()
    maior = 0
    for l in linhas:
        sufixo = str(dict(l)["natural_key"])[len(prefixo):]
        if sufixo.isdigit():
            maior = max(maior, int(sufixo))
    return f"{prefixo}{maior + 1:04d}"


def abrir(d: dict[str, Any]) -> dict[str, Any]:
    """Abre uma ordem de produção e devolve tudo que ela gerou.

    `d`: code, segment, project_id?, product_key?, qty, title?, planned_start?,
         planned_end?, actor?
    """
    code = str(d.get("code") or "").strip()
    if not code:
        return {"ok": False, "message": "número da OP é obrigatório"}
    actor = d.get("actor") or "planner"
    projeto = planning.get_project(d["project_id"]) if d.get("project_id") else None
    if d.get("project_id") and projeto is None:
        return {"ok": False, "message": "projeto não encontrado"}

    # O segmento define template, BOM e o próprio Tag-ID. Herdar do projeto
    # evita a OP nascer num processo diferente do projeto que a pediu.
    segment = str(d.get("segment") or (projeto or {}).get("segment") or "GENERIC").upper()
    instancia = str(d.get("instance") or "01")
    tag_id = tagid.build(segment, "OP", code, instancia)

    if store.get_tag(tag_id):
        # Reabrir por engano criaria um segundo Fio para a mesma ordem física.
        return {"ok": False, "message": f"a OP {code} já existe neste segmento", "tag_id": tag_id}

    qty = float(d.get("qty") or 1)
    avisos: list[str] = []

    # 1) GÊNESE — cria a instância, semeia as fases e entra na primeira.
    engine.capture({
        "tag_id": tag_id,
        "action": _GENESE("OP"),
        "parent_tag_id": (projeto or {}).get("tag_id"),
        "owner": d.get("owner") or "Operations",
        "payload": {"code": code, "qty": qty, "title": d.get("title") or code,
                    "product_key": d.get("product_key"), "project_id": d.get("project_id"),
                    "actor": actor},
    })

    # 2) ESTRUTURA — só quando há produto escolhido. Sem produto a OP existe e o
    #    PCP fica visivelmente pendente, que é a verdade da planta.
    estrutura: dict[str, Any] | None = None
    if d.get("product_key"):
        estrutura = pcp.structure(tag_id, qty, actor=actor)
        if estrutura and not estrutura.get("ok"):
            avisos.append(estrutura.get("message") or "estrutura não pôde ser explodida")
    else:
        avisos.append("aberta sem estrutura — o PCP vai pedir a BOM antes da separação")

    # 3) PLANO — datas do planejador substituem a janela vigente das fases.
    #    A primeira etapa recebe o intervalo pedido e a cascata reacomoda o
    #    resto pelos SLAs; o baseline da abertura permanece para medir desvio.
    if d.get("planned_start") or d.get("planned_end"):
        etapas = phases.rows(tag_id)
        if etapas:
            phases.set_window(tag_id, etapas[0]["phase"], d.get("planned_start"),
                              d.get("planned_end"), actor=actor, cascata=True)

    # 4) CRONOGRAMA — a OP aparece no projeto sem um segundo cadastro.
    card = None
    if projeto:
        card = planning.add_card(projeto["project_id"], {
            "code": code,
            "title": d.get("title") or code,
            "card_type": "DELIVERABLE",
            "planned_effort": float(d.get("planned_effort") or 8),
            "resource_key": d.get("resource_key"),
        })
        get_connection().execute(
            "UPDATE vps_card SET tag_id=?, planned_start=?, planned_end=?, state=? WHERE card_id=?",
            (tag_id, d.get("planned_start"), d.get("planned_end"), "SCHEDULED", card["card_id"]),
        )
        card = planning.get_card(card["card_id"])
        # A janela do projeto é a envoltória das ordens: abrir uma OP com datas
        # move a entrega do projeto na hora, sem esperar um "Agendar".
        planning.sincronizar_janela(projeto["project_id"])

    return {
        "ok": True,
        "tag_id": tag_id,
        "code": code,
        "segment": segment,
        "tag": store.get_tag(tag_id),
        "phases": phases.rows(tag_id),
        "estrutura": estrutura,
        "card": card,
        "project_id": (projeto or {}).get("project_id"),
        "avisos": avisos,
    }


def abrir_lote(itens: list[dict[str, Any]], comuns: dict[str, Any] | None = None) -> dict[str, Any]:
    """Abre várias OPs numa passada — é assim que o assistente do projeto chama.

    Uma OP que falha não derruba as outras: o assistente mostra o que abriu e o
    que não abriu, em vez de deixar o operador adivinhar onde parou.
    """
    base = comuns or {}
    abertas: list[dict[str, Any]] = []
    recusadas: list[dict[str, Any]] = []
    for it in itens:
        r = abrir({**base, **it})
        (abertas if r.get("ok") else recusadas).append(r)
    return {"abertas": abertas, "recusadas": recusadas,
            "total": len(itens), "ok": len(abertas)}


def do_projeto(project_id: str, incluir_arquivadas: bool = False) -> list[dict[str, Any]]:
    """OPs de um projeto — pela LINHAGEM, não por uma coluna paralela.

    O vínculo verdadeiro é o Fio (`vps_lineage`, PROJ->OP). Ler dali garante que
    a lista não diverge do que o cockpit e a Árvore mostram.

    Arquivadas ficam de fora por padrão. A linhagem guarda TODAS as instâncias
    de uma chave natural — é para isso que ela existe, e reabrir uma ordem não
    apaga a anterior —, mas quem abre o projeto quer o que está valendo. Com
    `incluir_arquivadas` a história inteira volta.
    """
    p = planning.get_project(project_id)
    if not p or not p.get("tag_id"):
        return []
    filhos = store.children_of(p["tag_id"])
    out: list[dict[str, Any]] = []
    for f in filhos:
        t = store.get_tag(f["child_tag_id"])
        if not t or t.get("entity_type") != "OP":
            continue
        if not incluir_arquivadas and t.get("state") == "ARCHIVED":
            continue
        t["resumo"] = phases.resumo(t["tag_id"])
        out.append(t)
    return out
