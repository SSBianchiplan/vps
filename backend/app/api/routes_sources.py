"""Registro/listagem de fontes de captura (DIM_SOURCE)."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from ..db.repository import repository
from ..schemas.enums import SourceType

router = APIRouter(prefix="/sources", tags=["sources"])


class SourceIn(BaseModel):
    source_id: str
    tipo: SourceType
    resolucao: str | None = None
    fps_nominal: int | None = None
    descricao: str | None = None


@router.post("")
def register_source(src: SourceIn) -> dict:
    sid = repository.upsert_source(
        src.source_id, src.tipo.value, src.resolucao, src.fps_nominal, src.descricao
    )
    return {"source_id": sid}


@router.get("")
def list_sources() -> list[dict]:
    return repository.list_sources()
