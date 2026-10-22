"""Controle PTZ via ONVIF (best-effort).

Implementa GetProfiles + ContinuousMove/Stop por SOAP sobre httpx, com
WS-UsernameToken (PasswordDigest). Muitas câmeras Xiongmai/iCSee são fixas
(bullet) e NÃO possuem motor PTZ — nesse caso o dispositivo responde com falta
de suporte e degradamos com uma mensagem honesta em vez de fingir movimento.

Portas ONVIF comuns nesses aparelhos: 8899 (Xiongmai), 80, 8000, 8080.
"""
from __future__ import annotations

import base64
import hashlib
import os
import re
from datetime import datetime, timezone

import httpx

ONVIF_PORTS = [8899, 80, 8000, 8080, 2000]

_NS = (
    'xmlns:s="http://www.w3.org/2003/05/soap-envelope" '
    'xmlns:tt="http://www.onvif.org/ver10/schema" '
    'xmlns:trt="http://www.onvif.org/ver10/media/wsdl" '
    'xmlns:tptz="http://www.onvif.org/ver20/ptz/wsdl"'
)


def _security_header(username: str | None, password: str | None) -> str:
    if not username:
        return ""
    nonce = os.urandom(16)
    created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    digest = base64.b64encode(
        hashlib.sha1(nonce + created.encode() + (password or "").encode()).digest()
    ).decode()
    nonce_b64 = base64.b64encode(nonce).decode()
    return (
        '<s:Header><Security s:mustUnderstand="1" '
        'xmlns="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">'
        "<UsernameToken><Username>" + username + "</Username>"
        '<Password Type="http://docs.oasis-open.org/wss/2004/01/'
        'oasis-200401-wss-username-token-profile-1.0#PasswordDigest">' + digest + "</Password>"
        '<Nonce EncodingType="http://docs.oasis-open.org/wss/2004/01/'
        'oasis-200401-wss-soap-message-security-1.0#Base64Binary">' + nonce_b64 + "</Nonce>"
        "<Created xmlns=\"http://docs.oasis-open.org/wss/2004/01/"
        "oasis-200401-wss-wssecurity-utility-1.0.xsd\">" + created + "</Created>"
        "</UsernameToken></Security></s:Header>"
    )


def _envelope(body: str, username: str | None, password: str | None) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f"<s:Envelope {_NS}>" + _security_header(username, password) +
        f"<s:Body>{body}</s:Body></s:Envelope>"
    )


async def _post(client: httpx.AsyncClient, url: str, body: str, action: str,
                username: str | None, password: str | None) -> str:
    headers = {"Content-Type": f'application/soap+xml; charset=utf-8; action="{action}"'}
    resp = await client.post(url, content=_envelope(body, username, password).encode(), headers=headers)
    resp.raise_for_status()
    return resp.text


async def _device_url(ip: str) -> tuple[str, int] | None:
    """Tenta achar um endpoint ONVIF device em portas comuns."""
    async with httpx.AsyncClient(timeout=2.5) as client:
        for port in ONVIF_PORTS:
            url = f"http://{ip}:{port}/onvif/device_service"
            body = '<tds:GetCapabilities xmlns:tds="http://www.onvif.org/ver10/device/wsdl"/>'
            try:
                await _post(client, url, body, "http://www.onvif.org/ver10/device/wsdl/GetCapabilities", None, None)
                return url, port
            except Exception:
                continue
    return None


async def _first_profile(client: httpx.AsyncClient, ip: str, port: int,
                         username: str | None, password: str | None) -> str | None:
    url = f"http://{ip}:{port}/onvif/media_service"
    body = "<trt:GetProfiles/>"
    try:
        text = await _post(client, url, body, "http://www.onvif.org/ver10/media/wsdl/GetProfiles", username, password)
    except Exception:
        return None
    m = re.search(r'Profiles[^>]*token="([^"]+)"', text) or re.search(r'token="([^"]+)"', text)
    return m.group(1) if m else None


_substream_cache: dict[str, str | None] = {}


async def discover_substream(ip: str, username: str | None, password: str | None) -> str | None:
    """Descobre a URI RTSP do SUBSTREAM via ONVIF GetStreamUri (último profile).

    Substream = baixa-res/bitrate → muito menos perda em Wi-Fi → vídeo fluido.
    Resultado cacheado por IP (None = sem ONVIF/substream).
    """
    if ip in _substream_cache:
        return _substream_cache[ip]
    result: str | None = None
    found = await _device_url(ip)
    if found:
        _, port = found
        media = f"http://{ip}:{port}/onvif/media_service"
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                text = await _post(client, media, "<trt:GetProfiles/>",
                                   "http://www.onvif.org/ver10/media/wsdl/GetProfiles", username, password)
                tokens = re.findall(r'token="([^"]+)"', text)
                if tokens:
                    token = tokens[-1]  # último profile costuma ser o substream
                    body = (
                        "<trt:GetStreamUri><trt:StreamSetup>"
                        "<tt:Stream>RTP-Unicast</tt:Stream>"
                        "<tt:Transport><tt:Protocol>RTSP</tt:Protocol></tt:Transport>"
                        f"</trt:StreamSetup><trt:ProfileToken>{token}</trt:ProfileToken></trt:GetStreamUri>"
                    )
                    su = await _post(client, media, body,
                                     "http://www.onvif.org/ver10/media/wsdl/GetStreamUri", username, password)
                    m = re.search(r"<[^>]*Uri>(rtsp://[^<]+)<", su)
                    if m:
                        uri = m.group(1)
                        result = f"rtsp://{quote_creds(username, password)}{uri[len('rtsp://'):]}" if username else uri
        except Exception:
            result = None
    _substream_cache[ip] = result
    return result


