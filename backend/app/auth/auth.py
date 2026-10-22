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
from ..logging_conf import get_logger

ROLES = ("admin", "operador", "view")
# Perfis operacionais (o que um "operador" governa) — definidos em vps/rbac.py.
PERFIS = ("Operations", "Supply", "Quality", "Projects")

log = get_logger("visiondesk.auth")

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
        "SELECT operator_id, name, role, perfil, active, (pin_hash IS NOT NULL) AS has_pin, created_at "
        "FROM vps_access ORDER BY created_at DESC").fetchall()
    out = []
    for r in rows:
        d = dict(r); d["active"] = bool(d["active"]); d["has_pin"] = bool(d["has_pin"])
        d["has_face"] = _has_face(d["operator_id"])
        out.append(d)
    return out


def upsert_user(name: str, role: str, operator_id: str | None = None, pin: str | None = None,
                perfil: str | None = None) -> dict[str, Any]:
    if role not in ROLES:
        return {"ok": False, "message": "papel inválido (admin|operador|view)"}
    if perfil is not None and perfil not in PERFIS:
        return {"ok": False, "message": f"perfil operacional inválido ({'|'.join(PERFIS)})"}
    oid = operator_id or ("op_" + name.strip().lower().replace(" ", "_"))
    # Um cadastro, duas faces: quem tem login é operador do chão de fábrica.
    # Antes esta escrita falhava calada (except: pass) e a tela de Operadores
    # mostrava só os dois de exemplo, enquanto Acesso & Regras tinha seis
    # usuários — duas listas de pessoas que deveriam ser a mesma.
    try:
        from ..vps import operators
        atual = operators.get_operator(oid) or {}
        operators.upsert_operator({
            "operator_id": oid, "name": name,
            # papel do operador segue o perfil operacional quando houver;
            # senão, traduz o papel de acesso para o vocabulário do chão.
            "role": perfil or atual.get("role") or {"admin": "Supervisor", "operador": "Operador", "view": "Visitante"}.get(role, "Operador"),
            "matricula": atual.get("matricula"), "badge": atual.get("badge"),
            "stations": atual.get("stations"), "skills": atual.get("skills"),
            "shift": atual.get("shift"), "status": atual.get("status", "ativo"),
        })
    except Exception:  # noqa: BLE001
        log.exception("usuário %s criado sem espelho em operadores", oid)
    ph = _hash(pin) if pin else None
    conn = get_connection()
    conn.execute(
        "INSERT INTO vps_access(operator_id,name,role,pin_hash,active,created_at,perfil) VALUES (?,?,?,?,1,?,?)"
        " ON CONFLICT(operator_id) DO UPDATE SET name=excluded.name, role=excluded.role,"
        " pin_hash=COALESCE(excluded.pin_hash, vps_access.pin_hash),"
        " perfil=COALESCE(excluded.perfil, vps_access.perfil)",
        (oid, name, role, ph, _now(), perfil))
    _event("USER_UPSERT", oid, summary=f"usuário {name} ({role}{' · ' + perfil if perfil else ''})")
    return {"ok": True, "operator_id": oid, "name": name, "role": role, "perfil": perfil}


def sync_operators() -> int:
    """Garante que todo usuário do sistema tenha a face de operador.

    Roda no boot e é idempotente. Existe porque os usuários criados ANTES do
    vínculo ficaram só em vps_access: a tela de Operadores mostrava três
    pessoas de exemplo enquanto Acesso & Regras tinha seis usuários reais.
    """
    n = 0
    try:
        from ..vps import operators
        for u in users():
            if operators.get_operator(u["operator_id"]):
                continue
            operators.upsert_operator({
                "operator_id": u["operator_id"], "name": u["name"],
                "role": u.get("perfil") or {"admin": "Supervisor", "operador": "Operador", "view": "Visitante"}.get(u["role"], "Operador"),
                "status": "ativo" if u.get("active", True) else "inativo",
            })
            n += 1
        if n:
            log.info("operadores espelhados a partir de usuários: %d", n)
    except Exception:  # noqa: BLE001
        log.exception("falha ao espelhar usuários em operadores (não fatal)")
    return n


