"""Cibersegurança — postura NIST CSF, integridade da trilha, ameaças, frameworks."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from .. import security

router = APIRouter(prefix="/security", tags=["security"])


@router.get("/overview")
def overview() -> dict[str, Any]:
    return security.overview()


@router.get("/integrity")
def integrity() -> dict[str, Any]:
    return security.integrity_check()


@router.get("/events")
def events(limit: int = 30) -> dict[str, Any]:
    return {"events": security.events(limit)}