def quote_creds(user: str | None, pwd: str | None) -> str:
    from urllib.parse import quote
    return f"{quote(user or '')}:{quote(pwd or '')}@"


async def move(ip: str, username: str | None, password: str | None,
               pan: float = 0.0, tilt: float = 0.0, zoom: float = 0.0) -> dict:
    """Executa ContinuousMove (sem Stop automático — o cliente chama stop)."""
    found = await _device_url(ip)
    if not found:
        return {"ok": False, "supported": False, "message": "ONVIF não respondeu (porta/credenciais?)"}
    _, port = found
    async with httpx.AsyncClient(timeout=3.0) as client:
        token = await _first_profile(client, ip, port, username, password)
        if not token:
            return {"ok": False, "supported": False, "message": "sem profiles ONVIF (câmera fixa?)"}
        url = f"http://{ip}:{port}/onvif/ptz_service"
        body = (
            f'<tptz:ContinuousMove><tptz:ProfileToken>{token}</tptz:ProfileToken>'
            f'<tptz:Velocity><tt:PanTilt x="{pan}" y="{tilt}"/><tt:Zoom x="{zoom}"/></tptz:Velocity>'
            "</tptz:ContinuousMove>"
        )
        try:
            await _post(client, url, body, "http://www.onvif.org/ver20/ptz/wsdl/ContinuousMove", username, password)
            return {"ok": True, "supported": True, "profile": token}
        except httpx.HTTPStatusError as exc:
            return {"ok": False, "supported": False, "message": f"PTZ não suportado pela câmera ({exc.response.status_code})"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "supported": False, "message": str(exc)}


async def _ptz_ctx(ip: str, username: str | None, password: str | None) -> tuple[int, str] | None:
    """(porta ONVIF, profile token) ou None se indisponível."""
    found = await _device_url(ip)
    if not found:
        return None
    _, port = found
    async with httpx.AsyncClient(timeout=3.0) as client:
        token = await _first_profile(client, ip, port, username, password)
    return (port, token) if token else None


_PTZ_WSDL = "http://www.onvif.org/ver20/ptz/wsdl"


async def set_preset(ip: str, username: str | None, password: str | None, name: str | None = None) -> dict:
    """Grava a posição ATUAL da câmera como preset (PTZ SetPreset)."""
    ctx = await _ptz_ctx(ip, username, password)
    if not ctx:
        return {"ok": False, "supported": False, "message": "PTZ/ONVIF indisponível (câmera fixa?)"}
    port, token = ctx
    nm = (name or "VisionDesk").replace("<", "").replace(">", "")[:40]
    url = f"http://{ip}:{port}/onvif/ptz_service"
    body = (f"<tptz:SetPreset><tptz:ProfileToken>{token}</tptz:ProfileToken>"
            f"<tptz:PresetName>{nm}</tptz:PresetName></tptz:SetPreset>")
    async with httpx.AsyncClient(timeout=4.0) as client:
        try:
            text = await _post(client, url, body, f"{_PTZ_WSDL}/SetPreset", username, password)
            m = re.search(r"PresetToken[^>]*>([^<]+)<", text) or re.search(r'PresetToken="([^"]+)"', text)
            return {"ok": True, "supported": True, "preset_token": m.group(1) if m else None, "name": nm}
        except httpx.HTTPStatusError as exc:
            return {"ok": False, "supported": False, "message": f"presets não suportados ({exc.response.status_code})"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "supported": False, "message": str(exc)}


async def get_presets(ip: str, username: str | None, password: str | None) -> dict:
    ctx = await _ptz_ctx(ip, username, password)
    if not ctx:
        return {"ok": False, "supported": False, "presets": [], "message": "PTZ/ONVIF indisponível"}
    port, token = ctx
    url = f"http://{ip}:{port}/onvif/ptz_service"
    body = f"<tptz:GetPresets><tptz:ProfileToken>{token}</tptz:ProfileToken></tptz:GetPresets>"
    async with httpx.AsyncClient(timeout=4.0) as client:
        try:
            text = await _post(client, url, body, f"{_PTZ_WSDL}/GetPresets", username, password)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "supported": False, "presets": [], "message": str(exc)}
    presets = []
    for m in re.finditer(r'<(?:\w+:)?Preset\b[^>]*token="([^"]+)"[^>]*>(.*?)</(?:\w+:)?Preset>', text, re.S):
        nm = re.search(r"<(?:\w+:)?Name>([^<]*)<", m.group(2))
        presets.append({"token": m.group(1), "name": (nm.group(1) if nm else m.group(1))})
    return {"ok": True, "supported": True, "presets": presets}


