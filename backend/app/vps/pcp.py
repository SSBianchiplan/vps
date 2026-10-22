"""PCP — Planejamento e Controle da Produção.

A ETAPA QUE FALTAVA NO PROCESSO

O fluxo ia de PURCHASING direto para PICKING. Quer dizer: alguém decidia de
cabeça o que separar. A lista de separação não vinha de lugar nenhum, não tinha
dono e não tinha como ser conferida — e a diferença entre o que o produto PEDE e
o que foi separado não tinha onde ser medida, porque o "pede" não estava escrito.

O PCP é onde a demanda vira material. Ele fica ao lado de engenharia e compras,
recebe a OP e faz a **estruturação do produto**: explode a estrutura (`vps_bom`)
em **demandas de separação** (`vps_pick_demand`), abre o Tag-ID da separação como
filho da OP (linhagem) e libera o processo para seguir. Depois disso o PICKING
tem o que buscar, e cada item separado pode ser confrontado com o planejado.

COMO SE LIGA AO RESTO

- **Fio Dourado**: `STRUCTURE_RELEASED` na OP, `PICK_REQUESTED` no filho, e
  `PICK_SHORT` / `PICK_COMPLETED` conforme a separação anda. Todos passam pela
  `engine.capture`, então fase, SLA, pendência e ocorrência funcionam sozinhos.
- **Template**: a fase `PCP` é declarada, não codificada — `blocking_on`
  `BOM_INCOMPLETE` trava a OP quando o produto não tem estrutura.
- **Log de mudanças**: as duas tabelas têm gatilho; toda alteração guarda o
  antes/depois com o autor.
- **APS**: o `lead_time_h` do item entra na conversa de CTP/ressuprimento.
"""
from __future__ import annotations

import uuid
from typing import Any

from ..db.database import get_connection
from . import engine, store, tagid

ESTADOS = ("PLANNED", "PICKING", "DONE", "SHORT")

# Estrutura de demonstração por família. Não é "dado de mentira": é o mínimo
# para a etapa existir num sistema recém-instalado, do mesmo jeito que os
# recursos padrão do APS. Quem usa troca pela estrutura real.
SEMENTE: dict[str, list[dict[str, Any]]] = {
    "PANEL": [
        {"item_key": "RES-22K", "descricao": "Resistor 22kΩ 1/4W", "qty": 12, "unit": "un", "lead_time_h": 24},
        {"item_key": "DISJ-C16", "descricao": "Disjuntor C16 1P", "qty": 4, "unit": "un", "lead_time_h": 72, "critico": 1},
        {"item_key": "CAB-2.5", "descricao": "Cabo flexível 2,5mm² azul", "qty": 30, "unit": "m", "lead_time_h": 48},
        {"item_key": "BORNE-X", "descricao": "Borne sindal 6mm²", "qty": 24, "unit": "un", "lead_time_h": 24},
        {"item_key": "CLP-S71200", "descricao": "CLP S7-1200 CPU 1214C", "qty": 1, "unit": "un", "lead_time_h": 240, "critico": 1},
    ],
    "GENERIC": [
        {"item_key": "MP-001", "descricao": "Matéria-prima principal", "qty": 10, "unit": "kg", "lead_time_h": 48},
        {"item_key": "EMB-CX", "descricao": "Caixa de embalagem", "qty": 1, "unit": "un", "lead_time_h": 24},
    ],
    "FOOD": [
        {"item_key": "ING-BASE", "descricao": "Ingrediente base", "qty": 25, "unit": "kg", "lead_time_h": 12, "critico": 1},
        {"item_key": "ING-COND", "descricao": "Condimento", "qty": 2, "unit": "kg", "lead_time_h": 24},
        {"item_key": "EMB-PET", "descricao": "Embalagem PET 500ml", "qty": 60, "unit": "un", "lead_time_h": 48},
    ],
    "PHARMA": [
        {"item_key": "API-01", "descricao": "Insumo farmacêutico ativo", "qty": 1.5, "unit": "kg", "lead_time_h": 168, "critico": 1},
        {"item_key": "EXC-LAC", "descricao": "Excipiente lactose", "qty": 8, "unit": "kg", "lead_time_h": 72},
        {"item_key": "BLI-PVC", "descricao": "Blister PVC/alumínio", "qty": 500, "unit": "un", "lead_time_h": 96},
    ],
}

