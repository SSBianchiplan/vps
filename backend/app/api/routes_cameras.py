"""Descoberta, câmeras salvas e captura de câmeras IP na rede local."""
from __future__ import annotations

import signal
import subprocess
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .. import audit
from ..config import get_settings
from ..discovery import imaging, ptz, saved, service, snapshot, stream
from ..inference.errors import InferenceError
from ..utils.images import bytes_to_b64

router = APIRouter(prefix="/cameras", tags=["cameras"])

# Gravação server-side de câmera IP (ffmpeg do RTSP → mp4 CFR em data/aerial).
_REC_DIR = Path("data/aerial")
_cam_recs: dict[str, subprocess.Popen] = {}
_cam_files: dict[str, Path] = {}


def _rec_alive(p: subprocess.Popen | None) -> bool:
    return p is not None and p.poll() is None


@router.get("/{cam_id}/record")
def cam_record_status(cam_id: str) -> dict:
    f = _cam_files.get(cam_id)
    size = f.stat().st_size if (f and f.exists()) else 0
    return {"recording": _rec_alive(_cam_recs.get(cam_id)), "file": (f.name if f else None), "size": size}


@router.post("/{cam_id}/record/start")
def cam_record_start(cam_id: str) -> dict:
    cam = saved.get(cam_id)
    if not cam:
        raise HTTPException(status_code=404, detail={"code": "camera_not_found", "message": "câmera não encontrada"})
    if not cam.get("enabled", True):
        raise HTTPException(status_code=409, detail={"code": "camera_disabled", "message": "câmera desligada"})
    if _rec_alive(_cam_recs.get(cam_id)):
        return {"recording": True, "file": _cam_files[cam_id].name}
    if not snapshot.opencv_available():
        raise HTTPException(status_code=503, detail={"code": "opencv_unavailable", "message": "OpenCV necessário"})
    url = snapshot._with_creds(saved.rtsp_url(cam), cam.get("username"), cam.get("password"))
    _REC_DIR.mkdir(parents=True, exist_ok=True)
    out = _REC_DIR / f"cam_{cam_id}_{datetime.now():%Y%m%d_%H%M%S}.mp4"
    cmd = [
        "ffmpeg", "-nostdin", "-fflags", "+genpts", "-rtsp_transport", "tcp", "-i", url,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-vsync", "cfr",
        "-an", "-movflags", "+faststart", "-y", str(out),
    ]
    try:
        _cam_recs[cam_id] = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        return {"recording": False, "error": "ffmpeg não encontrado"}
    _cam_files[cam_id] = out
    audit.record("CAMERA", "RECORD_START", summary=f"gravação iniciada: {cam.get('name') or cam_id}",
                 actor="usuário", source_id=f"cam:{cam_id}", entity_type="camera", entity_id=cam_id,
                 payload={"file": out.name})
    return {"recording": True, "file": out.name}


@router.post("/{cam_id}/record/stop")
def cam_record_stop(cam_id: str) -> dict:
    proc = _cam_recs.pop(cam_id, None)
    if proc is not None:
        try:
            proc.send_signal(signal.SIGINT); proc.wait(timeout=5)
        except Exception:  # noqa: BLE001
            proc.kill()
    f = _cam_files.get(cam_id)
    size = f.stat().st_size if (f and f.exists()) else 0
    if proc is not None:
        audit.record("CAMERA", "RECORD_STOP", summary=f"gravação encerrada: {cam_id}",
                     actor="usuário", source_id=f"cam:{cam_id}", entity_type="camera", entity_id=cam_id,
                     payload={"file": (f.name if f else None), "size": size})
    return {"recording": False, "file": (f.name if f else None), "size": size}


class EnabledIn(BaseModel):
    enabled: bool


