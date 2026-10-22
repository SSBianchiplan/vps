"""Classificação CNN (§3.1) / ViT (§3.3) — inferência local sob demanda."""
from __future__ import annotations

import asyncio
from time import perf_counter
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..inference.edge import classify as clf
from ..utils.images import b64_to_bytes

router = APIRouter(prefix="/classify", tags=["classify"])


class ClassifyIn(BaseModel):
    image_b64: str
    model: str = "cnn"     # cnn | vit
    topk: int = 5


@router.post("")
async def classify(body: ClassifyIn) -> dict[str, Any]:
    try:
        data = b64_to_bytes(body.image_b64)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"imagem inválida: {exc}")
    t0 = perf_counter()
    out = await asyncio.to_thread(clf.classify, data, body.model, body.topk)
    out["latency_ms"] = int((perf_counter() - t0) * 1000)
    out["model"] = body.model
    return out
