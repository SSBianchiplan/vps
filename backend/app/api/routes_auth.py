"""Login (FaceID/PIN), sessão e controle de acesso (RBAC: admin/operador/view)."""
from __future__ import annotations

import threading
import time
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import BaseModel

from ..auth import auth
from . import guard

router = APIRouter(prefix="/auth", tags=["auth"])


def _require_admin(token: str | None) -> None:
    if auth.bootstrap_needed():
        return  # 1ª configuração: sem admin ainda
    if auth.role_of_token(token) != "admin":
        raise HTTPException(status_code=403, detail={"code": "forbidden", "message": "requer admin"})


# ── limite de tentativas de login (por IP) ───────────────────────────
# PIN é curto: sem limite, a força bruta é trivial. 10 falhas em 15 min por IP
# bloqueiam novas tentativas desse IP até a janela passar. Em memória (1 worker).
_FAIL_MAX = 10
_FAIL_WINDOW_S = 15 * 60
_fails: dict[str, list[float]] = {}
_fails_lock = threading.Lock()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "?"


def _check_throttle(request: Request) -> None:
    ip = _client_ip(request)
    now = time.monotonic()
    with _fails_lock:
        recent = [t for t in _fails.get(ip, []) if now - t < _FAIL_WINDOW_S]
        _fails[ip] = recent
        if len(recent) >= _FAIL_MAX:
            raise HTTPException(status_code=429, detail={
                "code": "too_many_attempts",
                "message": "muitas tentativas de login — aguarde alguns minutos"})


def _register(request: Request, response: Response, res: dict[str, Any]) -> dict[str, Any]:
    """Login OK → grava o cookie de sessão; falha → conta para o limite."""
    if res.get("ok") and res.get("token"):
        guard.set_session_cookie(response, request, res["token"])
        with _fails_lock:
            _fails.pop(_client_ip(request), None)
    else:
        with _fails_lock:
            _fails.setdefault(_client_ip(request), []).append(time.monotonic())
    return res


class FaceLoginIn(BaseModel):
    image_b64: str


class PinLoginIn(BaseModel):
    operator_id: str
    pin: str


class BootstrapIn(BaseModel):
    name: str
    pin: str


class UserIn(BaseModel):
    name: str
    role: str = "view"
    operator_id: str | None = None
    pin: str | None = None
    perfil: str | None = None          # Operations | Supply | Quality | Projects (so p/ operador)
    face_b64: str | None = None       # cadastro de face opcional no ato


class RoleIn(BaseModel):
    role: str


class PerfilIn(BaseModel):
    perfil: str | None = None


class ActiveIn(BaseModel):
    active: bool


# ── sessão / login ───────────────────────────────────────────────────
@router.get("/state")
def state() -> dict[str, Any]:
    return {"bootstrap_needed": auth.bootstrap_needed(), "roles": list(auth.ROLES)}


@router.get("/me")
def me(request: Request, response: Response,
       x_auth_token: str | None = Header(default=None)) -> dict[str, Any]:
    s = auth.session(x_auth_token)
    # Quem já estava logado antes do cookie existir guarda o token só no
    # localStorage e o manda aqui no cabeçalho: devolve o cookie para que o
    # resto do app (fetch sem cabeçalho, <img>, WebSocket) siga autenticado.
    if s and x_auth_token and request.cookies.get(guard.COOKIE_NAME) != x_auth_token:
        guard.set_session_cookie(response, request, x_auth_token)
    if not s and request.cookies.get(guard.COOKIE_NAME):
        guard.clear_session_cookie(response)
    return {"authenticated": bool(s), "user": s}


@router.post("/login/face")
def login_face(body: FaceLoginIn, request: Request, response: Response) -> dict[str, Any]:
    _check_throttle(request)
    return _register(request, response, auth.login_face(body.image_b64))


@router.post("/login/pin")
def login_pin(body: PinLoginIn, request: Request, response: Response) -> dict[str, Any]:
    _check_throttle(request)
    return _register(request, response, auth.login_pin(body.operator_id, body.pin))


@router.post("/bootstrap")
def bootstrap(body: BootstrapIn, request: Request, response: Response) -> dict[str, Any]:
    _check_throttle(request)
    return _register(request, response, auth.bootstrap_admin(body.name, body.pin))


