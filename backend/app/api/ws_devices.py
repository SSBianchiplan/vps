"""Presença de dispositivos + sinalização WebRTC (câmeras abertas por aparelho).

Cada navegador conectado abre `/ws/devices`. O servidor mantém um registro EM
MEMÓRIA dos peers (nome do aparelho, plataforma, estado da câmera), faz
*broadcast* do roster a todos quando algo muda, e **relaya** mensagens de
sinalização (SDP/ICE) entre dois peers — sem interpretá-las.

O vídeo é **peer-to-peer (WebRTC)** e NÃO passa pelo servidor: só a sinalização.
Funciona na LAN com candidatos host/mDNS; STUN é configurado no cliente.

Estado em memória ⇒ requer 1 worker (uvicorn --reload usa 1). Em multi-worker,
trocar por um pub/sub compartilhado (Redis) — fora do escopo do dev local.
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..logging_conf import get_logger

router = APIRouter()
log = get_logger("visiondesk.devices")


class _Peer:
    def __init__(self, peer_id: str, ws: WebSocket) -> None:
        self.id = peer_id
        self.ws = ws
        self.name: str = "Dispositivo"
        self.platform: str = ""
        self.camera: dict[str, Any] | None = None  # {label,width,height,facing} | None

    def public(self) -> dict[str, Any]:
        return {
            "peer_id": self.id,
            "name": self.name,
            "platform": self.platform,
            "camera": self.camera,
        }


_peers: dict[str, _Peer] = {}
_lock = asyncio.Lock()


async def _broadcast_roster() -> None:
    """Envia o roster atual a todos; remove conexões mortas encontradas no caminho."""
    msg = {"type": "roster", "peers": [p.public() for p in _peers.values()]}
    dead: list[str] = []
    for p in list(_peers.values()):
        try:
            await p.ws.send_json(msg)
        except Exception:  # noqa: BLE001 — peer caindo; será limpo
            dead.append(p.id)
    if dead:
        async with _lock:
            for pid in dead:
                _peers.pop(pid, None)


@router.websocket("/ws/devices")
async def devices(ws: WebSocket) -> None:
    await ws.accept()
    peer_id = uuid.uuid4().hex[:12]
    peer = _Peer(peer_id, ws)
    async with _lock:
        _peers[peer_id] = peer
    await ws.send_json({"type": "welcome", "peer_id": peer_id})
    await _broadcast_roster()
    try:
        while True:
            data = await ws.receive_json()
            t = data.get("type")
            if t == "hello":
                dev = data.get("device") or {}
                peer.name = str(dev.get("name") or "Dispositivo")[:60]
                peer.platform = str(dev.get("platform") or "")[:40]
                peer.camera = data.get("camera")
                await _broadcast_roster()
            elif t == "camera":
                peer.camera = data.get("camera")
                await _broadcast_roster()
            elif t == "signal":
                target = _peers.get(data.get("to") or "")
                if target is not None:
                    try:
                        await target.ws.send_json(
                            {"type": "signal", "from": peer_id, "data": data.get("data")}
                        )
                    except Exception:  # noqa: BLE001
                        pass
            elif t == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001 — JSON inválido/socket; encerra limpo
        log.info("devices ws encerrada: %s", exc)
    finally:
        async with _lock:
            _peers.pop(peer_id, None)
        await _broadcast_roster()
