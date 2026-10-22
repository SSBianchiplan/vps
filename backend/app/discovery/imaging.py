"""ONVIF Imaging (best-effort) — "modo de câmera": dia/noite (IrCutFilter) e
ajustes de imagem (brilho, contraste, saturação, nitidez).

Reusa a infraestrutura SOAP/WS-UsernameToken de ptz.py. Muitas câmeras
Xiongmai/iCSee expõem o Imaging service; quando não, degradamos com mensagem
honesta (supported=False) em vez de fingir.

IrCutFilter (ONVIF): ON = filtro engatado (bloqueia IR → DIA/cor);
OFF = filtro removido (passa IR → NOITE/P&B); AUTO = automático por luz.
"""
from __future__ import annotations

import re
from typing import Any

import httpx

from . import ptz

_IMG_NS = 'xmlns:timg="http://www.onvif.org/ver20/imaging/wsdl"'
_SCHEMA_NS = 'xmlns:tt="http://www.onvif.org/ver10/schema"'

# cache por IP → (port, video_source_token)
_cache: dict[str, tuple[int, str]] = {}

_FIELDS = ("Brightness", "Contrast", "ColorSaturation", "Sharpness")


async def _video_source_token(client: httpx.AsyncClient, ip: str, port: int,
                              user: str | None, pwd: str | None) -> str | None:
    """Token do VideoSource (necessário p/ o Imaging service)."""
    url = f"http://{ip}:{port}/onvif/media_service"
    try:
        text = await ptz._post(client, url, "<trt:GetVideoSources/>",
                               "http://www.onvif.org/ver10/media/wsdl/GetVideoSources", user, pwd)
    except Exception:
        return None
    m = re.search(r'VideoSources[^>]*token="([^"]+)"', text) or re.search(r'token="([^"]+)"', text)
    return m.group(1) if m else None


async def _resolve(ip: str, user: str | None, pwd: str | None) -> tuple[int, str] | None:
    if ip in _cache:
        return _cache[ip]
    found = await ptz._device_url(ip)
    if not found:
        return None
    _, port = found
    async with httpx.AsyncClient(timeout=3.0) as client:
        token = await _video_source_token(client, ip, port, user, pwd)
    if not token:
        token = "000"  # fallback comum em Xiongmai
    _cache[ip] = (port, token)
    return port, token


def _imaging_url(ip: str, port: int) -> str:
    return f"http://{ip}:{port}/onvif/imaging_service"


def _num(text: str, tag: str) -> float | None:
    m = re.search(rf"<[^>]*{tag}>([\d.+-]+)<", text)
    return float(m.group(1)) if m else None


async def get_settings(ip: str, user: str | None, pwd: str | None) -> dict[str, Any]:
    resolved = await _resolve(ip, user, pwd)
    if not resolved:
        return {"supported": False, "message": "ONVIF não respondeu (porta/credenciais?)"}
    port, token = resolved
    body = (f"<timg:GetImagingSettings {_IMG_NS}>"
            f"<timg:VideoSourceToken>{token}</timg:VideoSourceToken></timg:GetImagingSettings>")
    async with httpx.AsyncClient(timeout=3.0) as client:
        try:
            text = await ptz._post(client, _imaging_url(ip, port), body,
                                   "http://www.onvif.org/ver20/imaging/wsdl/GetImagingSettings", user, pwd)
        except Exception as exc:  # noqa: BLE001
            return {"supported": False, "message": f"Imaging não suportado ({exc})"}
    ir = re.search(r"<[^>]*IrCutFilter>(\w+)<", text)
    return {
        "supported": True,
        "video_source_token": token,
        "ir_cut_filter": ir.group(1).upper() if ir else None,
        "brightness": _num(text, "Brightness"),
        "contrast": _num(text, "Contrast"),
        "color_saturation": _num(text, "ColorSaturation"),
        "sharpness": _num(text, "Sharpness"),
    }


async def set_settings(
    ip: str, user: str | None, pwd: str | None, *,
    ir_cut_filter: str | None = None,
    brightness: float | None = None,
    contrast: float | None = None,
    color_saturation: float | None = None,
    sharpness: float | None = None,
) -> dict[str, Any]:
    resolved = await _resolve(ip, user, pwd)
    if not resolved:
        return {"ok": False, "supported": False, "message": "ONVIF não respondeu"}
    port, token = resolved

    parts: list[str] = []
    if ir_cut_filter:
        irc = ir_cut_filter.upper()
        if irc not in ("ON", "OFF", "AUTO"):
            return {"ok": False, "supported": True, "message": "ir_cut_filter inválido (ON|OFF|AUTO)"}
        parts.append(f"<tt:IrCutFilter>{irc}</tt:IrCutFilter>")
    for tag, val in (("Brightness", brightness), ("Contrast", contrast),
                     ("ColorSaturation", color_saturation), ("Sharpness", sharpness)):
        if val is not None:
            parts.append(f"<tt:{tag}>{val}</tt:{tag}>")
    if not parts:
        return {"ok": False, "supported": True, "message": "nada para alterar"}

    body = (f"<timg:SetImagingSettings {_IMG_NS}>"
            f"<timg:VideoSourceToken>{token}</timg:VideoSourceToken>"
            f"<timg:ImagingSettings {_SCHEMA_NS}>{''.join(parts)}</timg:ImagingSettings>"
            f"<timg:ForcePersistence>true</timg:ForcePersistence></timg:SetImagingSettings>")
    async with httpx.AsyncClient(timeout=4.0) as client:
        try:
            await ptz._post(client, _imaging_url(ip, port), body,
                            "http://www.onvif.org/ver20/imaging/wsdl/SetImagingSettings", user, pwd)
            return {"ok": True, "supported": True}
        except httpx.HTTPStatusError as exc:
            return {"ok": False, "supported": False, "message": f"Imaging não suportado ({exc.response.status_code})"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "supported": False, "message": str(exc)}
