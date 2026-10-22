"""Utilidades de imagem (codificação base64, hash, dimensões).

Implementadas com Pillow (instala em qualquer ambiente). O caminho edge pode
usar numpy/OpenCV, importados de forma preguiçosa onde necessário.
"""
from __future__ import annotations

import base64
import hashlib
import io

from PIL import Image


def strip_data_uri(b64: str) -> str:
    """Remove prefixo 'data:image/...;base64,' se presente."""
    if "," in b64 and b64.strip().startswith("data:"):
        return b64.split(",", 1)[1]
    return b64


def b64_to_bytes(b64: str) -> bytes:
    return base64.b64decode(strip_data_uri(b64))


def bytes_to_b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def open_image(data: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    img.load()
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    return img


def image_size(data: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(data)) as img:
        return img.size  # (w, h)


def frame_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def to_jpeg(img: Image.Image, quality: int = 85) -> bytes:
    if img.mode != "RGB":
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def media_type_of(data: bytes) -> str:
    """Detecta o media type a partir dos magic bytes (jpeg/png/webp)."""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"