@router.post("/{cam_id}/enabled")
def cam_set_enabled(cam_id: str, body: EnabledIn) -> dict:
    """Liga/desliga a câmera no sistema todo (raiz). Ao desligar, para a gravação."""
    cam = saved.set_enabled(cam_id, body.enabled)
    if cam is None:
        raise HTTPException(status_code=404, detail={"code": "camera_not_found", "message": "câmera não encontrada"})
    if not body.enabled:
        cam_record_stop(cam_id)        # desligar = parar total (incl. gravação)
        stream.block(cam["ip"])        # derruba o stream RTSP vivo → vazão cai (raiz)
    else:
        stream.unblock(cam["ip"])      # religar = volta a permitir captura
    audit.record("CAMERA", "ENABLE" if body.enabled else "DISABLE",
                 summary=f"câmera {cam.get('name') or cam_id} {'ligada' if body.enabled else 'desligada'}",
                 severity="info" if body.enabled else "alerta", actor="usuário",
                 source_id=f"cam:{cam_id}", entity_type="camera", entity_id=cam_id)
    return cam


@router.get("/mtx/{path}/mjpeg")
async def mtx_mjpeg(path: str, w: int = Query(default=0)) -> StreamingResponse:
    """MJPEG ao vivo de um path do MediaMTX (drone/osmo) — preview suave no Estúdio."""
    s = get_settings()
    if path not in {s.aerial_path, s.aerial_osmo_path}:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "path inválido"})
    if not snapshot.opencv_available():
        raise HTTPException(status_code=503, detail={"code": "opencv_unavailable", "message": "OpenCV necessário"})
    return StreamingResponse(
        stream.mjpeg([f"rtsp://localhost:8554/{path}"], max_w=w or None),
        media_type=stream.content_type(),
        headers={"Cache-Control": "no-cache, no-store", "Connection": "close", "X-Accel-Buffering": "no"},
    )


# ── Descoberta ──────────────────────────────────────────────────────
@router.get("/scan")
async def scan(
    timeout: float = Query(default=3.0, ge=0.5, le=10.0),
    full: bool = Query(default=False),
):
    result = await service.scan(timeout=timeout)
    if not full:
        result["cameras"] = [c for c in result["cameras"] if c["likely_camera"]]
    result["opencv"] = snapshot.opencv_available()
    return result


@router.get("/opencv")
def opencv_status() -> dict:
    return {"opencv": snapshot.opencv_available()}


@router.get("/streams/stats")
def streams_stats() -> dict:
    """Vazão agregada dos streams de câmera ativos (monitoramento do Painel)."""
    return stream.stats()


@router.get("/{cam_id}/webrtc")
def webrtc_url(cam_id: str) -> dict:
    """#3 — URL WebRTC via media server externo (MediaMTX/go2rtc), se configurado.

    Um decode → fan-out p/ N viewers (resolve o gargalo N-clientes × M-câmeras do
    MJPEG). Configure VISIONDESK_RESTREAM_BASE apontando p/ o media server.
    """
    from ..config import get_settings
    base = get_settings().restream_base
    if not base:
        return {"available": False, "message": "media server não configurado (VISIONDESK_RESTREAM_BASE)"}
    return {"available": True, "whep": f"{base.rstrip('/')}/{cam_id}/whep", "hls": f"{base.rstrip('/')}/{cam_id}/index.m3u8"}


# ── Câmeras salvas (senhas só no backend) ───────────────────────────
class SavedCameraIn(BaseModel):
    name: str
    ip: str = ""
    username: str | None = None
    password: str | None = None
    port: int = 554
    path: str = "/onvif1"
    serial: str | None = None       # Cloud ID / SN (Xiongmai/XMEye/ICSee)
    provider: str | None = None     # ex.: "xmeye"
    share_key: str | None = None    # token de compartilhamento da nuvem


@router.get("/saved")
def list_saved() -> list[dict]:
    return saved.list_public()


