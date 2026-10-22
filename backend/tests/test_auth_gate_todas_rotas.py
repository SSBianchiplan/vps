"""Varre TODAS as rotas do OpenAPI: sem sessão, só a lista PUBLIC responde."""
from __future__ import annotations

import re

from fastapi.testclient import TestClient

from app.api import guard
from app.main import create_app
from app.config import get_settings


def test_todas_as_rotas_exigem_sessao(monkeypatch):
    monkeypatch.setattr(get_settings(), "expose_docs", True)   # só p/ ler o mapa
    app = create_app()
    with TestClient(app) as c:
        spec = c.get("/openapi.json").json()
        total, abertas = 0, []
        for path, ops in spec["paths"].items():
            concreto = re.sub(r"\{[^}]+\}", "x", path)
            for method in ops:
                total += 1
                r = c.request(method.upper(), concreto)
                # "/" (nome do serviço) fica fora de /api e o Caddy nem o encaminha
                if (method.upper(), path) in guard.PUBLIC or path == "/":
                    continue
                if r.status_code != 401:
                    abertas.append((method.upper(), path, r.status_code))
        print(f"{total} operações verificadas")
        assert total > 200, total
        assert abertas == [], abertas