TEMPLATE_DE: dict[str, str] = {
    "PANEL": "PANEL_ETO_V1", "GENERIC": "GENERIC_V1", "FOOD": "FOOD_V1", "PHARMA": "PHARMA_V1",
}


def _rows(sql: str, params=()) -> list[dict[str, Any]]:
    return [dict(r) for r in get_connection().execute(sql, params).fetchall()]


def _row(sql: str, params=()) -> dict[str, Any] | None:
    r = get_connection().execute(sql, params).fetchone()
    return dict(r) if r else None


# ── Estrutura de produto (BOM) ──────────────────────────────────────
def bom(product_key: str | None = None) -> list[dict[str, Any]]:
    if product_key:
        return _rows("SELECT * FROM vps_bom WHERE product_key=? ORDER BY posicao, item_key", (product_key.upper(),))
    return _rows("SELECT * FROM vps_bom ORDER BY product_key, posicao, item_key")


def produtos() -> list[dict[str, Any]]:
    """Famílias com estrutura, para a lista do módulo."""
    linhas = _rows("SELECT product_key, COUNT(*) AS itens, SUM(critico) AS criticos FROM vps_bom GROUP BY product_key ORDER BY product_key")
    for l in linhas:
        l["template_id"] = TEMPLATE_DE.get(l["product_key"], "GENERIC_V1")
        l["criticos"] = int(l.get("criticos") or 0)
    return linhas


