"""Workers de câmera contínuos (sempre-ligados) — desacopla captura→inferência→store.

Um asyncio.Task por câmera: grab (RTSP) → orquestrador → persiste evento →
gravação automática (pessoa/cachorro etc.). Roda no event loop do FastAPI.
Transforma o sistema de "disparado por humano" em plataforma 24/7 (#1 do roadmap).
"""
from __future__ import annotations

import asyncio
from typing import Any

from . import recording
from .db.repository import repository
from .discovery import saved, snapshot as snap
from .logging_conf import get_logger
from .orchestrator.router import Orchestrator
from .pipelines.base import FrameContext
from .schemas.tasks import TaskConfig

log = get_logger("visiondesk.worker")


def _task_for(mode: str) -> TaskConfig:
    mode = mode.upper()
    if mode == "CONTAR":
        return TaskConfig(mode="CONTAR", params={"mode": "CONTAR", "classes_alvo": [], "conf_threshold": 0.3, "counting": "instant", "counting_roi": None})  # type: ignore[arg-type]
    return TaskConfig(mode="DETECTAR", params={"mode": "DETECTAR", "classes_alvo": [], "conf_threshold": 0.3, "max_det": 50, "notificar": False, "notificar_classes": []})  # type: ignore[arg-type]


class WorkerManager:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task] = {}
        self._info: dict[str, dict[str, Any]] = {}

    def status(self) -> list[dict[str, Any]]:
        out = []
        for cid, info in self._info.items():
            t = self._tasks.get(cid)
            out.append({**info, "camera_id": cid, "running": bool(t and not t.done())})
        return out

    async def start(self, camera_id: str, mode: str = "DETECTAR", interval: float = 1.5) -> dict[str, Any]:
        cam = saved.get(camera_id)
        if not cam:
            return {"ok": False, "message": "câmera não encontrada"}
        await self.stop(camera_id)
        interval = max(0.3, min(30.0, interval))
        self._info[camera_id] = {"mode": mode.upper(), "interval": interval, "frames": 0, "last_ts": None, "last_result": None, "errors": 0}
        self._tasks[camera_id] = asyncio.create_task(self._loop(camera_id, cam, mode.upper(), interval))
        log.info("worker start cam=%s mode=%s interval=%.1fs", camera_id, mode, interval)
        return {"ok": True, "camera_id": camera_id, "mode": mode.upper(), "interval": interval}

    async def stop(self, camera_id: str) -> dict[str, Any]:
        t = self._tasks.pop(camera_id, None)
        if t and not t.done():
            t.cancel()
            try:
                await t
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        if camera_id in self._info:
            self._info[camera_id]["running"] = False
        return {"ok": True, "camera_id": camera_id}

    async def stop_all(self) -> None:
        for cid in list(self._tasks):
            await self.stop(cid)

    async def _loop(self, camera_id: str, cam: dict, mode: str, interval: float) -> None:
        orch = Orchestrator()
        task = _task_for(mode)
        url = snap._with_creds(saved.rtsp_url(cam), cam.get("username"), cam.get("password"))
        info = self._info[camera_id]
        while True:
            try:
                data, _m = await snap.grab(url, cam.get("username"), cam.get("password"))
                ctx = FrameContext(image_bytes=data, media_type="image/jpeg", source_id=f"cam:{camera_id}", continuous=True)
                result = await orch.process(ctx, task)
                await asyncio.to_thread(repository.save_inference, result, None)
                await asyncio.to_thread(recording.maybe_capture, result, data)
                info["frames"] += 1
                info["last_ts"] = result.timestamp
                info["last_result"] = {"pipeline": result.pipeline, "latency_ms": result.latency_ms,
                                       "contagens": result.result.get("contagens", {})}
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                info["errors"] = info.get("errors", 0) + 1
                log.debug("worker cam=%s erro: %s", camera_id, exc)
            await asyncio.sleep(interval)


manager = WorkerManager()