@router.post("/saved")
def add_saved(body: SavedCameraIn) -> dict:
    cam = saved.add(
        name=body.name, ip=body.ip, username=body.username,
        password=body.password, port=body.port, path=body.path,
        serial=body.serial, provider=body.provider, share_key=body.share_key,
    )
    audit.record("CAMERA", "CREATE", summary=f"câmera cadastrada: {body.name or body.ip}",
                 actor="usuário", source_id=f"cam:{cam.get('id') or ''}", entity_type="camera",
                 entity_id=str(cam.get("id") or ""), payload={"ip": body.ip, "port": body.port})
    return cam


@router.post("/saved/{cam_id}/resolve")
async def resolve_saved(cam_id: str, timeout: float = Query(default=3.0, ge=0.5, le=10.0)) -> dict:
    """Localiza na rede local o IP de uma câmera (ex.: cadastrada por QR de nuvem XMEye/ICSee)
    e vincula automaticamente. Prefere Xiongmai/ICSee (porta 34567), depois ONVIF, depois 554."""
    cam = saved.get(cam_id)
    if cam is None:
        raise HTTPException(status_code=404, detail="câmera não encontrada")
    result = await service.scan(timeout=timeout)
    cands = [c for c in result.get("cameras", []) if c.get("likely_camera")]
    cands.sort(key=lambda c: (34567 in c.get("ports", []), bool(c.get("onvif")), 554 in c.get("ports", [])), reverse=True)
    if not cands:
        return {"found": False, "camera": saved.public(cam), "candidates": []}
    chosen = cands[0]
    port = 554 if 554 in chosen.get("ports", []) else cam.get("port", 554)
    updated = saved.set_ip(cam_id, chosen["ip"], port=port)
    audit.record("CAMERA", "UPDATE", summary=f"câmera localizada na rede: {chosen['ip']}",
                 actor="sistema", source_id=f"cam:{cam_id}", entity_type="camera", entity_id=cam_id,
                 payload={"ip": chosen["ip"], "resolved": True})
    return {"found": True, "camera": updated, "candidates": cands}


@router.delete("/saved/{cam_id}")
def delete_saved(cam_id: str) -> dict:
    ok = saved.delete(cam_id)
    if ok:
        audit.record("CAMERA", "DELETE", summary=f"câmera removida: {cam_id}", severity="alerta",
                     actor="usuário", source_id=f"cam:{cam_id}", entity_type="camera", entity_id=cam_id)
    return {"deleted": ok}


# ── Captura de frame ────────────────────────────────────────────────
class SnapshotIn(BaseModel):
    # informe camera_id (resolve creds no backend) OU url+credenciais.
    camera_id: str | None = None
    url: str | None = None
    username: str | None = None
    password: str | None = None
    max_w: int | None = None   # largura-alvo da captura RTSP (0/None = padrão; reduz p/ acelerar)


class DecodeQrIn(BaseModel):
    image_b64: str


@router.post("/decode_qr")
def decode_qr(body: DecodeQrIn) -> dict:
    """Decodifica um QR (frame base64 da câmera) via cv2 → texto, p/ configurar câmera IP por QR."""
    import base64

    from ..vps.scan import _decode_qr
    raw = body.image_b64.split(",", 1)[-1]
    try:
        data = base64.b64decode(raw)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="base64 inválido") from e
    return {"text": _decode_qr(data)}


