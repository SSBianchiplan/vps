"""Automação Industrial — conector OT (PLC/IHM): ativos, simulação, eventos, OEE."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from ..automation import ot

router = APIRouter(prefix="/automation", tags=["automation"])


class AssetIn(BaseModel):
    asset_id: str
    name: str | None = None
    kind: str | None = None
    mode: str = "protocol"
    protocol: str | None = None
    endpoint: str | None = None
    tag_id: str | None = None


@router.get("/status")
def status() -> dict[str, Any]:
    return {"opcua_available": ot.available_opcua(), "read_only": True, "purdue_zone": "DMZ",
            "assets": len(ot.list_assets()), **ot.kpis()}


@router.get("/assets")
def assets() -> dict[str, Any]:
    return {"assets": ot.list_assets(), "demo": ot.DEMO}


@router.post("/asset")
def upsert(body: AssetIn) -> dict[str, Any]:
    return ot.upsert_asset(body.model_dump())


@router.post("/simulate")
def simulate(asset_id: str | None = None) -> dict[str, Any]:
    return ot.simulate(asset_id)


@router.get("/events")
def events(asset_id: str | None = None) -> dict[str, Any]:
    return {"events": ot.events(asset_id)}


@router.get("/alarms")
def alarms() -> dict[str, Any]:
    return {"alarms": ot.alarms()}


class AckIn(BaseModel):
    asset_id: str
    by: str | None = None


@router.post("/ack")
def ack(body: AckIn) -> dict[str, Any]:
    return ot.ack(body.asset_id, body.by)


@router.post("/ack_all")
def ack_all(by: str | None = None) -> dict[str, Any]:
    return ot.ack_all(by)


@router.post("/vision_inspect")
def vision_inspect(asset_id: str | None = None) -> dict[str, Any]:
    return ot.vision_inspect(asset_id)


@router.get("/alarm_qr")
def alarm_qr(asset_id: str | None = None) -> dict[str, Any]:
    return ot.alarm_qr(asset_id)


@router.get("/synoptic")
def synoptic(name: str = "default") -> dict[str, Any]:
    return ot.get_synoptic(name)


class SynopticIn(BaseModel):
    name: str = "default"
    widgets: list[dict[str, Any]]
    links: list[dict[str, Any]] = []


@router.put("/synoptic")
def save_synoptic(body: SynopticIn) -> dict[str, Any]:
    return ot.save_synoptic(body.name, body.widgets, body.links)


@router.get("/kpis")
def kpis() -> dict[str, Any]:
    return ot.kpis()
