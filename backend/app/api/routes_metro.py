"""Metrologia / inspeção dimensional: calibração, medição, KPIs (Cpk)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from ..metrology import metro

router = APIRouter(prefix="/metro", tags=["metro"])

Point = list[float]


class CalibrateIn(BaseModel):
    ref: str
    p1: Point
    p2: Point
    known_mm: float
    frame_w: int
    frame_h: int
    valid_until: str | None = None


class MeasureIn(BaseModel):
    kind: str = "linear"           # linear | diameter | angle
    points: list[Point]
    frame_w: int
    frame_h: int
    feature: str
    nominal: float
    tol_lo: float
    tol_hi: float
    op_tag: str | None = None
    unit: str = "mm"


@router.get("/status")
def status() -> dict[str, Any]:
    return {"calibration": metro.current_calibration(), **metro.kpis()}


@router.post("/calibrate")
def calibrate(body: CalibrateIn) -> dict[str, Any]:
    return metro.calibrate_from_reference(body.ref, body.p1, body.p2, body.known_mm,
                                          body.frame_w, body.frame_h, body.valid_until)


@router.post("/measure")
def measure(body: MeasureIn) -> dict[str, Any]:
    return metro.measure(kind=body.kind, points=body.points, frame_w=body.frame_w, frame_h=body.frame_h,
                         feature=body.feature, nominal=body.nominal, tol_lo=body.tol_lo, tol_hi=body.tol_hi,
                         op_tag=body.op_tag, unit=body.unit)


@router.get("/kpis")
def kpis() -> dict[str, Any]:
    return metro.kpis()
