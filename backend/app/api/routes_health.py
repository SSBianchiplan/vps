"""Health e capacidades do sistema."""
from __future__ import annotations

from pathlib import Path

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
        # Modelo edge em uso, resolvido do .env — a UI mostrava a versão escrita
        # à mão ("YOLO11") e ela envelheceu na primeira troca de pesos.
        "edge_model": Path(settings.yolo_weights).stem if caps.get("edge_detector") else None,
        "persist_frames": settings.persist_frames,
        "modes": ["LER", "CONTAR", "DETECTAR", "RASTREAR", "DESCREVER", "ANALISAR"],
    }
