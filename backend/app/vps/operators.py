"""Operadores — master data (SCD2-lite) + identificação na captura.

`operator_id` vincula cada ação a um responsável (P05), não vigia a pessoa (LGPD).
Inativar, nunca apagar. Sessão por estação: o operador logado carimba os eventos.
Ver VPS_Operadores_Cadastros_Usabilidade.md.
"""
from __future__ import annotations

from typing import Any

from ..db.database import get_connection
from .store import now_iso

# sessão (em memória): estação/source → operator_id logado
_current: dict[str, str] = {}


def list_operators(status: str | None = None) -> list[dict[str, Any]]:
    sql = "SELECT * FROM vps_operator"
    params: list[Any] = []
    if status:
        sql += " WHERE status=?"
        params.append(status)
    sql += " ORDER BY name"
    return [dict(r) for r in get_connection().execute(sql, params).fetchall()]


def get_operator(operator_id: str) -> dict[str, Any] | None:
    r = get_connection().execute("SELECT * FROM vps_operator WHERE operator_id=?", (operator_id,)).fetchone()
    return dict(r) if r else None


def by_badge(badge: str) -> dict[str, Any] | None:
    r = get_connection().execute("SELECT * FROM vps_operator WHERE badge=? AND status='ativo'", (badge,)).fetchone()
    return dict(r) if r else None


def upsert_operator(d: dict[str, Any]) -> dict[str, Any]:
    oid = d.get("operator_id") or ("op_" + (d.get("matricula") or d["name"]).strip().lower().replace(" ", "_"))
    get_connection().execute(
        """INSERT INTO vps_operator(operator_id, name, matricula, badge, role, stations, skills, shift, status, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(operator_id) DO UPDATE SET
             name=excluded.name, matricula=excluded.matricula, badge=excluded.badge, role=excluded.role,
             stations=excluded.stations, skills=excluded.skills, shift=excluded.shift, status=excluded.status""",
        (oid, d["name"], d.get("matricula"), d.get("badge"), d.get("role", "Operador"),
         d.get("stations"), d.get("skills"), d.get("shift"), d.get("status", "ativo"), now_iso()),
    )
    return get_operator(oid)  # type: ignore[return-value]


def set_status(operator_id: str, status: str) -> bool:
    cur = get_connection().execute("UPDATE vps_operator SET status=? WHERE operator_id=?", (status, operator_id))
    return bool(cur.rowcount)


# ── Identificação na captura (sessão de estação) ─────────────────────
def identify(station: str, operator_id: str | None = None, badge: str | None = None) -> dict[str, Any]:
    if badge and not operator_id:
        op = by_badge(badge)
        operator_id = op["operator_id"] if op else None
    if operator_id:
        _current[station] = operator_id
    else:
        _current.pop(station, None)
    return {"station": station, "operator_id": _current.get(station)}


def current(station: str) -> str | None:
    return _current.get(station)


def sessions() -> dict[str, str]:
    return dict(_current)


def seed() -> dict[str, Any]:
    for d in [
        {"operator_id": "u123", "name": "J. Silva", "matricula": "M-123", "badge": "QR-U123", "role": "Operador", "stations": "ALMOX-02", "skills": "picking,conferencia", "shift": "T1"},
        {"operator_id": "u204", "name": "M. Souza", "matricula": "M-204", "badge": "QR-U204", "role": "Supervisor", "stations": "ALMOX-02,LINHA-01", "skills": "supervisao", "shift": "T1"},
        {"operator_id": "u311", "name": "R. Lima", "matricula": "M-311", "badge": "QR-U311", "role": "Operador", "stations": "LINHA-01", "skills": "montagem", "shift": "T2", "status": "inativo"},
    ]:
        upsert_operator(d)
    return {"operators": len(list_operators())}
