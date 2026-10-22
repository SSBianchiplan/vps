"""Shim de compatibilidade.

O entrypoint canônico do backend é ``app.main:app`` (ver scripts/run-backend.sh
e README). Runners/processos antigos sobem ``uvicorn app.api.main:app`` — módulo
que havia sido removido numa refatoração. Quando esse comando é relançado sem o
módulo, o uvicorn falha a importar e um processo obsoleto carregado em memória
acaba servindo um SPA catch-all que sombreia as rotas ``/api/*`` (quebra o login).

Este shim faz ``app.api.main:app`` resolver para a aplicação correta, de modo que
qualquer relance desse comando sirva exatamente o mesmo app que ``app.main:app``.
"""
from __future__ import annotations

from app.main import app

__all__ = ["app"]
