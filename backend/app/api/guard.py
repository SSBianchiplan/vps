"""Portão de autenticação da API (auditoria out/2026, achado C3).

ANTES: só /api/changes e uns poucos endpoints conferiam sessão. O resto da API
(câmeras, PTZ, gravação, WhatsApp, biometria, ffmpeg de teste...) respondia a
qualquer um na internet, e /docs + /openapi.json listavam tudo.

AGORA:
  * ``SessionCookieBridge`` (ASGI): o login grava a sessão num cookie HttpOnly
    (``vd_session``). Quando o pedido chega SEM ``X-Auth-Token`` e COM o cookie,
    a ponte copia o cookie para o cabeçalho. Assim todo o código que já lia
    ``X-Auth-Token`` (rbac.current_role, _exige_sessao, _publica_ator...) passa a
    enxergar a sessão também em fetch sem cabeçalho, <img src=".../mjpeg"> e
    WebSocket, que não conseguem mandar cabeçalho próprio. O frontend publicado
    não precisa ser recompilado.
  * ``require_session``: dependência GLOBAL (FastAPI(dependencies=[...])) que
    vale para toda rota HTTP e WebSocket. Fora da lista PUBLIC, sem sessão válida
    → 401 (WebSocket: fecha com 1008). Depois aplica o papel mínimo:
      - leitura (GET/HEAD): qualquer papel (admin, operador, view);
      - escrita (POST/PUT/PATCH/DELETE): operador ou admin;
      - rotas ADMIN: só admin (configuração, WhatsApp, bancos, cadastro de
        câmeras com credencial, ffmpeg de teste, varredura de rede...).
  * Pedido de escrita autenticado por cookie com ``Origin`` de outro site → 403
    (CSRF), além do SameSite=Strict do cookie.
"""
from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlsplit

from fastapi import HTTPException, WebSocketException
from starlette.requests import HTTPConnection

from ..config import get_settings

COOKIE_NAME = "vd_session"

# (método, caminho) liberados sem sessão: o que a tela de login precisa ANTES de
# existir sessão, mais a sonda de saúde. Nada aqui devolve dado de negócio.
PUBLIC: set[tuple[str, str]] = {
    ("GET", "/api/health"),
    ("GET", "/api/capabilities"),     # config pública mínima (modos/motores disponíveis)
    ("GET", "/api/auth/state"),
    ("GET", "/api/auth/me"),          # responde {"authenticated": false} sem sessão
    ("POST", "/api/auth/login/face"),
    ("POST", "/api/auth/login/pin"),
    ("POST", "/api/auth/bootstrap"),  # só funciona enquanto não existe admin
    ("POST", "/api/auth/dev-login"),  # a própria rota recusa em produção
    ("POST", "/api/auth/logout"),
}

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
ROLES_WRITE = {"admin", "operador"}

# Prefixos que exigem admin. "*" = qualquer método; "W" = só escrita.
ADMIN_RULES: list[tuple[str, str]] = [
    ("*", "/api/notify/whatsapp/config"),   # destinatários (dado pessoal) e token
    ("*", "/api/notify/whatsapp/test"),     # envia mensagem com o token da empresa
    ("*", "/api/databases"),
    ("W", "/api/aerial/test"),              # publica stream com ffmpeg
    ("*", "/api/cameras/scan"),             # varredura da rede local
    ("W", "/api/cameras/saved"),            # cadastro/remoção de câmera com senha
    ("W", "/api/config"),                   # bancos/config = admin (matriz de acesso)
    ("W", "/api/events/sync-pg"),
    ("W", "/api/iamac/model"),
    ("W", "/api/iamac/reindex"),
    ("W", "/api/automation/asset"),
    ("W", "/api/automation/synoptic"),
]

# Escritas que um papel "view" pode fazer (não alteram estado de negócio).
VIEW_WRITE_OK: set[tuple[str, str]] = {
    ("POST", "/api/iamac/ask"),
    ("POST", "/api/iamac/feedback"),
    ("POST", "/api/config/validate_link"),
}


def _match(prefix: str, path: str) -> bool:
    return path == prefix or path.startswith(prefix.rstrip("/") + "/")


def needs_admin(method: str, path: str) -> bool:
    for m, prefix in ADMIN_RULES:
        if (m == "*" or (m == "W" and method not in SAFE_METHODS)) and _match(prefix, path):
            return True
    return False


def token_of(conn: HTTPConnection) -> str | None:
    return conn.headers.get("x-auth-token") or conn.cookies.get(COOKIE_NAME) or None


