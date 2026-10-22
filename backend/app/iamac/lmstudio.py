"""Backend LM Studio (servidor OpenAI-compatível local, default :1234).

Permite usar QUALQUER modelo carregado no LM Studio (ex.: Llama 4 Scout) como
fundação do iaMAC — local e soberano. O LM Studio expõe /v1/models e
/v1/chat/completions; aqui falamos via httpx (sem depender do SDK).
"""
from __future__ import annotations

import os
from typing import Any

import httpx

_URL = os.environ.get("LMSTUDIO_URL", "http://localhost:1234/v1")


def base_url() -> str:
    return _URL


def available() -> bool:
    try:
        return httpx.get(f"{_URL}/models", timeout=1.5).status_code == 200
    except Exception:  # noqa: BLE001
        return False


def models() -> list[str]:
    try:
        data = httpx.get(f"{_URL}/models", timeout=2).json().get("data", [])
        return [m.get("id", "") for m in data if m.get("id")]
    except Exception:  # noqa: BLE001
        return []


def _prompt(question: str, chunks: list[dict[str, Any]]) -> list[dict[str, str]]:
    ctx = "\n\n".join(f"[{c['source']} › {c['title']}]\n{c['text'][:700]}" for c in chunks[:4])
    return [
        {"role": "system", "content": (
            "Você é o copiloto do VisionDesk+VPS. Responda em PT-BR, conciso. "
            "Use SOMENTE o contexto e cite as fontes entre colchetes. "
            "Se não estiver no contexto, diga que não encontrou. Nunca invente.")},
        {"role": "user", "content": f"Contexto:\n{ctx}\n\nPergunta: {question}"},
    ]


def generate(question: str, chunks: list[dict[str, Any]], max_tokens: int = 400) -> str | None:
    mids = models()
    model = mids[0] if mids else "local-model"
    body = {"model": model, "messages": _prompt(question, chunks),
            "max_tokens": max_tokens, "temperature": 0.3, "stream": False}
    try:
        r = httpx.post(f"{_URL}/chat/completions", json=body, timeout=180)
        r.raise_for_status()
        return (r.json()["choices"][0]["message"]["content"] or "").strip() or None
    except Exception:  # noqa: BLE001
        return None
