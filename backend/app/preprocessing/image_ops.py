"""Pré-processamento de frames: resize, crop de ROI, realce.

Resolução de inferência ≠ resolução de preview (Seção 9 da spec): reduzimos o
frame antes de enviar ao modelo. Usa Pillow; melhorias opcionais via OpenCV.
"""
from __future__ import annotations

from PIL import Image, ImageOps

from ..schemas.tasks import ROI
from ..utils.images import open_image, to_jpeg


def resize_max_side(img: Image.Image, max_side: int = 1024) -> Image.Image:
    """Reduz mantendo proporção para que o maior lado <= max_side."""
    w, h = img.size
    longest = max(w, h)
    if longest <= max_side:
        return img
    scale = max_side / longest
    return img.resize((round(w * scale), round(h * scale)), Image.Resampling.LANCZOS)


def crop_roi(img: Image.Image, roi: ROI, pad: float = 0.04) -> Image.Image:
    """Recorta a ROI (coords normalizadas) com pequena folga. Caminho híbrido."""
    rect = roi.as_rect()
    w, h = img.size
    if rect is not None:
        x, y, rw, rh = rect
    else:
        # line/zone → bounding box dos pontos
        xs = [p[0] for p in roi.points] or [0.0, 1.0]
        ys = [p[1] for p in roi.points] or [0.0, 1.0]
        x, y, rw, rh = min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)

    x0 = max(0, int((x - pad) * w))
    y0 = max(0, int((y - pad) * h))
    x1 = min(w, int((x + rw + pad) * w))
    y1 = min(h, int((y + rh + pad) * h))
    if x1 <= x0 or y1 <= y0:
        return img
    return img.crop((x0, y0, x1, y1))


def enhance_for_ocr(img: Image.Image) -> Image.Image:
    """Realce leve para OCR: escala de cinza + autocontraste."""
    gray = ImageOps.grayscale(img)
    return ImageOps.autocontrast(gray, cutoff=1)


def prepare_for_vlm(
    data: bytes,
    roi: ROI | None = None,
    max_side: int = 1024,
    quality: int = 85,
) -> bytes:
    """Pipeline padrão para o VLM: (crop ROI) → resize → JPEG."""
    img = open_image(data)
    if roi is not None and roi.points:
        img = crop_roi(img, roi)
    img = resize_max_side(img, max_side)
    return to_jpeg(img, quality=quality)


def prepare_for_edge(
    data: bytes,
    roi: ROI | None = None,
    max_side: int = 640,
) -> bytes:
    """Pipeline para o detector edge: resize agressivo (ex. 640px para YOLO)."""
    img = open_image(data)
    if roi is not None and roi.points:
        img = crop_roi(img, roi)
    img = resize_max_side(img, max_side)
    return to_jpeg(img, quality=88)
