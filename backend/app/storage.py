"""Object store p/ frames/gravações (#2) — abstração com fallback gracioso.

Default: filesystem local (data/recordings). Se VISIONDESK_S3_ENDPOINT setado e
boto3 disponível, também espelha em S3/MinIO e retorna URI s3:// (Image_URI §6.1).
Migrar p/ object store + Postgres é trocar esta camada — o resto não muda.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import get_settings
from .logging_conf import get_logger

log = get_logger("visiondesk.storage")
_s3: Any | None = None
_s3_tried = False


def _local_dir() -> Path:
    p = Path(get_settings().db_path).parent / "recordings"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _s3_client() -> Any | None:
    global _s3, _s3_tried
    s = get_settings()
    if not s.s3_endpoint:
        return None
    if _s3 is not None or _s3_tried:
        return _s3
    _s3_tried = True
    try:
        import boto3  # type: ignore
        _s3 = boto3.client("s3", endpoint_url=s.s3_endpoint)
        try:
            _s3.head_bucket(Bucket=s.s3_bucket)
        except Exception:  # noqa: BLE001
            _s3.create_bucket(Bucket=s.s3_bucket)
        log.info("S3/MinIO conectado em %s (bucket=%s)", s.s3_endpoint, s.s3_bucket)
    except Exception as exc:  # noqa: BLE001
        log.warning("S3 indisponível (%s) — usando filesystem local.", exc)
        _s3 = None
    return _s3


def save(key: str, data: bytes) -> str:
    """Grava local (sempre) e em S3 (se configurado). Retorna o Image_URI."""
    path = _local_dir() / key
    path.write_bytes(data)
    c = _s3_client()
    if c is not None:
        s = get_settings()
        try:
            c.put_object(Bucket=s.s3_bucket, Key=key, Body=data, ContentType="image/jpeg")
            return f"s3://{s.s3_bucket}/{key}"
        except Exception:  # noqa: BLE001
            pass
    return f"file://{path}"
