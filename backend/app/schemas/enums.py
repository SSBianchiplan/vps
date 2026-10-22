"""Enumerações compartilhadas do domínio."""
from __future__ import annotations

from enum import Enum


class Mode(str, Enum):
    """Tarefa que a IA executa sobre a imagem."""

    LER = "LER"
    CONTAR = "CONTAR"
    DETECTAR = "DETECTAR"
    RASTREAR = "RASTREAR"   # tracking temporal: identidade, trajetória, linha/zona, dwell, fluxo
    DESCREVER = "DESCREVER"
    ANALISAR = "ANALISAR"


class SourceType(str, Enum):
    MACBOOK = "macbook"
    IPHONE_CONTINUITY = "iphone_continuity"
    IPHONE_WEBRTC = "iphone_webrtc"


class ModelType(str, Enum):
    EDGE = "edge"
    VLM = "vlm"


class PipelineKind(str, Enum):
    """Caminho de inferência escolhido pelo orquestrador."""

    EDGE = "edge"
    VLM = "vlm"
    HYBRID = "hybrid"


class ROIShape(str, Enum):
    RECT = "rect"
    LINE = "line"
    ZONE = "zone"  # polígono fechado
