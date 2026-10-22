"""LGPD — anonimização (blur facial) + retenção de imagens (SPEC_VPS §15).

Imagens podem conter pessoas → política de retenção + blur facial + acesso restrito.
Blur usa o MESMO detector do módulo facial (biometrics/face.py): YuNet quando os
modelos estão presentes, Haar como reserva. Antes tinha um Haar próprio aqui — e
o OpenCV 5 removeu o CascadeClassifier, o que deixaria o blur em no-op silencioso
com a política LGPD ligada. Retenção apaga frames/gravações além da janela.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from ..config import get_settings
from ..logging_conf import get_logger

log = get_logger("visiondesk.vps.lgpd")
_blur_override: bool | None = None


def blur_enabled() -> bool:
    return get_settings().vps_lgpd_blur if _blur_override is None else _blur_override


def set_blur(on: bool) -> None:
    global _blur_override
    _blur_override = on


def _detector_ok() -> bool:
    try:
        from ..biometrics import face
        return face.available()
    except Exception:  # noqa: BLE001
        return False


def anonymize(jpeg: bytes) -> bytes:
    """Borra rostos no JPEG. Retorna original se desligado / sem cv2 / sem rosto."""
    if not blur_enabled():
        return jpeg
    if not _detector_ok():
        return jpeg
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
        from ..biometrics import face
        img = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            return jpeg
        faces = face.detect_faces(img)
        for (x, y, w, h) in faces:
            roi = img[y:y + h, x:x + w]
            k = max(15, (w // 3) | 1)  # kernel ímpar proporcional
            img[y:y + h, x:x + w] = cv2.GaussianBlur(roi, (k, k), 0)
        if len(faces) == 0:
            return jpeg
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return bytes(buf) if ok else jpeg
    except Exception:  # noqa: BLE001
        log.exception("anonymize falhou (não fatal)")
        return jpeg


def _dirs() -> list[Path]:
    s = get_settings()
    dirs = [s.frames_path(), Path("data/aerial")]
    return [d for d in dirs if d.exists()]


def retention_sweep(days: int | None = None) -> dict[str, Any]:
    """Apaga arquivos além da janela de retenção. Retorna o que foi removido."""
    s = get_settings()
    days = days if days is not None else s.vps_retention_days
    cutoff = time.time() - days * 86400
    removed = 0
    freed = 0
    for d in _dirs():
        for f in d.glob("*"):
            try:
                if f.is_file() and f.stat().st_mtime < cutoff:
                    freed += f.stat().st_size
                    f.unlink()
                    removed += 1
            except OSError:
                pass
    return {"removed": removed, "freed_mb": round(freed / 1e6, 2), "retention_days": days}


def status() -> dict[str, Any]:
    s = get_settings()
    counts = {}
    for d in _dirs():
        counts[d.name] = sum(1 for f in d.glob("*") if f.is_file())
    return {"blur": blur_enabled(), "blur_available": _detector_ok(),
            "retention_days": s.vps_retention_days, "files": counts}
