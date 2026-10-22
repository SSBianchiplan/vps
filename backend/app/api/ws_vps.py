"""VPS ao vivo — push incremental de eventos do Fio Dourado p/ o cockpit.

Sem cross-thread: a captura grava no Event Store (em thread); este WS consulta o
delta (rowid > last) e empurra. Cadência curta = "tempo real" sem polling no cliente.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..logging_conf import get_logger
from ..vps import store

router = APIRouter()
log = get_logger("visiondesk.vps.ws")

_POLL_S = 1.5


@router.websocket("/ws/vps")
async def vps_live(ws: WebSocket) -> None:
    await ws.accept()
    last = await asyncio.to_thread(store.max_event_rowid)
    try:
        await ws.send_json({"type": "ready", "last": last})
        while True:
            await asyncio.sleep(_POLL_S)
            rows = await asyncio.to_thread(store.events_after, last)
            if rows:
                last = rows[-1]["_rowid"]
                await ws.send_json({"type": "events", "events": rows})
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        log.exception("WS /ws/vps encerrado por erro")
