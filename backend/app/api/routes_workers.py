"""Workers de câmera contínuos: start/stop/status (#1 — sempre-ligado)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from ..workers import manager

router = APIRouter(prefix="/workers", tags=["workers"])


class StartIn(BaseModel):
    mode: str = "DETECTAR"      # DETECTAR | CONTAR
    interval: float = 1.5       # segundos entre frames


@router.get("")
def list_workers() -> dict[str, Any]:
    return {"workers": manager.status()}


@router.post("/{camera_id}/start")
async def start_worker(camera_id: str, body: StartIn) -> dict[str, Any]:
    return await manager.start(camera_id, body.mode, body.interval)


@router.post("/{camera_id}/stop")
async def stop_worker(camera_id: str) -> dict[str, Any]:
    return await manager.stop(camera_id)