@router.post("/snapshot")
async def take_snapshot(body: SnapshotIn) -> dict:
    if body.camera_id:
        cam = saved.get(body.camera_id)
        if not cam:
            raise HTTPException(status_code=404, detail={"code": "camera_not_found", "message": "câmera salva não encontrada"})
        if not cam.get("enabled", True):
            raise HTTPException(status_code=409, detail={"code": "camera_disabled", "message": "câmera desligada"})
        url = saved.rtsp_url(cam)
        username = cam.get("username")
        password = cam.get("password")
    elif body.url:
        url, username, password = body.url, body.username, body.password
    else:
        raise HTTPException(status_code=400, detail={"code": "missing_target", "message": "informe camera_id ou url"})

    try:
        # RTSP: reusa o stream de baixa latência (1 conexão por câmera, frame fresco
        # já reduzido ~1280px/Q72) → captação muito mais rápida que reabrir/ler full-res.
        if url.lower().startswith(("rtsp://", "rtsps://")):
            if not snapshot.opencv_available():
                raise HTTPException(status_code=503, detail={"code": "opencv_unavailable", "message": "OpenCV necessário p/ RTSP"})
            full = snapshot._with_creds(url, username, password)
            data = await stream.latest_jpeg([full], max_w=body.max_w)
            if data is None:
                raise HTTPException(status_code=503, detail={"code": "snapshot_unavailable", "message": "Sem frame do RTSP (verifique URL, porta e credenciais)."})
            media = "image/jpeg"
        else:
            data, media = await snapshot.grab(url, username, password)
    except HTTPException:
        raise
    except InferenceError as exc:
        raise HTTPException(status_code=503, detail={"code": exc.code, "message": exc.message})
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail={"code": "snapshot_error", "message": str(exc)})
    return {"image_b64": bytes_to_b64(data), "media_type": media}


# ── Stream MJPEG ao vivo (baixa latência) ───────────────────────────
@router.get("/{cam_id}/mjpeg")
async def mjpeg_stream(cam_id: str, sub: bool = Query(default=False), w: int = Query(default=0)) -> StreamingResponse:
    cam = saved.get(cam_id)
    if not cam:
        raise HTTPException(status_code=404, detail={"code": "camera_not_found", "message": "câmera não encontrada"})
    if not cam.get("enabled", True):
        raise HTTPException(status_code=409, detail={"code": "camera_disabled", "message": "câmera desligada"})
    if not snapshot.opencv_available():
        raise HTTPException(status_code=503, detail={"code": "opencv_unavailable", "message": "OpenCV necessário p/ RTSP"})
    url = snapshot._with_creds(saved.rtsp_url(cam), cam.get("username"), cam.get("password"))
    if sub:
        # substream real (ONVIF) → guess onvif2 → main, nessa ordem (fallback automático)
        urls: list[str] = []
        onvif_sub = await ptz.discover_substream(cam["ip"], cam.get("username"), cam.get("password"))
        if onvif_sub:
            urls.append(onvif_sub)
        urls += stream.substream_candidates(url)
    else:
        urls = [url]
    return StreamingResponse(
        stream.mjpeg(urls, max_w=w or None),
        media_type=stream.content_type(),
        headers={"Cache-Control": "no-cache, no-store", "Connection": "close", "X-Accel-Buffering": "no"},
    )


# ── PTZ (ONVIF, best-effort) ────────────────────────────────────────
class PtzIn(BaseModel):
    camera_id: str | None = None
    ip: str | None = None
    username: str | None = None
    password: str | None = None
    pan: float = 0.0   # [-1,1] esquerda/direita
    tilt: float = 0.0  # [-1,1] baixo/cima
    zoom: float = 0.0  # [-1,1] out/in


def _ptz_target(body: PtzIn) -> tuple[str, str | None, str | None]:
    if body.camera_id:
        cam = saved.get(body.camera_id)
        if not cam:
            raise HTTPException(status_code=404, detail={"code": "camera_not_found", "message": "câmera não encontrada"})
        return cam["ip"], cam.get("username"), cam.get("password")
    if body.ip:
        return body.ip, body.username, body.password
    raise HTTPException(status_code=400, detail={"code": "missing_target", "message": "informe camera_id ou ip"})


# ── Configurações do modo de câmera (ONVIF Imaging) ─────────────────
def _cam_target(cam_id: str) -> tuple[str, str | None, str | None]:
    cam = saved.get(cam_id)
    if not cam:
        raise HTTPException(status_code=404, detail={"code": "camera_not_found", "message": "câmera não encontrada"})
    return cam["ip"], cam.get("username"), cam.get("password")


class ImagingIn(BaseModel):
    # dia/noite via filtro IR-cut: ON=dia(cor) · OFF=noite(P&B/IR) · AUTO=automático
    ir_cut_filter: str | None = None
    brightness: float | None = None
    contrast: float | None = None
    color_saturation: float | None = None
    sharpness: float | None = None