def set_perfil(oid: str, perfil: str | None) -> dict[str, Any]:
    """Perfil operacional (Operations|Supply|Quality|Projects) — o que o operador governa."""
    if perfil is not None and perfil not in PERFIS:
        return {"ok": False, "message": f"perfil inválido ({'|'.join(PERFIS)})"}
    get_connection().execute("UPDATE vps_access SET perfil=? WHERE operator_id=?", (perfil, oid))
    _event("USER_PERFIL_SET", oid, summary=f"perfil operacional → {perfil or '—'}")
    return {"ok": True, "perfil": perfil}


def set_role(oid: str, role: str) -> dict[str, Any]:
    if role not in ROLES:
        return {"ok": False, "message": "papel inválido"}
    get_connection().execute("UPDATE vps_access SET role=? WHERE operator_id=?", (role, oid))
    _event("USER_ROLE_SET", oid, summary=f"papel → {role}")
    return {"ok": True}


def set_active(oid: str, active: bool) -> dict[str, Any]:
    get_connection().execute("UPDATE vps_access SET active=? WHERE operator_id=?", (1 if active else 0, oid))
    # espelha no master data: desativar o login desativa a pessoa no chão
    try:
        from ..vps import operators
        operators.set_status(oid, "ativo" if active else "inativo")
    except Exception:  # noqa: BLE001
        pass
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


def dev_login() -> dict[str, Any]:
    """Login de conveniência p/ desenvolvimento — garante um admin 'DEV Admin'
    (op_dev, ativo) e abre uma sessão real (token). Sempre auditado como alerta.

    O gate de ambiente fica na rota (routes_auth): só é permitido em modo aberto
    (sem VISIONDESK_API_KEY). Nunca deve ficar acessível em produção.
    """
    oid = "op_dev"
    if not _access(oid):
        upsert_user("DEV Admin", "admin", operator_id=oid)
    else:
        get_connection().execute("UPDATE vps_access SET role='admin', active=1 WHERE operator_id=?", (oid,))
    _event("LOGIN_DEV", oid, severity="alerta", summary="login DEV Admin (modo aberto/dev)")
    return _new_session(oid, "DEV Admin", "admin", "dev")


def session(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    # JOIN com vps_access: o perfil operacional e o "ativo" valem AGORA, nao no
    # momento do login — desativar um usuario derruba a sessao dele na hora.
    r = get_connection().execute(
        "SELECT s.operator_id, s.name, a.role, s.method, a.perfil, a.active, s.created_at"
        " FROM auth_session s LEFT JOIN vps_access a ON a.operator_id=s.operator_id WHERE s.token=?",
        (token,)).fetchone()
    if not r:
        return None
    d = dict(r)
    # Sessão órfã (usuário removido de vps_access) não vale: antes o LEFT JOIN
    # devolvia role=None e o token seguia "autenticado".
    if not d.get("active") or not d.get("role"):
        return None
    # Validade (auditoria out/2026): o token não expirava nunca.
    if _expired(d.pop("created_at", None)):
        return None
    d.pop("active", None)
    return d


def _expired(created_at: Any) -> bool:
    from ..config import get_settings
    ttl = get_settings().session_ttl_hours
    if not ttl or ttl <= 0 or not created_at:
        return False
    try:
        t = created_at if isinstance(created_at, datetime) else datetime.fromisoformat(str(created_at))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - t).total_seconds() > ttl * 3600
    except Exception:  # noqa: BLE001
        return False


def logout(token: str | None) -> dict[str, Any]:
    if token:
        get_connection().execute("DELETE FROM auth_session WHERE token=?", (token,))
    return {"ok": True}


def role_of_token(token: str | None) -> str | None:
    s = session(token)
    return s["role"] if s else None
