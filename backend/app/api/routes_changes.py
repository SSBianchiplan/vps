"""Gestão de alterações — quem mudou o quê, quando e de que valor para qual."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query

from .. import changes

router = APIRouter(prefix="/changes", tags=["changes"])


def _exige_sessao(token: str | None) -> None:
    """O log mostra valores antes/depois de tabelas de negócio: exige sessão."""
    from ..auth import auth
    s = auth.session(token)
    if not s:
        raise HTTPException(status_code=403, detail={"code": "forbidden", "message": "requer sessão"})


@router.get("")
def listar(table: str | None = Query(default=None), pk: str | None = Query(default=None),
           actor: str | None = Query(default=None), op: str | None = Query(default=None),
           q: str | None = Query(default=None), limit: int = Query(default=200, le=1000),
           x_auth_token: str | None = Header(default=None)) -> dict[str, Any]:
    _exige_sessao(x_auth_token)
    return changes.listar(table, pk, actor, op, q, limit)


@router.get("/summary")
def resumo(x_auth_token: str | None = Header(default=None)) -> dict[str, Any]:
    _exige_sessao(x_auth_token)
    return changes.resumo()


@router.get("/history")
def historico(table: str = Query(...), pk: str = Query(...), limit: int = Query(default=100, le=500),
              x_auth_token: str | None = Header(default=None)) -> dict[str, Any]:
    _exige_sessao(x_auth_token)
    return changes.historico(table, pk, limit)
