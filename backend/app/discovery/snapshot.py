"""Captura de um frame de uma câmera IP (RTSP via OpenCV; HTTP via httpx).

OpenCV é opcional (parte do caminho edge). Sem ele, o RTSP fica indisponível e
o erro é claro; câmeras com endpoint HTTP de snapshot funcionam sem OpenCV.
Capturas RTSP são reaproveitadas (cache por URL) para melhorar o FPS.
"""
from __future__ import annotations

import asyncio
import os
import threading
from functools import lru_cache
from typing import Any
from urllib.parse import quote, urlparse, urlunparse

import httpx

from ..inference.errors import InferenceError

# Força RTSP sobre TCP e timeout de socket (µs) no backend FFmpeg do OpenCV,
# para que uma URL/credencial inválida falhe rápido em vez de travar a thread.
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp|stimeout;6000000")


class SnapshotUnavailable(InferenceError):
    code = "snapshot_unavailable"


@lru_cache(maxsize=1)
def _cv2() -> Any | None:
    try:
        import cv2
        return cv2
    except Exception:
        return None


def opencv_available() -> bool:
    return _cv2() is not None


def _with_creds(url: str, user: str | None, pwd: str | None) -> str:
    if not user:
        return url
    p = urlparse(url)
    netloc = f"{quote(user)}:{quote(pwd or '')}@{p.hostname or ''}"
    if p.port:
        netloc += f":{p.port}"
    return urlunparse((p.scheme, netloc, p.path, p.params, p.query, p.fragment))


_caps: dict[str, Any] = {}
_caps_lock = threading.Lock()


def _open_capture(cv2: Any, url: str) -> Any:
    # HW decode (VideoToolbox no macOS) p/ aliviar a CPU em HEVC/H264 de alta-res.
    accel = getattr(cv2, "VIDEO_ACCELERATION_ANY", None)
    if accel is not None:
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG, [int(cv2.CAP_PROP_HW_ACCELERATION), int(accel)])
    else:
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    for prop, val in (
        ("CAP_PROP_OPEN_TIMEOUT_MSEC", 6000),
        ("CAP_PROP_READ_TIMEOUT_MSEC", 6000),
        ("CAP_PROP_BUFFERSIZE", 1),
    ):
        p = getattr(cv2, prop, None)
        if p is not None:
            try:
                cap.set(p, val)
            except Exception:
                pass
    return cap


def _grab_rtsp_sync(url: str) -> bytes:
    cv2 = _cv2()
    if cv2 is None:
        raise SnapshotUnavailable(
            "OpenCV não instalado — necessário para RTSP. Instale opencv-python "
            "(requirements-edge.txt) ou use uma URL HTTP de snapshot."
        )
    with _caps_lock:
        cap = _caps.get(url)
        if cap is None or not cap.isOpened():
            cap = _open_capture(cv2, url)
            _caps[url] = cap
        ok, frame = cap.read()
        if not ok or frame is None:
            cap.release()
            cap = _open_capture(cv2, url)
            _caps[url] = cap
            ok, frame = cap.read()
        if not ok or frame is None:
            raise SnapshotUnavailable(
                "Não foi possível ler frame do RTSP (verifique URL, porta e credenciais)."
            )
        ok2, buf = cv2.imencode(".jpg", frame)
        if not ok2:
            raise SnapshotUnavailable("Falha ao codificar o frame em JPEG.")
        return bytes(buf)


async def _grab_http(url: str, user: str | None, pwd: str | None) -> tuple[bytes, str]:
    async with httpx.AsyncClient(timeout=8.0, verify=False, follow_redirects=True) as client:
        if user:
            # tenta Digest (comum em câmeras) e cai para Basic em caso de 401
            for auth in (httpx.DigestAuth(user, pwd or ""), httpx.BasicAuth(user, pwd or "")):
                r = await client.get(url, auth=auth)
                if r.status_code != 401:
                    r.raise_for_status()
                    return r.content, r.headers.get("content-type", "image/jpeg").split(";")[0]
            raise SnapshotUnavailable("Autenticação HTTP falhou (401).")
        r = await client.get(url)
        r.raise_for_status()
        return r.content, r.headers.get("content-type", "image/jpeg").split(";")[0]


async def grab(url: str, username: str | None = None, password: str | None = None) -> tuple[bytes, str]:
    scheme = urlparse(url).scheme.lower()
    if scheme in ("http", "https"):
        return await _grab_http(url, username, password)
    if scheme in ("rtsp", "rtsps"):
        full = _with_creds(url, username, password)
        return await asyncio.to_thread(_grab_rtsp_sync, full), "image/jpeg"
    raise SnapshotUnavailable(f"Esquema de URL não suportado: {scheme!r}")


def release(url: str | None = None) -> None:
    with _caps_lock:
        if url:
            cap = _caps.pop(url, None)
            if cap is not None:
                cap.release()
        else:
            for cap in _caps.values():
                cap.release()
            _caps.clear()
