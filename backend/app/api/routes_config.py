"""Configurações persistidas: catálogo UI/UX, schema de links do supervisório,
aparência e implantação em ondas (chave→JSON em app_config)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from .. import appconfig

router = APIRouter(prefix="/config", tags=["config"])
_seeded = False


def _ensure() -> None:
    global _seeded
    if not _seeded:
        appconfig.seed()
        _seeded = True


@router.get("")
def list_all() -> dict[str, Any]:
    _ensure()
    return {
        "keys": appconfig.keys(),
        "ui_components": appconfig.get("ui_components"),
        "sup_link_fields": appconfig.get("sup_link_fields"),
        "ui_rollout": appconfig.get("ui_rollout"),
        "appearance": appconfig.get("appearance"),
    }


class WaveIn(BaseModel):
    current_wave: int


@router.put("/wave")
def set_wave(body: WaveIn) -> dict[str, Any]:
    _ensure()
    r = appconfig.get("ui_rollout") or dict(appconfig.DEFAULT_ROLLOUT)
    r["current_wave"] = max(0, min(int(body.current_wave), int(r.get("waves", 8))))
    appconfig.put("ui_rollout", r)
    return r


class LinkIn(BaseModel):
    link: dict[str, Any]


@router.post("/validate_link")
def validate_link(body: LinkIn) -> dict[str, Any]:
    _ensure()
    missing = appconfig.validate_link(body.link)
    return {"ok": not missing, "missing": missing}


@router.get("/{key}")
def get_one(key: str) -> dict[str, Any]:
    _ensure()
    return {"key": key, "value": appconfig.get(key)}


class CfgIn(BaseModel):
    value: Any


@router.put("/{key}")
def put_one(key: str, body: CfgIn) -> dict[str, Any]:
    _ensure()
    return appconfig.put(key, body.value)
