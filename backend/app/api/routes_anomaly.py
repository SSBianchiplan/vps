"""Anomalia não supervisionada (§3.4): treinar perfil de normais + pontuar."""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..discovery import saved, snapshot as snap
from ..inference.edge import anomaly
from ..utils.images import b64_to_bytes

router = APIRouter(prefix="/anomaly", tags=["anomaly"])


class FitIn(BaseModel):
    profile: str | None = None           # default = source_id da câmera
    camera_id: str | None = None         # captura N frames da câmera
    samples: int = 8
    images_b64: list[str] | None = None  # ou forneça frames diretamente


class ScoreIn(BaseModel):
    profile: str
    image_b64: str


@router.get("/status")
def anomaly_status(profile: str) -> dict[str, Any]:
    return anomaly.status(profile)


@router.post("/fit")
async def anomaly_fit(body: FitIn) -> dict[str, Any]:
    profile = body.profile or (f"cam:{body.camera_id}" if body.camera_id else None)
    if not profile:
        raise HTTPException(status_code=400, detail={"code": "missing_profile", "message": "informe profile ou camera_id"})

    images: list[bytes] = []
    if body.images_b64:
        images = [b64_to_bytes(b) for b in body.images_b64]
    elif body.camera_id:
        cam = saved.get(body.camera_id)
        if not cam:
            raise HTTPException(status_code=404, detail={"code": "camera_not_found", "message": "câmera não encontrada"})
        url = snap._with_creds(saved.rtsp_url(cam), cam.get("username"), cam.get("password"))
        for _ in range(max(2, min(20, body.samples))):
            try:
                data, _m = await snap.grab(url, cam.get("username"), cam.get("password"))
                images.append(data)
            except Exception:  # noqa: BLE001
                continue
            await asyncio.sleep(0.4)
    if len(images) < 2:
        raise HTTPException(status_code=400, detail={"code": "insufficient", "message": "≥2 frames normais necessários"})

    return await asyncio.to_thread(anomaly.fit, profile, images)


@router.post("/score")
async def anomaly_score(body: ScoreIn) -> dict[str, Any]:
    data = b64_to_bytes(body.image_b64)
    return await asyncio.to_thread(anomaly.score, body.profile, data)
