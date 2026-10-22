"""Síntese local via MLX (LLM open-weight self-hosted no Apple Silicon).

Suporta MÚLTIPLOS modelos (cache por id) — selecionáveis no iaMAC. Lazy-load:
o modelo só baixa/carrega quando escolhido. Degrada para extrativo se faltar.
"""
from __future__ import annotations

import os
from typing import Any

# Cache de modelos (pode apontar para um disco externo via VISIONDESK_MODELS_DIR) — definido
# ANTES de qualquer import do huggingface_hub (que só ocorre dentro das funções).
_MODELS_DRIVE = os.environ.get("VISIONDESK_MODELS_DIR", "")
if _MODELS_DRIVE and (os.path.isdir(os.path.dirname(_MODELS_DRIVE)) or os.path.isdir(_MODELS_DRIVE)):
    os.makedirs(_MODELS_DRIVE, exist_ok=True)
    os.environ.setdefault("HF_HOME", _MODELS_DRIVE)
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")  # downloader clássico — robusto em drive externo

_DEFAULT = "mlx-community/Qwen2.5-1.5B-Instruct-4bit"


def models_dir() -> str:
    return os.environ.get("HF_HOME", "(padrão do sistema)")
_cache: dict[str, Any] = {}      # model_id → (model, tok)
_errors: dict[str, str] = {}     # model_id → erro


def available() -> bool:
    import importlib.util
    return importlib.util.find_spec("mlx_lm") is not None


def loaded(model_id: str | None = None) -> bool:
    return (model_id or _DEFAULT) in _cache


def _load(model_id: str) -> Any | None:
    if model_id in _cache:
        return _cache[model_id]
    if model_id in _errors or not available():
        return None
    try:
        from mlx_lm import load
        # 16 GB de RAM: mantém só UM modelo carregado por vez (libera os demais).
        if _cache:
            _cache.clear()
            import gc
            gc.collect()
        _cache[model_id] = load(model_id)
        return _cache[model_id]
    except Exception as exc:  # noqa: BLE001
        _errors[model_id] = str(exc)[:160]
        return None


def synthesize(question: str, chunks: list[dict[str, Any]], model_id: str = _DEFAULT, max_tokens: int = 320) -> str | None:
    pair = _load(model_id)
    if not pair:
        return None
    try:
        from mlx_lm import generate
        model, tok = pair
        ctx = "\n\n".join(f"[{c['source']} › {c['title']}]\n{c['text'][:700]}" for c in chunks[:4])
        msgs = [
            {"role": "system", "content": (
                "Você é o copiloto do VisionDesk+VPS. Responda em PT-BR, conciso. "
                "Use SOMENTE o contexto fornecido e cite as fontes entre colchetes. "
                "Se não estiver no contexto, diga que não encontrou. Nunca invente nem altere dados.")},
            {"role": "user", "content": f"Contexto:\n{ctx}\n\nPergunta: {question}"},
        ]
        prompt = tok.apply_chat_template(msgs, add_generation_prompt=True)
        out = generate(model, tok, prompt=prompt, max_tokens=max_tokens, verbose=False)
        return (out or "").strip() or None
    except Exception as exc:  # noqa: BLE001
        _errors[model_id] = str(exc)[:160]
        return None


def error(model_id: str) -> str | None:
    return _errors.get(model_id)