@router.get("/{cam_id}/imaging")
async def get_imaging(cam_id: str) -> dict:
    ip, user, pwd = _cam_target(cam_id)
    return await imaging.get_settings(ip, user, pwd)


@router.post("/{cam_id}/imaging")
async def set_imaging(cam_id: str, body: ImagingIn) -> dict:
    ip, user, pwd = _cam_target(cam_id)
    return await imaging.set_settings(
        ip, user, pwd,
        ir_cut_filter=body.ir_cut_filter, brightness=body.brightness,
        contrast=body.contrast, color_saturation=body.color_saturation, sharpness=body.sharpness,
    )


class LightIn(BaseModel):
    on: bool
    kind: str | None = None      # "white" (padrão) | "ir"
    mode: str | None = None      # "manual" (liga fixa) | "auto" (acende na detecção)


@router.post("/{cam_id}/light")
async def set_light(cam_id: str, body: LightIn) -> dict:
    """Controla a luz LED branca da câmera IP.

    Xiongmai (XM) ignora o aux ONVIF → usa DVRIP nativo (porta 34567). mode="auto"
    usa o modo Intelligent (a câmera acende sozinha na detecção dela). Para outras
    marcas, cai no SendAuxiliaryCommand ONVIF.
    """
    ip, user, pwd = _cam_target(cam_id)
    kind = body.kind or "white"
    mode = body.mode or "manual"
    res: dict = {"ok": False, "supported": False}
    if kind == "white":
        from ..discovery import xm_dvrip
        res = await xm_dvrip.set_white_light(ip, user, pwd, body.on, mode=mode)
    if not res.get("ok"):                       # fallback ONVIF (não-XM / luz IR)
        onvif = await ptz.set_light(ip, user, pwd, body.on, kind=kind)
        if onvif.get("ok") or not res.get("supported"):
            res = onvif
    if res.get("ok"):
        act = ("LIGHT_AUTO" if mode == "auto" else "LIGHT_ON") if body.on else "LIGHT_OFF"
        audit.record("CAMERA", act,
                     summary=f"luz {'automática' if mode=='auto' else 'branca'} {'ligada' if body.on else 'apagada'}: {cam_id}",
                     actor="usuário", source_id=f"cam:{cam_id}", entity_type="camera", entity_id=cam_id)
    return res


@router.post("/ptz/move")
async def ptz_move(body: PtzIn) -> dict:
    ip, user, pwd = _ptz_target(body)
    return await ptz.move(ip, user, pwd, pan=body.pan, tilt=body.tilt, zoom=body.zoom)


@router.post("/ptz/stop")
async def ptz_stop(body: PtzIn) -> dict:
    ip, user, pwd = _ptz_target(body)
    return await ptz.stop(ip, user, pwd)


# ── Presets PTZ (gravar/recuperar posição) ──────────────────────────
class PresetIn(BaseModel):
    name: str | None = None


@router.get("/{cam_id}/ptz/presets")
async def ptz_presets(cam_id: str) -> dict:
    ip, user, pwd = _cam_target(cam_id)
    return await ptz.get_presets(ip, user, pwd)


@router.post("/{cam_id}/ptz/presets")
async def ptz_set_preset(cam_id: str, body: PresetIn) -> dict:
    ip, user, pwd = _cam_target(cam_id)
    return await ptz.set_preset(ip, user, pwd, body.name)


@router.post("/{cam_id}/ptz/presets/{preset_token}/goto")
async def ptz_goto_preset(cam_id: str, preset_token: str) -> dict:
    ip, user, pwd = _cam_target(cam_id)
    return await ptz.goto_preset(ip, user, pwd, preset_token)


@router.delete("/{cam_id}/ptz/presets/{preset_token}")
async def ptz_remove_preset(cam_id: str, preset_token: str) -> dict:
    ip, user, pwd = _cam_target(cam_id)
    return await ptz.remove_preset(ip, user, pwd, preset_token)
