"""Streams ao vivo (drone/osmo) RTMP→MediaMTX→player. spec_Drono.md + spec_osmo.md.

Path-aware: `?path=` (allowlist) reusa tudo p/ Visão Aérea (drone_neo2) e Vídeo Osmo
(osmo_pocket). WHEP encaminhado pelo backend (same-origin → sem mixed-content/CORS);
vídeo flui P2P. Record por-path via ffmpeg pull do RTSP do MediaMTX (mp4 compactado).
"""
from __future__ import annotations

import shlex
import signal
import subprocess
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel

from ..config import get_settings

router = APIRouter(prefix="/aerial", tags=["aerial"])

_AERIAL_DIR = Path("data/aerial")            # cwd do backend (backend/)
_recs: dict[str, subprocess.Popen] = {}      # path → ffmpeg de gravação
_rec_files: dict[str, Path] = {}
_tests: dict[str, subprocess.Popen] = {}     # path → ffmpeg publicador de teste (DEV)


def _pick(path: str) -> str:
    s = get_settings()
    return path if path in {s.aerial_path, s.aerial_osmo_path} else s.aerial_path


def _alive(proc: subprocess.Popen | None) -> bool:
    return proc is not None and proc.poll() is None


def _default_test_cmd(p: str) -> str:
    # Vídeo-only + GOP curto: MediaMTX detecta H264 estável (áudio junto dropa vídeo no E-RTMP).
    return (
        "ffmpeg -re -f lavfi -i testsrc=size=1280x720:rate=25 "
        f"-c:v libx264 -preset veryfast -b:v 2M -pix_fmt yuv420p -g 25 -f flv rtmp://localhost:1935/{p}"
    )


@router.get("/config")
def aerial_config(path: str = Query(default="")) -> dict:
    s = get_settings()
    p = _pick(path)
    # Host por-stream: osmo (câmera empurra pela WiFi → IP da LAN); drone (celular c/ Tailscale).
    host = (s.aerial_osmo_rtmp_host if p == s.aerial_osmo_path else s.aerial_rtmp_host)  # "host" ou "host:porta"
    hostport = (host if ":" in host else f"{host}:1935") if host else None
    whep = s.aerial_whep_base
    hls = whep.replace(":8889", ":8888") if ":8889" in whep else whep
    return {
        "path": p,
        "rtmp_host": host,
        "rtmp_url": f"rtmp://{hostport}/{p}" if hostport else None,
        "whep_proxy": f"/api/aerial/whep?path={p}",
        "hls_url": f"{hls}/{p}/index.m3u8",
        "rtsp_url": f"rtsp://<host>:8554/{p}",
    }


@router.get("/status")
async def aerial_status(path: str = Query(default="")) -> dict:
    s = get_settings()
    p = _pick(path)
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.get(f"{s.aerial_api_base}/v3/paths/get/{p}")
        if r.status_code != 200:
            return {"online": False, "readers": 0, "bytes_received": 0}
        d = r.json()
        return {
            "online": bool(d.get("ready")),
            "readers": len(d.get("readers") or []),
            "bytes_received": int(d.get("bytesReceived") or 0),
        }
    except Exception:  # noqa: BLE001 — MediaMTX fora do ar → offline
        return {"online": False, "readers": 0, "bytes_received": 0}


class TestIn(BaseModel):
    command: str | None = None


@router.get("/test")
def aerial_test_status(path: str = Query(default="")) -> dict:
    p = _pick(path)
    return {"running": _alive(_tests.get(p)), "default_cmd": _default_test_cmd(p)}


@router.post("/test/start")
def aerial_test_start(body: TestIn, path: str = Query(default="")) -> dict:
    """Publica um stream de teste (simula a câmera). DEV-only: só ffmpeg, sem shell."""
    p = _pick(path)
    if _alive(_tests.get(p)):
        return {"running": True}
    # Auditoria out/2026: o comando vinha do corpo e o ffmpeg aceita ler e
    # gravar qualquer arquivo/URL (ex.: -i /opt/visiondesk/.env -f data http://...).
    # Comando livre só em desenvolvimento aberto; em produção, só o padrão.
    from ..config import get_settings
    s = get_settings()
    custom = body.command if (s.dev_login and not s.api_key) else None
    try:
        argv = shlex.split((custom or _default_test_cmd(p)).strip())
    except ValueError as exc:
        return {"running": False, "error": f"comando inválido: {exc}"}
    if not argv or argv[0] != "ffmpeg":
        return {"running": False, "error": "só comandos ffmpeg são permitidos"}
    try:
        _tests[p] = subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        return {"running": False, "error": "ffmpeg não encontrado no servidor"}
    except Exception as exc:  # noqa: BLE001
        return {"running": False, "error": str(exc)}
    return {"running": True}


