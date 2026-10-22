"""Cliente de teste já autenticado (o portão global exige sessão em /api/*)."""
from __future__ import annotations

from fastapi.testclient import TestClient

ADMIN_PIN = "4321"


class AuthClient(TestClient):
    """TestClient que, ao entrar no contexto, garante um admin e faz login.

    A sessão vai no cookie vd_session (como no navegador) — nenhum cabeçalho
    extra, para provar que o frontend publicado segue funcionando.
    """

    def __enter__(self):
        super().__enter__()
        st = self.get("/api/auth/state").json()
        if st["bootstrap_needed"]:
            r = self.post("/api/auth/bootstrap", json={"name": "Admin Teste", "pin": ADMIN_PIN})
        else:
            r = self.post("/api/auth/login/pin", json={"operator_id": "op_admin_teste", "pin": ADMIN_PIN})
        assert r.status_code == 200 and r.json().get("ok"), r.text
        return self


def admin_client(app) -> AuthClient:
    return AuthClient(app)
