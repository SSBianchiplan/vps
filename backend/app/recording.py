"""Gravações automáticas por detecção.

Salva um snapshot (JPEG) quando classes-alvo (padrão: pessoa, cachorro) são
detectadas em uma inferência. Config persistida em data/recording.json; índice
das gravações em data/recordings/index.json; arquivos em data/recordings/.

Acionado após a inferência (REST one-shot e WS contínuo). Cooldown por
fonte+conjunto-de-classes evita inundar o disco.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from .config import get_settings
from .schemas.results import InferenceResult

_DEFAULT_CLASSES = ["person", "dog"]
_DEFAULT_COOLDOWN = 8.0
_MAX_INDEX = 1000
_last: dict[str, float] = {}


def _base_dir() -> Path:
    p = Path(get_settings().db_path).parent / "recordings"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _cfg_file() -> Path:
    return Path(get_settings().db_path).parent / "recording.json"


def _index_file() -> Path:
    return _base_dir() / "index.json"


def load_config() -> dict[str, Any]:
    f = _cfg_file()
    cfg = {}
    if f.exists():
        try:
            cfg = json.loads(f.read_text())
        except Exception:  # noqa: BLE001
            cfg = {}
    return {
        "enabled": bool(cfg.get("enabled", True)),
        "classes": cfg.get("classes") or list(_DEFAULT_CLASSES),
        "cooldown_s": float(cfg.get("cooldown_s", _DEFAULT_COOLDOWN)),
    }


def save_config(partial: dict[str, Any]) -> dict[str, Any]:
    cfg = load_config()
    cfg.update({k: v for k, v in partial.items() if v is not None})
    f = _cfg_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))
    return cfg


def list_recordings(source_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    from .db.repository import repository
    return repository.list_recordings(source_id, limit)


def file_path(rec_id: str) -> Path | None:
    p = _base_dir() / f"{rec_id}.jpg"
    return p if p.exists() else None


def _classes_in_result(result: InferenceResult) -> dict[str, int]:
    r = result.result or {}
    cont = r.get("contagens") or {}
    if cont:
        return {str(k): int(v) for k, v in cont.items()}
    out: dict[str, int] = {}
    for d in r.get("detections") or []:
        c = d.get("classe")
        if c:
            out[c] = out.get(c, 0) + 1
    return out


def _save(source_id: str, mode: str, classes: dict[str, int], image_bytes: bytes,
          trigger: str = "auto") -> dict[str, Any]:
    from . import storage
    from .db.repository import repository
    rec_id = f"rec_{uuid.uuid4().hex[:12]}"
    uri = storage.save(f"{rec_id}.jpg", image_bytes)   # local + S3 (se configurado)
    ts = _now_iso()
    repository.add_recording(rec_id, source_id, ts, mode, trigger, classes, uri)
    return {"id": rec_id, "source_id": source_id, "timestamp": ts,
            "mode": mode, "classes": classes, "trigger": trigger, "image_uri": uri}


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def maybe_capture(result: InferenceResult, image_bytes: bytes) -> dict[str, Any] | None:
    """Grava se habilitado e alguma classe-alvo foi detectada (respeita cooldown)."""
    cfg = load_config()
    if not cfg["enabled"]:
        return None
    targets = {c.lower() for c in cfg["classes"]}
    found = {c: n for c, n in _classes_in_result(result).items() if c.lower() in targets}
    if not found:
        return None
    src = result.source_id or "camera"
    key = f"{src}|{','.join(sorted(found))}"
    now = time.monotonic()
    if now - _last.get(key, 0.0) < cfg["cooldown_s"]:
        return None
    _last[key] = now
    return _save(src, result.mode.value, found, image_bytes, trigger="auto")


def manual_capture(source_id: str, image_bytes: bytes, classes: dict[str, int] | None = None) -> dict[str, Any]:
    return _save(source_id, "MANUAL", classes or {}, image_bytes, trigger="manual")
