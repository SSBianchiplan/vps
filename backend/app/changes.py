"""Gestão de alterações — leitura do log de mudanças do banco.

O `change_log` é escrito por trigger no PostgreSQL (app/db/change_log.sql):
toda linha inserida, alterada ou removida nas tabelas de negócio, com o antes,
o depois e quais campos mudaram. Este módulo só lê.

Em SQLite não existe change_log — lá a gestão de alterações é o `audit_event`
da aplicação. As funções devolvem `disponivel: False` em vez de estourar, e a
interface explica em vez de mostrar uma tabela vazia sem motivo.
"""
from __future__ import annotations

from typing import Any

from .db.database import _use_pg, get_connection


def disponivel() -> bool:
    if not _use_pg():
        return False
    try:
        r = get_connection().execute("SELECT to_regclass('change_log') AS t").fetchone()
        return bool(dict(r)["t"]) if r else False
    except Exception:  # noqa: BLE001
        return False


def _linhas(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    return [dict(r) for r in get_connection().execute(sql, params).fetchall()]


def listar(table: str | None = None, pk: str | None = None, actor: str | None = None,
           op: str | None = None, q: str | None = None, limit: int = 200) -> dict[str, Any]:
    """Mudanças mais recentes, com filtros. `q` busca na chave e no ator."""
    if not disponivel():
        return {"disponivel": False, "motivo": "runtime em SQLite — a gestão de alterações exige PostgreSQL",
                "changes": [], "count": 0}
    onde, params = [], []
    if table:
        onde.append("table_name = %s"); params.append(table)
    if pk:
        onde.append("pk = %s"); params.append(pk)
    if actor:
        onde.append("actor = %s"); params.append(actor)
    if op:
        onde.append("op = %s"); params.append(op.upper()[:1])
    if q:
        onde.append("(pk ILIKE %s OR actor ILIKE %s OR origem ILIKE %s)")
        params += [f"%{q}%"] * 3
    sql = "SELECT change_id, changed_at, table_name, op, pk, actor, origem, changed_fields," \
          " before_json, after_json FROM change_log"
    if onde:
        sql += " WHERE " + " AND ".join(onde)
    sql += " ORDER BY change_id DESC LIMIT %s"
    params.append(min(int(limit), 1000))
    linhas = _linhas(sql, tuple(params))
    for l in linhas:
        l["changed_at"] = str(l["changed_at"])
        l["changed_fields"] = list(l.get("changed_fields") or [])
    return {"disponivel": True, "changes": linhas, "count": len(linhas)}


def resumo() -> dict[str, Any]:
    """Contagens para o painel: por tabela, por operação, por ator, por dia."""
    if not disponivel():
        return {"disponivel": False, "motivo": "runtime em SQLite — a gestão de alterações exige PostgreSQL"}
    return {
        "disponivel": True,
        "total": _linhas("SELECT COUNT(*) AS n FROM change_log")[0]["n"],
        "por_tabela": _linhas("SELECT table_name AS k, COUNT(*) AS n FROM change_log GROUP BY 1 ORDER BY 2 DESC LIMIT 20"),
        "por_operacao": _linhas("SELECT op AS k, COUNT(*) AS n FROM change_log GROUP BY 1 ORDER BY 2 DESC"),
        "por_ator": _linhas("SELECT COALESCE(actor, '(fora da aplicação)') AS k, COUNT(*) AS n"
                            " FROM change_log GROUP BY 1 ORDER BY 2 DESC LIMIT 20"),
        "por_dia": _linhas("SELECT to_char(changed_at, 'YYYY-MM-DD') AS k, COUNT(*) AS n"
                           " FROM change_log GROUP BY 1 ORDER BY 1 DESC LIMIT 14"),
        "tabelas_monitoradas": [r["k"] for r in _linhas(
            "SELECT event_object_table AS k FROM information_schema.triggers"
            " WHERE trigger_name='trg_change_log' GROUP BY 1 ORDER BY 1")],
    }


def historico(table: str, pk: str, limit: int = 100) -> dict[str, Any]:
    """Linha do tempo de UMA linha: útil para 'por que este card está assim?'."""
    return listar(table=table, pk=pk, limit=limit)