def upsert_item(d: dict[str, Any]) -> dict[str, Any]:
    bid = d.get("bom_id") or "bom_" + uuid.uuid4().hex[:12]
    produto = (d.get("product_key") or "GENERIC").upper()
    campos = {
        "product_key": produto,
        "template_id": d.get("template_id") or TEMPLATE_DE.get(produto, "GENERIC_V1"),
        "item_key": (d.get("item_key") or "").strip().upper(),
        "descricao": d.get("descricao") or "",
        "qty": float(d.get("qty") or 1),
        "unit": d.get("unit") or "un",
        "posicao": int(d.get("posicao") or 0),
        "lead_time_h": float(d.get("lead_time_h") or 0),
        "critico": 1 if d.get("critico") else 0,
    }
    if not campos["item_key"]:
        raise ValueError("item_key é obrigatório")
    conn = get_connection()
    if _row("SELECT bom_id FROM vps_bom WHERE bom_id=?", (bid,)):
        conn.execute(
            """UPDATE vps_bom SET product_key=?, template_id=?, item_key=?, descricao=?, qty=?,
                 unit=?, posicao=?, lead_time_h=?, critico=? WHERE bom_id=?""",
            (*campos.values(), bid))
    else:
        conn.execute(
            """INSERT INTO vps_bom(bom_id, product_key, template_id, item_key, descricao, qty,
                 unit, posicao, lead_time_h, critico, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (bid, *campos.values(), store.now_iso()))
    return _row("SELECT * FROM vps_bom WHERE bom_id=?", (bid,)) or {}


def delete_item(bom_id: str) -> bool:
    if not _row("SELECT bom_id FROM vps_bom WHERE bom_id=?", (bom_id,)):
        return False
    get_connection().execute("DELETE FROM vps_bom WHERE bom_id=?", (bom_id,))
    return True


def seed() -> dict[str, Any]:
    """Estrutura inicial, só onde ainda não existe nenhuma."""
    criados = 0
    for produto, itens in SEMENTE.items():
        if bom(produto):
            continue
        for i, it in enumerate(itens, 1):
            upsert_item({**it, "product_key": produto, "posicao": i})
            criados += 1
    return {"ok": True, "itens": criados, "produtos": produtos()}


# ── Explosão: a estruturação do produto ─────────────────────────────
def _produto_da_tag(tag: dict[str, Any]) -> str:
    return (tag.get("segment") or "GENERIC").upper()


def _tag_da_separacao(tag: dict[str, Any]) -> str:
    """PK-xxxx a partir da OP: a separação é outra entidade, com Tag-ID próprio."""
    nk = str(tag.get("natural_key") or "")
    # Só o prefixo "OP-" vira "PK-": cortar no primeiro hífen transformava
    # "TESTE-PCP" em "PK-PCP" e a separação perdia a referência da própria OP.
    chave = ("PK-" + nk[3:]) if nk.upper().startswith("OP-") else ("PK-" + nk)
    return tagid.build(_produto_da_tag(tag), "PICK", chave, str(tag.get("instance") or "01"))


def demands(tag_id: str) -> list[dict[str, Any]]:
    return _rows("SELECT * FROM vps_pick_demand WHERE tag_id=? ORDER BY critico DESC, item_key", (tag_id,))


def structure(tag_id: str, qty: float = 1, actor: str = "pcp") -> dict[str, Any] | None:
    """Explode a estrutura do produto em demandas de separação.

    Idempotente por recusa: estruturar duas vezes dobraria a lista de separação
    sem ninguém perceber, e o picking passaria a buscar o dobro do necessário.
    """
    tag = store.get_tag(tag_id)
    if tag is None:
        return None
    if tag.get("state") in ("COMPLETED", "ARCHIVED"):
        return {"ok": False, "message": "OP encerrada não se estrutura"}
    if demands(tag_id):
        return {"ok": False, "message": "esta OP já foi estruturada — limpe as demandas antes de refazer"}

    produto = _produto_da_tag(tag)
    itens = bom(produto)
    if not itens:
        # A fase declara blocking_on BOM_INCOMPLETE: o evento abre a pendência
        # e trava a OP. Estruturar sem estrutura seria inventar a lista.
        engine.capture({"tag_id": tag_id, "action": "BOM_INCOMPLETE", "owner": "PCP",
                        "payload": {"produto": produto, "actor": actor}})
        return {"ok": False, "message": f"produto '{produto}' não tem estrutura cadastrada — cadastre a BOM antes",
                "produto": produto}

    mult = max(0.0001, float(qty or 1))
    pick_tag = _tag_da_separacao(tag)
    engine.capture({"tag_id": pick_tag, "action": "PICK_REQUESTED", "parent_tag_id": tag_id,
                    "owner": "Supply", "payload": {"origem": "PCP", "produto": produto, "qty": mult}})

    conn = get_connection()
    criadas: list[dict[str, Any]] = []
    for it in itens:
        did = "dem_" + uuid.uuid4().hex[:12]
        planejado = round(float(it["qty"]) * mult, 4)
        conn.execute(
            """INSERT INTO vps_pick_demand(demand_id, tag_id, pick_tag_id, bom_id, item_key, descricao,
                 qty_planned, qty_picked, unit, state, critico, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (did, tag_id, pick_tag, it["bom_id"], it["item_key"], it["descricao"],
             planejado, 0, it["unit"], "PLANNED", it["critico"], store.now_iso()))
        criadas.append(_row("SELECT * FROM vps_pick_demand WHERE demand_id=?", (did,)) or {})

    engine.capture({"tag_id": tag_id, "action": "STRUCTURE_RELEASED", "owner": "PCP",
                    "payload": {"produto": produto, "itens": len(criadas), "qty": mult,
                                "pick_tag_id": pick_tag, "actor": actor}})
    return {"ok": True, "pick_tag_id": pick_tag, "produto": produto,
            "demands": criadas, "tag": store.get_tag(tag_id)}


def clear(tag_id: str, actor: str = "pcp") -> dict[str, Any]:
    """Apaga as demandas para reestruturar. Não apaga evento: o passado fica."""
    n = len(demands(tag_id))
    get_connection().execute("DELETE FROM vps_pick_demand WHERE tag_id=?", (tag_id,))
    if n:
        engine.capture({"tag_id": tag_id, "action": "STRUCTURE_REQUESTED", "owner": "PCP",
                        "payload": {"apagadas": n, "actor": actor, "motivo": "reestruturação"}})
    return {"ok": True, "apagadas": n}


# ── Separação: o que o PICKING confirma ─────────────────────────────
def set_demand(demand_id: str, qty_picked: float, actor: str = "supply") -> dict[str, Any] | None:
    """Confirma a separação de um item; fecha a lista quando tudo estiver ok."""
    d = _row("SELECT * FROM vps_pick_demand WHERE demand_id=?", (demand_id,))
    if d is None:
        return None
    q = max(0.0, float(qty_picked))
    estado = "DONE" if q >= float(d["qty_planned"]) else ("SHORT" if q > 0 else "PLANNED")
    get_connection().execute(
        "UPDATE vps_pick_demand SET qty_picked=?, state=?, closed_at=? WHERE demand_id=?",
        (q, estado, store.now_iso() if estado in ("DONE", "SHORT") else None, demand_id))

    if estado == "SHORT":
        # PICK_SHORT é a ação que o template marca como bloqueante: a fase para
        # até alguém resolver a falta. É o mesmo caminho do resto do sistema.
        engine.capture({"tag_id": d["tag_id"], "action": "PICK_SHORT", "owner": "Supply",
                        "payload": {"item": d["item_key"], "alvo": d["qty_planned"], "separado": q,
                                    "critico": bool(d["critico"]), "actor": actor}})
    restantes = [x for x in demands(d["tag_id"]) if x["state"] != "DONE"]
    if not restantes:
        engine.capture({"tag_id": d["tag_id"], "action": "PICK_COMPLETED", "owner": "Supply",
                        "payload": {"itens": len(demands(d["tag_id"])), "actor": actor}})
    return {"ok": True, "demand": _row("SELECT * FROM vps_pick_demand WHERE demand_id=?", (demand_id,)),
            "restantes": len(restantes)}


# ── Painel do módulo ────────────────────────────────────────────────
def fila() -> list[dict[str, Any]]:
    """OPs paradas na fase PCP — a fila de estruturação."""
    out = []
    for t in store.all_tags():
        if (t.get("current_phase") or "") != "PCP" or t.get("state") in ("COMPLETED", "ARCHIVED"):
            continue
        ds = demands(t["tag_id"])
        out.append({
            "tag_id": t["tag_id"], "natural_key": t.get("natural_key"), "segment": t.get("segment"),
            "entity_type": t.get("entity_type"), "state": t.get("state"),
            "template_id": t.get("template_id"), "estruturado": bool(ds), "itens": len(ds),
            "tem_estrutura": bool(bom(_produto_da_tag(t))),
        })
    return sorted(out, key=lambda x: (x["estruturado"], x["natural_key"] or ""))


def kpis() -> dict[str, Any]:
    todas = _rows("SELECT * FROM vps_pick_demand")
    abertas = [d for d in todas if d["state"] != "DONE"]
    curtas = [d for d in todas if d["state"] == "SHORT"]
    planejado = sum(float(d["qty_planned"]) for d in todas) or 0.0
    separado = sum(float(d["qty_picked"]) for d in todas) or 0.0
    f = fila()
    return {
        "CLD_PCP_Queue": len([x for x in f if not x["estruturado"]]),
        "CLD_PCP_Structured": len([x for x in f if x["estruturado"]]),
        "CLD_PCP_Demands_Open": len(abertas),
        "CLD_PCP_Shortages": len(curtas),
        "CLD_PCP_Critical_Short": len([d for d in curtas if d["critico"]]),
        "CLD_PCP_Fill_Rate": round(100 * separado / planejado, 1) if planejado else None,
        "CLD_PCP_Bom_Items": len(bom()),
    }
