"""Health e capacidades do sistema."""
from __future__ import annotations

from fastapi import APIRouter

from ..config import get_settings
from ..orchestrator.router import Orchestrator

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "visiondesk", "version": "0.1.0"}


@router.get("/capabilities")
def capabilities() -> dict:
    settings = get_settings()
    caps = Orchestrator.capabilities()
    return {
        **caps,
        "claude_model": settings.claude_model,
        "persist_frames": settings.persist_frames,
        "modes": ["LER", "CONTAR", "DETECTAR", "RASTREAR", "DESCREVER", "ANALISAR"],
    }
