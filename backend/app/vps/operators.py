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
    linhas = [dict(r) for r in get_connection().execute(sql, params).fetchall()]
    return [{**o, **_acesso(o["operator_id"])} for o in linhas]


def _acesso(operator_id: str) -> dict[str, Any]:
    """Face de ACESSO do mesmo cadastro: papel de login, perfil e se tem PIN/face.

    A tela de Operadores precisa mostrar se aquela pessoa entra no sistema e
    com que poder — senão o vínculo usuário↔operador existe no banco e não
    aparece para quem opera.
    """
    r = get_connection().execute(
        "SELECT role, perfil, active, (pin_hash IS NOT NULL) AS has_pin FROM vps_access WHERE operator_id=?",
        (operator_id,)).fetchone()
    if not r:
        return {"tem_login": False, "login_role": None, "perfil": None, "login_ativo": None, "tem_pin": False, "tem_face": False}
    d = dict(r)
    f = get_connection().execute(
        "SELECT 1 AS x FROM vps_face_template WHERE operator_id=? AND is_current=1", (operator_id,)).fetchone()
    return {"tem_login": True, "login_role": d["role"], "perfil": d.get("perfil"),
            "login_ativo": bool(d["active"]), "tem_pin": bool(d["has_pin"]), "tem_face": bool(f)}


def opcoes() -> dict[str, list[str]]:
    """Valores JÁ existentes em cada coluna — alimenta as listas segmentadas.

    A tela oferece o que a base tem (estações, turnos, skills, papéis) em vez
    de campo de texto livre: digitar "ALMOX 02" onde todo mundo escreveu
    "ALMOX-02" cria uma estação fantasma que nenhuma consulta encontra.
    """
    def distintos(coluna: str, split_csv: bool = False) -> list[str]:
        vals: set[str] = set()
        for r in get_connection().execute(f"SELECT DISTINCT {coluna} AS v FROM vps_operator WHERE {coluna} IS NOT NULL").fetchall():
            v = (dict(r)["v"] or "").strip()
            if not v:
                continue
            if split_csv:
                vals.update(x.strip() for x in v.split(",") if x.strip())
            else:
                vals.add(v)
        return sorted(vals)

    from ..vps import rbac
    return {
        "role": sorted(set(distintos("role")) | {"Operador", "Supervisor", "Líder", "Manutenção", "Qualidade", "Visitante"}),
        "stations": sorted(set(distintos("stations", True)) | {"ALMOX-02", "LINHA-01", "CEL-MONT-01", "QC-01"}),
        "skills": distintos("skills", True) or ["picking", "conferencia", "montagem", "inspecao", "supervisao"],
        "shift": sorted(set(distintos("shift")) | {"T1", "T2", "T3", "ADM"}),
        "status": ["ativo", "inativo"],
        "perfil": list(rbac.PERFIS_OPERACIONAIS.keys()),
        "login_role": ["admin", "operador", "view"],
    }


def get_operator(operator_id: str) -> dict[str, Any] | None:
    r = get_connection().execute("SELECT * FROM vps_operator WHERE operator_id=?", (operator_id,)).fetchone()
    if not r:
        return None
    return {**dict(r), **_acesso(operator_id)}


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