@router.post("/test/stop")
def aerial_test_stop(path: str = Query(default="")) -> dict:
    p = _pick(path)
    proc = _tests.pop(p, None)
    if proc is not None:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:  # noqa: BLE001
            proc.kill()
    return {"running": False}


@router.get("/record")
def aerial_record_status(path: str = Query(default="")) -> dict:
    p = _pick(path)
    f = _rec_files.get(p)
    size = f.stat().st_size if (f and f.exists()) else 0
    return {"recording": _alive(_recs.get(p)), "file": (f.name if f else None), "size": size}


@router.post("/record/start")
def aerial_record_start(path: str = Query(default="")) -> dict:
    """Grava a transmissão (RTSP do MediaMTX) em .mp4 compactado (H.264 CRF 28)."""
    p = _pick(path)
    if _alive(_recs.get(p)):
        return {"recording": True, "file": _rec_files[p].name}
    _AERIAL_DIR.mkdir(parents=True, exist_ok=True)
    out = _AERIAL_DIR / f"{p}_{datetime.now():%Y%m%d_%H%M%S}.mp4"
    # Re-encode CFR (frame rate constante) → reprodução FLUIDA mesmo com jitter de
    # timestamp/quedas do RTMP-sobre-WiFi. crf 20 = alta qualidade. genpts normaliza
    # PTS; faststart põe o moov no início (seek/play suave). Finaliza no stop (SIGINT).
    cmd = [
        "ffmpeg", "-nostdin", "-fflags", "+genpts", "-rtsp_transport", "tcp",
        "-i", f"rtsp://localhost:8554/{p}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-vsync", "cfr",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        "-y", str(out),
    ]
    try:
        _recs[p] = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        return {"recording": False, "error": "ffmpeg não encontrado no servidor"}
    _rec_files[p] = out
    return {"recording": True, "file": out.name}


@router.post("/record/stop")
def aerial_record_stop(path: str = Query(default="")) -> dict:
    p = _pick(path)
    proc = _recs.pop(p, None)
    if proc is not None:
        try:
            proc.send_signal(signal.SIGINT)   # finaliza o mp4 limpo
            proc.wait(timeout=5)
        except Exception:  # noqa: BLE001
            proc.kill()
    f = _rec_files.get(p)
    size = f.stat().st_size if (f and f.exists()) else 0
    return {"recording": False, "file": (f.name if f else None), "size": size}


@router.get("/recordings")
def aerial_recordings(path: str = Query(default="")) -> dict:
    if not _AERIAL_DIR.exists():
        return {"items": []}
    glob = "*.mp4" if path == "all" else f"{_pick(path)}_*.mp4"  # "all" = todas (drone/osmo/cam IP)
    items = [
        {"name": f.name, "size": f.stat().st_size, "ts": int(f.stat().st_mtime)}
        for f in sorted(_AERIAL_DIR.glob(glob), key=lambda x: x.stat().st_mtime, reverse=True)
    ]
    return {"items": items}


@router.get("/recordings/{name}")
def aerial_recording_file(name: str) -> FileResponse:
    f = (_AERIAL_DIR / name).resolve()
    if _AERIAL_DIR.resolve() not in f.parents or not f.exists():
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "gravação não encontrada"})
    return FileResponse(str(f), media_type="video/mp4", filename=name)


@router.post("/whep")
async def aerial_whep(request: Request, path: str = Query(default="")) -> PlainTextResponse:
    """Encaminha o SDP offer ao WHEP do MediaMTX e devolve o answer."""
    s = get_settings()
    p = _pick(path)
    offer = await request.body()
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.post(f"{s.aerial_whep_base}/{p}/whep", content=offer, headers={"Content-Type": "application/sdp"})
    except Exception as exc:  # noqa: BLE001
        return PlainTextResponse(f"WHEP indisponível: {exc}", status_code=502)
    return PlainTextResponse(r.text, status_code=r.status_code, media_type="application/sdp")
