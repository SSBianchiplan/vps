"""Controle nativo Xiongmai (XM) via DVRIP/Sofia (porta 34567).

Câmeras XM (ex.: XM533_X3-WQ-B) IGNORAM o SendAuxiliaryCommand ONVIF para a luz
branca — respondem 200 mas não acionam o LED. O caminho correto é o protocolo
proprietário DVRIP: login (hash "sofia") → GetConfig/SetConfig de `Camera.WhiteLight`.

Best-effort e síncrono (socket TCP); a rota chama via asyncio.to_thread.
"""
from __future__ import annotations

import hashlib
import json
import socket
import struct
from typing import Any

_PORT = 34567
_LOGIN, _CFG_GET, _CFG_SET = 1000, 1042, 1040


def _sofia_hash(password: str) -> str:
    """Hash de senha do XM (reduz o MD5 a 8 chars [0-9A-Za-z])."""
    md5 = hashlib.md5(password.encode()).digest()
    out = ""
    for i in range(8):
        n = (md5[2 * i] + md5[2 * i + 1]) % 62
        out += chr(n + ord("0")) if n < 10 else chr(n + ord("A") - 10) if n < 36 else chr(n + ord("a") - 36)
    return out


def _pkt(sid: int, msgid: int, payload: dict[str, Any]) -> bytes:
    data = json.dumps(payload).encode() + b"\x0a\x00"
    return struct.pack("<BBHIIBBHI", 0xFF, 0, 0, sid, 0, 0, 0, msgid, len(data)) + data


def _recv(sock: socket.socket) -> Any:
    head = b""
    while len(head) < 20:
        chunk = sock.recv(20 - len(head))
        if not chunk:
            raise ConnectionError("conexão fechada")
        head += chunk
    dlen = struct.unpack("<I", head[16:20])[0]
    body = b""
    while len(body) < dlen:
        chunk = sock.recv(dlen - len(body))
        if not chunk:
            break
        body += chunk
    try:
        return json.loads(body.rstrip(b"\x00").rstrip(b"\n").decode("utf-8", "ignore"))
    except Exception:  # noqa: BLE001
        return {}


def _set_light_blocking(ip: str, user: str, pwd: str, on: bool, brightness: int,
                        mode: str = "manual") -> dict[str, Any]:
    try:
        sock = socket.create_connection((ip, _PORT), timeout=3)
    except OSError as exc:
        return {"ok": False, "supported": False, "message": f"DVRIP indisponível ({exc})"}
    try:
        sock.settimeout(4)
        sock.sendall(_pkt(0, _LOGIN, {
            "EncryptType": "MD5", "LoginType": "DVRIP-Web",
            "PassWord": _sofia_hash(pwd or ""), "UserName": user or "admin",
        }))
        r = _recv(sock)
        if not isinstance(r, dict) or r.get("Ret") != 100 or "SessionID" not in r:
            return {"ok": False, "supported": True, "message": f"login DVRIP recusado (Ret {r.get('Ret') if isinstance(r, dict) else '?'})"}
        sid = int(r["SessionID"], 16) if isinstance(r["SessionID"], str) else int(r["SessionID"])
        shex = "0x%08X" % sid

        def get(name: str) -> dict[str, Any]:
            sock.sendall(_pkt(sid, _CFG_GET, {"Name": name, "SessionID": shex}))
            return _recv(sock)

        def setc(name: str, val: Any) -> bool:
            sock.sendall(_pkt(sid, _CFG_SET, {"Name": name, "SessionID": shex, name: val}))
            res = _recv(sock)
            return isinstance(res, dict) and res.get("Ret") in (100, 0)

        # Camera.WhiteLight.WorkMode (validado no hardware XM533):
        #   KeepOpen   = sempre acesa (full-color)      ← "Manual" é no-op neste firmware
        #   Intelligent= acende na detecção da câmera   ← luz automática
        #   Close      = apagada
        wl = (get("Camera.WhiteLight") or {}).get("Camera.WhiteLight")
        ok = False
        if isinstance(wl, dict):
            if mode == "auto":
                wl["WorkMode"] = "Intelligent" if on else "Close"
            else:
                wl["WorkMode"] = "KeepOpen" if on else "Close"
            if on:
                wl["Brightness"] = max(1, min(100, int(brightness)))
                # garante período 24h p/ não depender da janela noturna padrão
                wp = wl.get("WorkPeriod") or {}
                wp.update({"Enable": 1, "SHour": 0, "SMinute": 0, "EHour": 23, "EMinute": 59})
                wl["WorkPeriod"] = wp
            ok = setc("Camera.WhiteLight", wl)

        # DayNightColor=Color força o subsistema full-color (necessário p/ o LED branco
        # engatar; em IR a câmera ignora a luz). Off → Auto (câmera decide).
        pm = (get("Camera.Param") or {}).get("Camera.Param")
        if isinstance(pm, list) and pm and isinstance(pm[0], dict) and "DayNightColor" in pm[0]:
            pm[0]["DayNightColor"] = "0x00000001" if (on and mode != "auto") else "0x00000000"
            setc("Camera.Param", pm)

        # ParamEx.OneKeyOpenWL: gatilho "um toque" p/ acender já (reforça o on)
        px = (get("Camera.ParamEx") or {}).get("Camera.ParamEx")
        if isinstance(px, list) and px and isinstance(px[0], dict) and "OneKeyOpenWL" in px[0]:
            px[0]["OneKeyOpenWL"] = bool(on and mode != "auto")
            ok = setc("Camera.ParamEx", px) or ok

        if ok:
            return {"ok": True, "supported": True, "on": on, "via": "dvrip"}
        return {"ok": False, "supported": True, "message": "câmera não aceitou SetConfig da luz"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "supported": True, "message": f"DVRIP erro: {str(exc)[:60]}"}
    finally:
        try:
            sock.close()
        except Exception:  # noqa: BLE001
            pass


async def set_white_light(ip: str, user: str | None, pwd: str | None,
                          on: bool, brightness: int = 100, mode: str = "manual") -> dict[str, Any]:
    """Controla a luz branca de câmera Xiongmai via DVRIP (porta 34567).

    mode="manual": liga fixa (KeepOpen) / apaga (Close).
    mode="auto":   acende automaticamente na detecção da câmera (Intelligent).
    """
    import asyncio
    return await asyncio.to_thread(_set_light_blocking, ip, user or "admin", pwd or "", on, brightness, mode)