async def goto_preset(ip: str, username: str | None, password: str | None, preset_token: str) -> dict:
    ctx = await _ptz_ctx(ip, username, password)
    if not ctx:
        return {"ok": False, "supported": False, "message": "PTZ/ONVIF indisponível"}
    port, token = ctx
    url = f"http://{ip}:{port}/onvif/ptz_service"
    body = (f"<tptz:GotoPreset><tptz:ProfileToken>{token}</tptz:ProfileToken>"
            f"<tptz:PresetToken>{preset_token}</tptz:PresetToken></tptz:GotoPreset>")
    async with httpx.AsyncClient(timeout=4.0) as client:
        try:
            await _post(client, url, body, f"{_PTZ_WSDL}/GotoPreset", username, password)
            return {"ok": True, "supported": True}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "supported": False, "message": str(exc)}


async def remove_preset(ip: str, username: str | None, password: str | None, preset_token: str) -> dict:
    ctx = await _ptz_ctx(ip, username, password)
    if not ctx:
        return {"ok": False, "supported": False, "message": "PTZ/ONVIF indisponível"}
    port, token = ctx
    url = f"http://{ip}:{port}/onvif/ptz_service"
    body = (f"<tptz:RemovePreset><tptz:ProfileToken>{token}</tptz:ProfileToken>"
            f"<tptz:PresetToken>{preset_token}</tptz:PresetToken></tptz:RemovePreset>")
    async with httpx.AsyncClient(timeout=4.0) as client:
        try:
            await _post(client, url, body, f"{_PTZ_WSDL}/RemovePreset", username, password)
            return {"ok": True, "supported": True}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "supported": False, "message": str(exc)}


# Comandos auxiliares ONVIF p/ acionar a iluminação (LED branco / IR).
# A string exata é definida pelo fabricante; tentamos as mais comuns em ordem.
_LIGHT_AUX = {
    "white": ["tt:WhiteLight", "tt:FloodLight", "tt:Light", "tt:SupplementLight", "tt:IRLamp"],
    "ir": ["tt:IRLamp", "tt:IrLight", "tt:Light"],
}


async def set_light(ip: str, username: str | None, password: str | None,
                    on: bool, kind: str = "white") -> dict:
    """Acende/apaga a luz da câmera (LED branco ou IR) via ONVIF SendAuxiliaryCommand.

    Best-effort: a maioria das câmeras com refletor expõe a lâmpada como
    dispositivo auxiliar. Sem suporte → mensagem honesta (supported=False).
    """
    ctx = await _ptz_ctx(ip, username, password)
    if not ctx:
        return {"ok": False, "supported": False, "message": "ONVIF/PTZ indisponível p/ comando auxiliar"}
    port, token = ctx
    url = f"http://{ip}:{port}/onvif/ptz_service"
    state = "On" if on else "Off"
    candidates = _LIGHT_AUX.get(kind, _LIGHT_AUX["white"])
    last = "sem resposta"
    async with httpx.AsyncClient(timeout=4.0) as client:
        for base in candidates:
            aux = f"{base}|{state}"
            body = (f"<tptz:SendAuxiliaryCommand><tptz:ProfileToken>{token}</tptz:ProfileToken>"
                    f"<tptz:AuxiliaryData>{aux}</tptz:AuxiliaryData></tptz:SendAuxiliaryCommand>")
            try:
                text = await _post(client, url, body, f"{_PTZ_WSDL}/SendAuxiliaryCommand", username, password)
                if "Fault" in text or "NotSupported" in text or "ActionNotSupported" in text:
                    last = f"{base}: recusado"
                    continue
                return {"ok": True, "supported": True, "on": on, "aux": aux}
            except httpx.HTTPStatusError as exc:
                last = f"HTTP {exc.response.status_code}"
                continue
            except Exception as exc:  # noqa: BLE001
                last = str(exc)
                continue
    return {"ok": False, "supported": False,
            "message": f"câmera não aceitou comando de luz ({last})"}


async def stop(ip: str, username: str | None, password: str | None) -> dict:
    found = await _device_url(ip)
    if not found:
        return {"ok": False, "supported": False, "message": "ONVIF não respondeu"}
    _, port = found
    async with httpx.AsyncClient(timeout=3.0) as client:
        token = await _first_profile(client, ip, port, username, password)
        if not token:
            return {"ok": False, "supported": False, "message": "sem profiles ONVIF"}
        url = f"http://{ip}:{port}/onvif/ptz_service"
        body = (
            f"<tptz:Stop><tptz:ProfileToken>{token}</tptz:ProfileToken>"
            "<tptz:PanTilt>true</tptz:PanTilt><tptz:Zoom>true</tptz:Zoom></tptz:Stop>"
        )
        try:
            await _post(client, url, body, "http://www.onvif.org/ver20/ptz/wsdl/Stop", username, password)
            return {"ok": True, "supported": True}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "supported": False, "message": str(exc)}
