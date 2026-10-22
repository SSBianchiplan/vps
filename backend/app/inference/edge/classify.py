"""Classificação de imagem — CNN (§3.1) e ViT (§3.3) reais via torchvision.

- CNN: MobileNetV3-Small (leve, rápido) — cavalo de batalha de classificação.
- ViT: ViT-B/16 (Vision Transformer) — contexto global por atenção.
Ambos pré-treinados (ImageNet); pesos baixados no 1º uso e cacheados. Inferência
local (edge), sem token. Em domínio industrial, troca-se o head por fine-tune.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

_BACKBONES = {
    "cnn": ("mobilenet_v3_small", "MobileNet_V3_Small_Weights"),
    "vit": ("vit_b_16", "ViT_B_16_Weights"),
}


def available() -> bool:
    try:
        import torch  # noqa: F401
        import torchvision  # noqa: F401
        return True
    except Exception:
        return False


@lru_cache(maxsize=2)
def _load(kind: str):
    import torchvision.models as M
    fn_name, w_name = _BACKBONES[kind]
    weights = getattr(M, w_name).IMAGENET1K_V1
    model = getattr(M, fn_name)(weights=weights)
    model.eval()
    return model, weights


def classify(image_bytes: bytes, kind: str = "cnn", topk: int = 5) -> dict[str, Any]:
    if kind not in _BACKBONES:
        kind = "cnn"
    if not available():
        return {"supported": False, "message": "torch/torchvision ausente (requirements-edge)"}
    import io
    import torch
    from PIL import Image

    model, weights = _load(kind)
    tf = weights.transforms()
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    x = tf(img).unsqueeze(0)
    with torch.no_grad():
        probs = model(x).softmax(dim=1)[0]
    k = min(topk, probs.shape[0])
    p, idx = probs.topk(k)
    cats = weights.meta["categories"]
    results = [{"label": cats[int(i)], "conf": round(float(v), 4)} for v, i in zip(p, idx)]
    return {"supported": True, "backbone": _BACKBONES[kind][0], "results": results}