def _origin_ok(conn: HTTPConnection) -> bool:
    """Escrita autenticada por cookie: a origem tem de ser o próprio site
    (ou uma das VISIONDESK_CORS_ORIGINS). Sem Origin/Referer, aceita (curl,
    navegadores antigos) — o cookie SameSite=Strict já não sai de outro site."""
    origin = conn.headers.get("origin") or conn.headers.get("referer")
    if not origin:
        return True
    o = urlsplit(origin)
    if not o.netloc:
        return True
    host = conn.headers.get("host", "")
    if o.netloc == host:
        return True
    return f"{o.scheme}://{o.netloc}" in get_settings().cors_origins_list


def _deny(conn: HTTPConnection, status: int, code: str, message: str):
    if conn.scope.get("type") == "websocket":
        return WebSocketException(code=1008, reason=message[:120])
    return HTTPException(status_code=status, detail={"code": code, "message": message})


async def require_session(conn: HTTPConnection) -> dict[str, Any] | None:
    """Dependência global: sessão obrigatória em /api/* e /ws/*, papel por rota."""
    path = conn.url.path
    is_ws = conn.scope.get("type") == "websocket"
    method = "WS" if is_ws else conn.scope.get("method", "GET").upper()
    if not (path.startswith("/api/") or path.startswith("/ws/")):
        return None
    if (method, path) in PUBLIC or (method == "HEAD" and ("GET", path) in PUBLIC):
        return None

    settings = get_settings()
    # Integração serviço-a-serviço (ex.: Prometheus em /api/metrics): só se
    # VISIONDESK_API_KEY estiver definido e o pedido trouxer a chave certa.
    if settings.api_key and conn.headers.get("x-api-key") == settings.api_key and path == "/api/metrics":
        return None

    token = token_of(conn)
    from ..auth import auth as _auth
    sess = await asyncio.to_thread(_auth.session, token) if token else None
    if not sess:
        raise _deny(conn, 401, "unauthorized", "faça login")
    role = sess.get("role")

    # WebSocket com cookie vindo de página de outro site (cross-site WS hijacking).
    if is_ws and conn.scope.get("vd_cookie_auth") and not _origin_ok(conn):
        raise _deny(conn, 403, "forbidden", "origem não permitida")

    if not is_ws and method not in SAFE_METHODS:
        # Credencial que o navegador manda sozinho (cookie) → confere a origem.
        if conn.scope.get("vd_cookie_auth") and not _origin_ok(conn):
            raise _deny(conn, 403, "forbidden", "origem não permitida")
        if needs_admin(method, path):
            if role != "admin":
                raise _deny(conn, 403, "forbidden", "requer admin")
        elif role not in ROLES_WRITE and (method, path) not in VIEW_WRITE_OK \
                and not path.startswith("/api/auth/"):
            raise _deny(conn, 403, "forbidden", "papel somente leitura")
    elif not is_ws and needs_admin(method, path) and role != "admin":
        raise _deny(conn, 403, "forbidden", "requer admin")

    conn.state.session = sess
    return sess


class SessionCookieBridge:
    """ASGI: cookie ``vd_session`` → cabeçalho ``x-auth-token`` quando ausente."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            headers = scope.get("headers") or []
            if not any(k == b"x-auth-token" for k, _ in headers):
                tok = _cookie_from_headers(headers)
                if tok:
                    scope = dict(scope)
                    scope["headers"] = list(headers) + [(b"x-auth-token", tok.encode("latin-1"))]
                    scope["vd_cookie_auth"] = True   # p/ a checagem de origem (CSRF)
        await self.app(scope, receive, send)


def _cookie_from_headers(headers) -> str | None:
    for k, v in headers:
        if k != b"cookie":
            continue
        for part in v.decode("latin-1").split(";"):
            name, _, val = part.strip().partition("=")
            if name == COOKIE_NAME and val:
                # token é hex; qualquer outra coisa é descartada
                val = val.strip().strip('"')
                if val.isalnum() and len(val) <= 128:
                    return val
    return None


def set_session_cookie(response, request, token: str) -> None:
    s = get_settings()
    secure = s.cookie_secure if s.cookie_secure is not None else (request.url.scheme == "https")
    response.set_cookie(
        COOKIE_NAME, token,
        max_age=int(s.session_ttl_hours * 3600) if s.session_ttl_hours > 0 else 30 * 24 * 3600,
        httponly=True, secure=secure, samesite="strict", path="/",
    )


def clear_session_cookie(response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")
