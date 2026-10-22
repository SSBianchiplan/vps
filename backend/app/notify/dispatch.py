"""Despacho de notificações de detecção (NOTIFICAR).

Chamado após a inferência: se o modo DETECTAR tem `notificar`, envia mensagem
WhatsApp (texto) com resumo, respeitando um cooldown por tarefa+classe p/ não
inundar. Grava FACT_ACTION e retorna um alerta p/ toast no frontend.
"""
from __future__ import annotations

import time
from typing import Any

from ..db.repository import repository
from ..schemas.enums import Mode
from ..schemas.results import InferenceResult
from ..schemas.tasks import DetectParams, TaskConfig
from . import whatsapp

_COOLDOWN_S = 60.0
_last: dict[str, float] = {}


def _cooled(key: str) -> bool:
    now = time.monotonic()
    if now - _last.get(key, 0.0) < _COOLDOWN_S:
        return True
    _last[key] = now
    return False


async def notify_detection(task: TaskConfig, result: InferenceResult) -> list[dict[str, Any]]:
    if task.mode != Mode.DETECTAR:
        return []
    params: DetectParams = task.typed_params()  # type: ignore[assignment]
    if not params.notificar:
        return []
    contagens: dict[str, int] = result.result.get("contagens", {}) or {}
    alvo = set(params.notificar_classes)
    hits = {c: n for c, n in contagens.items() if not alvo or c in alvo}
    if not hits:
        return []
    key = f"{task.task_id}|{','.join(sorted(hits))}"
    if _cooled(key):
        return []

    resumo = ", ".join(f"{n}× {c}" for c, n in hits.items())
    fonte = result.source_id or "câmera"
    body = f"🔔 VisionDesk — DETECÇÃO\n{resumo}\nFonte: {fonte}\nHora: {result.timestamp[:19].replace('T', ' ')}"

    res = await whatsapp.notify(body) if whatsapp.configured() else {"ok": False, "error": "WhatsApp não configurado"}
    import asyncio
    await asyncio.to_thread(
        repository.record_action, None, result.detection_id, task.task_id, "whatsapp",
        ",".join(whatsapp.public_config().get("recipients", [])) or None, {"body": body},
        "success" if res.get("ok") else "error", None, None if res.get("ok") else str(res.get("error")), 0,
    )
    return [{"action_type": "whatsapp", "message": resumo, "payload": None,
             "rule": "DETECTAR · notificar" + ("" if res.get("ok") else " (WhatsApp não enviado)")}]
