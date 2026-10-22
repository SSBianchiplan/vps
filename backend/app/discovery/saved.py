"""Câmeras IP salvas (config local). As senhas ficam SOMENTE no backend.

Persistidas em data/cameras.json (gitignored). O frontend referencia uma câmera
por `id` e nunca recebe a senha — o backend a injeta ao capturar o frame.
"""
from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path
from typing import Any

from ..config import get_settings

_lock = threading.Lock()


def _file() -> Path:
    p = Path(get_settings().db_path).parent / "cameras.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _load() -> list[dict[str, Any]]:
    f = _file()
    if not f.exists():
        return []
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(items: list[dict[str, Any]]) -> None:
    _file().write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def rtsp_url(cam: dict[str, Any]) -> str:
    ip = cam.get("ip")
    if not ip:
        return ""  # câmera de nuvem (P2P) sem IP local → ainda sem RTSP
    port = cam.get("port", 554)
    path = cam.get("path", "/onvif1")
    if not path.startswith("/"):
        path = "/" + path
    return f"rtsp://{ip}:{port}{path}"


def public(cam: dict[str, Any]) -> dict[str, Any]:
    """Versão sem segredos para o frontend."""
    return {
        "id": cam["id"],
        "name": cam.get("name") or cam.get("ip") or cam.get("serial") or "câmera",
        "ip": cam.get("ip", ""),
        "port": cam.get("port", 554),
        "path": cam.get("path", "/onvif1"),
        "username": cam.get("username"),
        "has_password": bool(cam.get("password")),
        "url": rtsp_url(cam),  # sem credenciais
        "enabled": cam.get("enabled", True),  # liga/desliga system-wide (persistido)
        "serial": cam.get("serial"),
        "provider": cam.get("provider"),
        "cloud": bool(cam.get("provider") or cam.get("share_key")) and not cam.get("ip"),
    }


def set_ip(cam_id: str, ip: str, port: int | None = None, path: str | None = None) -> dict[str, Any] | None:
    """Vincula um IP local a uma câmera (ex.: resolução na LAN de uma câmera de nuvem)."""
    with _lock:
        items = _load()
        cam = next((c for c in items if c["id"] == cam_id), None)
        if cam is None:
            return None
        cam["ip"] = ip
        if port:
            cam["port"] = port
        if path:
            cam["path"] = path
        _save(items)
        return public(cam)


def set_enabled(cam_id: str, enabled: bool) -> dict[str, Any] | None:
    """Liga/desliga a câmera no registro raiz (cameras.json) → vale p/ todo o sistema."""
    with _lock:
        items = _load()
        cam = next((c for c in items if c["id"] == cam_id), None)
        if cam is None:
            return None
        cam["enabled"] = enabled
        _save(items)
        return public(cam)


def list_public() -> list[dict[str, Any]]:
    return [public(c) for c in _load()]


def get(cam_id: str) -> dict[str, Any] | None:
    return next((c for c in _load() if c["id"] == cam_id), None)


def add(
    name: str,
    ip: str,
    username: str | None = None,
    password: str | None = None,
    port: int = 554,
    path: str = "/onvif1",
    serial: str | None = None,
    provider: str | None = None,
    share_key: str | None = None,
) -> dict[str, Any]:
    with _lock:
        items = _load()
        cam = {
            "id": f"cam_{uuid.uuid4().hex[:8]}",
            "name": name,
            "ip": ip,
            "port": port,
            "path": path,
            "username": username,
            "password": password,
            "serial": serial,
            "provider": provider,
            "share_key": share_key,
        }
        items.append(cam)
        _save(items)
    return public(cam)


def delete(cam_id: str) -> bool:
    with _lock:
        items = _load()
        new = [c for c in items if c["id"] != cam_id]
        if len(new) == len(items):
            return False
        _save(new)
    return True
