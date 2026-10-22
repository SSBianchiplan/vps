"""Status das bases de dados/armazenamentos do sistema (#4)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from .. import databases

router = APIRouter(prefix="/databases", tags=["databases"])


@router.get("")
def list_databases() -> dict[str, Any]:
    return databases.status()


@router.get("/teste")
def teste_sistema() -> dict[str, Any]:
    """Inventário do projeto 'Teste Sistema' (PostgreSQL) — tabelas + relacionamentos."""
    return databases.test_system_inventory()