@router.post("/dev-login")
def dev_login(request: Request, response: Response) -> dict[str, Any]:
    """Atalho de DEV: entra como admin sem PIN.

    Exige DOIS gates, porque o endpoint entrega uma sessão de admin sem
    credencial nenhuma: qualquer um que alcance a URL seria admin. A API key
    sozinha não bastava — num deploy público sem API key (o frontend não manda
    X-API-Key) o atalho ficava aberto na internet. Por isso vale também
    VISIONDESK_DEV_LOGIN=false, que é o que a instalação no VPS usa.
    """
    from ..config import get_settings

    s = get_settings()
    # Terceiro gate (auditoria out/2026): só de loopback. Atrás do Caddy o
    # uvicorn resolve o IP real pelo X-Forwarded-For, então quem vem da
    # internet nunca é 127.0.0.1 — mesmo que o .env esqueça DEV_LOGIN=false.
    local = (request.client.host if request.client else "") in ("127.0.0.1", "::1", "localhost")
    if s.api_key or not s.dev_login or not local:
        raise HTTPException(status_code=403, detail={"code": "forbidden", "message": "dev-login desabilitado (produção)"})
    res = auth.dev_login()
    if res.get("token"):
        guard.set_session_cookie(response, request, res["token"])
    return res


@router.post("/logout")
def logout(response: Response, x_auth_token: str | None = Header(default=None)) -> dict[str, Any]:
    guard.clear_session_cookie(response)
    return auth.logout(x_auth_token)


@router.get("/matrix")
def matrix() -> dict[str, Any]:
    return {"matrix": auth.MATRIX, "roles": list(auth.ROLES)}


# ── usuários (admin) ─────────────────────────────────────────────────
@router.get("/users")
def list_users(x_auth_token: str | None = Header(default=None)) -> dict[str, Any]:
    _require_admin(x_auth_token)
    return {"users": auth.users()}


@router.post("/users")
def create_user(body: UserIn, x_auth_token: str | None = Header(default=None)) -> dict[str, Any]:
    _require_admin(x_auth_token)
    res = auth.upsert_user(body.name, body.role, body.operator_id, body.pin, body.perfil)
    if res.get("ok") and body.face_b64:        # cadastro de face consentido no ato
        from ..biometrics import face
        f = face.enroll(res["operator_id"], body.name, body.face_b64, consent=True)
        res["face"] = f
    return res


@router.post("/users/{operator_id}/role")
def user_role(operator_id: str, body: RoleIn, x_auth_token: str | None = Header(default=None)) -> dict[str, Any]:
    _require_admin(x_auth_token)
    return auth.set_role(operator_id, body.role)


@router.post("/users/{operator_id}/perfil")
def user_perfil(operator_id: str, body: PerfilIn, x_auth_token: str | None = Header(default=None)) -> dict[str, Any]:
    # Perfil operacional: qual contexto do chao de fabrica este usuario governa.
    _require_admin(x_auth_token)
    return auth.set_perfil(operator_id, body.perfil)


@router.get("/perfis")
def perfis() -> dict[str, Any]:
    # Os 4 perfis operacionais e o que cada um pode fazer (a UI monta a tabela daqui).
    from ..vps import rbac
    return {"perfis": rbac.perfis(), "contextos": {k: sorted(v) for k, v in rbac.CONTEXT_ACTIONS.items()}}


@router.post("/users/{operator_id}/active")
def user_active(operator_id: str, body: ActiveIn, x_auth_token: str | None = Header(default=None)) -> dict[str, Any]:
    _require_admin(x_auth_token)
    return auth.set_active(operator_id, body.active)


@router.post("/users/{operator_id}/face")
def user_face(operator_id: str, body: FaceLoginIn, x_auth_token: str | None = Header(default=None)) -> dict[str, Any]:
    _require_admin(x_auth_token)
    from ..biometrics import face
    u = next((u for u in auth.users() if u["operator_id"] == operator_id), None)
    return face.enroll(operator_id, (u or {}).get("name") or operator_id, body.image_b64, consent=True)


@router.delete("/users/{operator_id}")
def remove_user(operator_id: str, x_auth_token: str | None = Header(default=None)) -> dict[str, Any]:
    _require_admin(x_auth_token)
    return auth.delete_user(operator_id)
