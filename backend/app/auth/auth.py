"""Autenticação + RBAC do sistema (login FaceID/PIN, papéis admin/operador/view).

Usuário = operador (vps_operator) + papel de ACESSO (vps_access). Login por face
(reusa biometrics.face.identify — template, não foto) ou PIN (fallback, LGPD §9).
Sessão por token (auth_session). Toda autenticação é auditada na trilha.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Any

from ..db.database import get_connection

ROLES = ("admin", "operador", "view")

# Matriz de capacidades por papel (exibida no módulo Acesso & Regras).
MATRIX = [
    {"cap": "Ver painéis / cockpit / eventos", "admin": True, "operador": True, "view": True},
    {"cap": "Operar (estação, análise CV, scan, captura)", "admin": True, "operador": True, "view": False},
    {"cap": "Planejar / APS / projetos", "admin": True, "operador": True, "view": False},
    {"cap": "Cadastrar/medir (metrologia, termografia, facial)", "admin": True, "operador": True, "view": False},
    {"cap": "Bases de dados / config", "admin": True, "operador": False, "view": False},
    {"cap": "Controle de acesso (usuários/papéis)", "admin": True, "operador": False, "view": False},
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(pin: str) -> str:
    return hashlib.sha256(("vd$" + pin).encode()).hexdigest()


def _event(action: str, oid: str | None, *, severity: str = "info", summary: str = "") -> None:
    try:
        from .. import audit
        audit.record("SYSTEM", action, severity=severity, actor=oid or "auth",
                     entity_type="user", entity_id=oid, summary=summary)
    except Exception:  # noqa: BLE001
        pass


# ── Usuários (operador + papel de acesso) ────────────────────────────
def _has_face(oid: str) -> bool:
    r = get_connection().execute("SELECT 1 FROM vps_face_template WHERE operator_id=? AND is_current=1", (oid,)).fetchone()
    return bool(r)


def users() -> list[dict[str, Any]]:
    rows = get_connection().execute(
        "SELECT operator_id, name, role, active, (pin_hash IS NOT NULL) AS has_pin, created_at "
        "FROM vps_access ORDER BY created_at DESC").fetchall()
    out = []
    for r in rows:
        d = dict(r); d["active"] = bool(d["active"]); d["has_pin"] = bool(d["has_pin"])
        d["has_face"] = _has_face(d["operator_id"])
        out.append(d)
    return out


def upsert_user(name: str, role: str, operator_id: str | None = None, pin: str | None = None) -> dict[str, Any]:
    if role not in ROLES:
        return {"ok": False, "message": "papel inválido (admin|operador|view)"}
    oid = operator_id or ("op_" + name.strip().lower().replace(" ", "_"))
    # cria/atualiza o operador (master data) também
    try:
        from ..vps import operators
        operators.upsert_operator({"operator_id": oid, "name": name, "role": role})
    except Exception:  # noqa: BLE001
        pass
    ph = _hash(pin) if pin else None
    conn = get_connection()
    conn.execute(
        "INSERT INTO vps_access(operator_id,name,role,pin_hash,active,created_at) VALUES (?,?,?,?,1,?)"
        " ON CONFLICT(operator_id) DO UPDATE SET name=excluded.name, role=excluded.role,"
        " pin_hash=COALESCE(excluded.pin_hash, vps_access.pin_hash)",
        (oid, name, role, ph, _now()))
    _event("USER_UPSERT", oid, summary=f"usuário {name} ({role})")
    return {"ok": True, "operator_id": oid, "name": name, "role": role}


def set_role(oid: str, role: str) -> dict[str, Any]:
    if role not in ROLES:
        return {"ok": False, "message": "papel inválido"}
    get_connection().execute("UPDATE vps_access SET role=? WHERE operator_id=?", (role, oid))
    _event("USER_ROLE_SET", oid, summary=f"papel → {role}")
    return {"ok": True}


def set_active(oid: str, active: bool) -> dict[str, Any]:
    get_connection().execute("UPDATE vps_access SET active=? WHERE operator_id=?", (1 if active else 0, oid))
    _event("USER_ACTIVE_SET", oid, severity="alerta" if not active else "info",
           summary=f"usuário {'ativado' if active else 'desativado'}")
    return {"ok": True}


def set_pin(oid: str, pin: str) -> dict[str, Any]:
    get_connection().execute("UPDATE vps_access SET pin_hash=? WHERE operator_id=?", (_hash(pin), oid))
    return {"ok": True}


def delete_user(oid: str) -> dict[str, Any]:
    get_connection().execute("DELETE FROM vps_access WHERE operator_id=?", (oid,))
    _event("USER_DELETE", oid, severity="alerta", summary="usuário removido do acesso")
    return {"ok": True}


def _access(oid: str) -> dict[str, Any] | None:
    r = get_connection().execute("SELECT * FROM vps_access WHERE operator_id=?", (oid,)).fetchone()
    return dict(r) if r else None


# ── Bootstrap (primeiro admin) ───────────────────────────────────────
def bootstrap_needed() -> bool:
    r = get_connection().execute("SELECT COUNT(*) AS n FROM vps_access WHERE role='admin' AND active=1").fetchone()
    return int(dict(r)["n"]) == 0


def bootstrap_admin(name: str, pin: str) -> dict[str, Any]:
    if not bootstrap_needed():
        return {"ok": False, "message": "já existe admin — peça a um admin para criar usuários"}
    if not pin:
        return {"ok": False, "message": "defina um PIN para o admin"}
    u = upsert_user(name, "admin", pin=pin)
    _event("BOOTSTRAP_ADMIN", u["operator_id"], summary=f"primeiro admin criado: {name}")
    return _new_session(u["operator_id"], name, "admin", "bootstrap")


# ── Sessão / login ───────────────────────────────────────────────────
def _new_session(oid: str, name: str, role: str, method: str) -> dict[str, Any]:
    token = secrets.token_hex(20)
    get_connection().execute(
        "INSERT INTO auth_session(token,operator_id,name,role,method,created_at) VALUES (?,?,?,?,?,?)",
        (token, oid, name, role, method, _now()))
    return {"ok": True, "token": token, "user": {"operator_id": oid, "name": name, "role": role, "method": method}}


def login_face(image_b64: str) -> dict[str, Any]:
    from ..biometrics import face
    r = face.identify(image_b64)
    if not r.get("ok"):
        return {"ok": False, "message": r.get("message", "falha na captura")}
    if not r.get("matched"):
        _event("LOGIN_DENIED", None, severity="alerta", summary="face não reconhecida")
        return {"ok": False, "message": "face não reconhecida — use PIN ou peça cadastro", "live": r.get("live")}
    oid = r["operator_id"]
    acc = _access(oid)
    if not acc or not acc["active"]:
        _event("LOGIN_DENIED", oid, severity="alerta", summary="usuário sem acesso/ inativo")
        return {"ok": False, "message": "operador identificado mas sem acesso liberado"}
    _event("LOGIN_OK", oid, severity="ok", summary=f"login facial: {acc['name']} ({acc['role']})")
    return _new_session(oid, acc["name"], acc["role"], "face")


def login_pin(operator_id: str, pin: str) -> dict[str, Any]:
    acc = _access(operator_id)
    if not acc or not acc["active"]:
        return {"ok": False, "message": "usuário inexistente/inativo"}
    if not acc.get("pin_hash") or acc["pin_hash"] != _hash(pin):
        _event("LOGIN_DENIED", operator_id, severity="alerta", summary="PIN incorreto")
        return {"ok": False, "message": "PIN incorreto"}
    _event("LOGIN_OK", operator_id, severity="ok", summary=f"login PIN: {acc['name']} ({acc['role']})")
    return _new_session(operator_id, acc["name"], acc["role"], "pin")


def session(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    r = get_connection().execute(
        "SELECT operator_id, name, role, method FROM auth_session WHERE token=?", (token,)).fetchone()
    return dict(r) if r else None


def logout(token: str | None) -> dict[str, Any]:
    if token:
        get_connection().execute("DELETE FROM auth_session WHERE token=?", (token,))
    return {"ok": True}


def role_of_token(token: str | None) -> str | None:
    s = session(token)
    return s["role"] if s else None
