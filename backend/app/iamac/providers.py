"""iaMAC — registro de modelos/backends selecionáveis e despacho.

Backends: extractive (sempre), mlx (modelos open-weight locais no Apple Silicon),
lmstudio (servidor OpenAI-compatível local — qualquer modelo carregado, ex.: Llama 4 Scout).
A escolha do modelo é persistida em data/iamac.json.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config import get_settings
from . import lmstudio, mlx_llm

# Catálogo de modelos selecionáveis (id estável → backend + modelo + rótulo).
MODELS: list[dict[str, Any]] = [
    {"id": "extractive", "provider": "extractive", "model": None,
     "label": "RAG extrativo (sem modelo)", "note": "sempre disponível · local · sem download"},
    {"id": "mlx-qwen-1.5b", "provider": "mlx", "model": "mlx-community/Qwen2.5-1.5B-Instruct-4bit",
     "label": "Qwen2.5 1.5B · MLX", "note": "rápido · ~1 GB · instalado"},
    {"id": "mlx-llama-3.2-3b", "provider": "mlx", "model": "mlx-community/Llama-3.2-3B-Instruct-4bit",
     "label": "Llama 3.2 3B · MLX", "note": "melhor qualidade · ~1.8 GB · baixa no 1º uso"},
    {"id": "mlx-qwen-7b", "provider": "mlx", "model": "mlx-community/Qwen2.5-7B-Instruct-4bit",
     "label": "Qwen2.5 7B · MLX (disco externo)", "note": "alta qualidade · ~4.3 GB no disco de modelos · roda em 16 GB RAM (padrão)"},
    {"id": "mlx-qwen-14b", "provider": "mlx", "model": "mlx-community/Qwen2.5-14B-Instruct-4bit",
     "label": "Qwen2.5 14B · MLX (disco externo)", "note": "máxima qualidade p/ 16 GB · ~8.5 GB no disco de modelos · carga/inferência mais lentas (limite da RAM)"},
    {"id": "mlx-llama-4-scout", "provider": "mlx", "model": "mlx-community/Llama-4-Scout-17B-16E-Instruct-4bit",
     "label": "Llama 4 Scout · MLX", "note": "MoE 17B/16E · ~60 GB + ~64 GB RAM — NÃO roda em 16 GB; use via LM Studio em máquina maior"},
    {"id": "lmstudio", "provider": "lmstudio", "model": None,
     "label": "LM Studio (modelo carregado)", "note": "abra o LM Studio, carregue um modelo (ex.: Llama 4 Scout) e inicie o servidor :1234"},
]
_BY_ID = {m["id"]: m for m in MODELS}


def _cfg_file() -> Path:
    return Path(get_settings().db_path).parent / "iamac.json"


def _default_id() -> str:
    return "mlx-qwen-7b" if mlx_llm.available() else "extractive"


def current_id() -> str:
    f = _cfg_file()
    if f.exists():
        try:
            mid = json.loads(f.read_text()).get("model_id")
            if mid in _BY_ID:
                return mid
        except Exception:  # noqa: BLE001
            pass
    return _default_id()


def set_current(model_id: str) -> dict[str, Any]:
    if model_id not in _BY_ID:
        return {"ok": False, "message": "modelo desconhecido"}
    f = _cfg_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"model_id": model_id}))
    return {"ok": True, "current": model_id}


def available(provider: str) -> bool:
    if provider == "extractive":
        return True
    if provider == "mlx":
        return mlx_llm.available()
    if provider == "lmstudio":
        return lmstudio.available()
    return False


def catalog() -> list[dict[str, Any]]:
    cur = current_id()
    out = []
    for m in MODELS:
        av = available(m["provider"])
        out.append({**m, "available": av,
                    "loaded": mlx_llm.loaded(m["model"]) if m["provider"] == "mlx" else None,
                    "current": m["id"] == cur})
    return out


def generate(question: str, chunks: list[dict[str, Any]]) -> tuple[str | None, str]:
    """Sintetiza com o modelo atual. Retorna (texto|None, engine_label)."""
    m = _BY_ID.get(current_id()) or _BY_ID["extractive"]
    prov = m["provider"]
    if prov == "mlx" and mlx_llm.available():
        txt = mlx_llm.synthesize(question, chunks, m["model"])
        if txt:
            return txt, f"mlx:{m['model'].split('/')[-1]}"
    elif prov == "lmstudio" and lmstudio.available():
        txt = lmstudio.generate(question, chunks)
        if txt:
            return txt, "lmstudio"
    return None, "extractive-rag"   # extrativo (ou fallback)
