"""Termografia / manutenção preditiva: análise, baseline, tendência, KPIs."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from ..thermography import thermo

router = APIRouter(prefix="/thermo", tags=["thermo"])


class AssetIn(BaseModel):
    asset_id: str
    name: str | None = None
    emissivity: float | None = None
    t_min: float | None = None
    t_max: float | None = None
    t_abs_limit: float | None = None
    delta_t_limit: float | None = None
    tag_id: str | None = None


class AnalyzeIn(BaseModel):
    asset_id: str
    image_b64: str


@router.get("/status")
def status() -> dict[str, Any]:
    return {"available": thermo.available(), **thermo.kpis()}


@router.get("/assets")
def assets() -> dict[str, Any]:
    return {"assets": thermo.list_assets()}


@router.post("/asset")
def upsert_asset(body: AssetIn) -> dict[str, Any]:
    kw = {k: v for k, v in body.model_dump().items() if k not in ("asset_id", "name") and v is not None}
    return thermo.upsert_asset(body.asset_id, body.name, **kw)


@router.post("/analyze")
def analyze(body: AnalyzeIn) -> dict[str, Any]:
    return thermo.analyze(body.image_b64, body.asset_id)


@router.post("/baseline")
def baseline(body: AnalyzeIn) -> dict[str, Any]:
    return thermo.set_baseline(body.asset_id, body.image_b64)


@router.get("/trend/{asset_id}")
def trend(asset_id: str) -> dict[str, Any]:
    return {"readings": thermo.trend_series(asset_id)}


@router.get("/kpis")
def kpis() -> dict[str, Any]:
    return thermo.kpis()
