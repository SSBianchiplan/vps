"""Scanner de token (📷 APONTAR/ESCANEAR) — lê o QR e registra no Fio Dourado.

Fonte do frame: imagem do navegador (local/mobile via getUserMedia), câmera IP salva
(RTSP) ou MediaMTX (osmo/drone). Decodifica QR com OpenCV. 1ª leitura = gênese;
leitura de tag existente = observação (carimbo da estação). Carimba operator_id (P05).
"""
from __future__ import annotations

import base64
import re
from typing import Any

from ..discovery import saved, snapshot, stream
from . import engine, operators, tagid

_TAG_RE = re.compile(r"VPS:[A-Z0-9]+:[A-Z0-9]+:[^\s:]+:[0-9]+", re.I)


async def _grab(image_b64: str | None, camera_id: str | None, mtx_path: str | None) -> bytes | None:
    if image_b64:
        b = image_b64.split(",", 1)[-1]          # remove prefixo data:
        try:
            return base64.b64decode(b)
        except Exception:  # noqa: BLE001
            return None
    if camera_id:
        cam = saved.get(camera_id)
        if not cam:
            return None
        url = snapshot._with_creds(saved.rtsp_url(cam), cam.get("username"), cam.get("password"))  # noqa: SLF001
        return await stream.latest_jpeg([url])
    if mtx_path:
        return await stream.latest_jpeg([f"rtsp://localhost:8554/{mtx_path}"])
    return None


def _decode_qr(data: bytes) -> str | None:
    cv2 = stream._cv2()  # noqa: SLF001
    if cv2 is None:
        return None
    try:
        import numpy as np  # type: ignore
        img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            return None
        det = cv2.QRCodeDetector()
        try:
            ok, infos, _pts, _ = det.detectAndDecodeMulti(img)
            if ok:
                for s in infos:
                    if s:
                        return s
        except Exception:  # noqa: BLE001
            pass
        s, _pts, _ = det.detectAndDecode(img)
        return s or None
    except Exception:  # noqa: BLE001
        return None


def _extract_tag(token: str) -> str | None:
    m = _TAG_RE.search(token or "")
    return m.group(0).upper() if m else None


async def scan(station: str, operator_id: str | None, image_b64: str | None,
               camera_id: str | None, mtx_path: str | None) -> dict[str, Any]:
    """RESOLVE (não grava): lê o QR e devolve a OP + as ações válidas p/ o operador escolher."""
    if operator_id:
        operators.identify(station, operator_id=operator_id)
    data = await _grab(image_b64, camera_id, mtx_path)
    if not data:
        return {"ok": False, "message": "sem frame da fonte selecionada"}
    token = _decode_qr(data)
    if not token:
        return {"ok": False, "message": "nenhum QR/token detectado — aproxime e melhore a luz", "frame": True}
    tag = _extract_tag(token)
    if not tag:
        return {"ok": False, "token": token, "message": "QR lido não é um Tag-ID VPS"}

    from . import store
    av = engine.available_actions(tag)
    p = tagid.parse(tag)
    existing = store.get_tag(tag)
    parent = ""
    parents = store.parents_of(tag) if existing else []
    if parents:
        pp = tagid.parse(parents[0]["parent_tag_id"])
        parent = f"{pp.entity_type} {pp.natural_key}" if pp else parents[0]["parent_tag_id"]
    info = {"segment": p.segment if p else None, "entity_type": p.entity_type if p else None,
            "natural_key": p.natural_key if p else None, "instance": p.instance if p else None,
            "parent": parent, "template_id": (existing or {}).get("template_id")}
    return {"ok": True, "resolved": True, "token": token, "tag_id": tag, "genesis": av["genesis"],
            "state": av["state"], "phase": av["phase"], "actions": av["actions"], "info": info,
            "operator_id": operator_id or operators.current(station)}


async def apply(tag_id: str, action: str, station: str, operator_id: str | None,
                payload: dict[str, Any] | None) -> dict[str, Any]:
    """Aplica a ação escolhida pelo operador → registra o evento no Fio (carimba operator_id)."""
    if operator_id:
        operators.identify(station, operator_id=operator_id)
    op = operator_id or operators.current(station)
    pl = {"scan": True, **(payload or {})}
    out = engine.capture({"tag_id": tag_id, "action": action, "vision_mode": "LER", "confidence": 1.0,
                          "source_type": station, "station_id": station, "operator_id": op, "payload": pl})
    if action == "OCCURRENCE_RAISED":
        from . import store
        store.raise_occurrence(tag_id, out.get("phase"), (payload or {}).get("kind", "QUALITY"),
                               (payload or {}).get("severity", "alerta"),
                               (payload or {}).get("note", "ocorrência registrada na estação"))
    return {"ok": True, "tag_id": tag_id, "action": action, "state": out["state"],
            "phase": out["phase"], "operator_id": op,
            "occurrences": (await _open_occ(tag_id))}


async def _open_occ(tag_id: str) -> int:
    from . import store
    return store.open_occurrence_count(tag_id)
