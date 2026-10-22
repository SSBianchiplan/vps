"""Detecção de anomalia não supervisionada (PatchCore-lite) — §3.4.

Sem rótulos de defeito: aprende a distribuição do "normal" a partir de frames
de referência (embeddings do YOLO11, 256-d, totalmente local) e pontua novos
frames pela distância à memória de normais. Score alto = desvio do normal.

Memory bank por perfil (source_id) persistido em data/anomaly/{perfil}.npz:
  X (N,256) embeddings L2-normalizados · mu/sigma/tau (calibração NN-distance).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ...config import get_settings
from .detector import yolo_detector


def _dir() -> Path:
    p = Path(get_settings().db_path).parent / "anomaly"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _file(profile: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", profile or "global")
    return _dir() / f"{safe}.npz"


def available() -> bool:
    return yolo_detector.available()


def _embed_norm(image_bytes: bytes):
    import numpy as np
    v = yolo_detector.embed(image_bytes)
    n = np.linalg.norm(v) + 1e-8
    return (v / n).astype("float32")


def _pairwise_nn_stats(X) -> tuple[float, float]:
    """Para cada ref, distância ao vizinho mais próximo no banco → (média, desvio)."""
    import numpy as np
    if len(X) < 2:
        return 0.0, 0.0
    sims = X @ X.T
    np.fill_diagonal(sims, -1.0)
    nn_sim = sims.max(axis=1)
    nn_dist = np.sqrt(np.clip(2.0 - 2.0 * nn_sim, 0, None))
    return float(nn_dist.mean()), float(nn_dist.std())


def fit(profile: str, images: list[bytes]) -> dict[str, Any]:
    import numpy as np
    if not available():
        return {"ok": False, "supported": False, "message": "edge (YOLO) indisponível"}
    vecs = [_embed_norm(b) for b in images if b]
    if len(vecs) < 2:
        return {"ok": False, "supported": True, "message": "forneça ≥2 frames normais"}
    X = np.stack(vecs)
    mu, sigma = _pairwise_nn_stats(X)
    tau = mu + 3 * sigma if sigma > 0 else (mu * 1.5 if mu > 0 else 0.35)
    np.savez(_file(profile), X=X, mu=mu, sigma=sigma, tau=tau)
    return {"ok": True, "supported": True, "n_ref": int(len(X)), "tau": round(float(tau), 4)}


def status(profile: str) -> dict[str, Any]:
    import numpy as np
    f = _file(profile)
    if not f.exists():
        return {"fitted": False, "n_ref": 0, "supported": available()}
    d = np.load(f)
    return {"fitted": True, "n_ref": int(d["X"].shape[0]), "tau": round(float(d["tau"]), 4), "supported": available()}


def score(profile: str, image_bytes: bytes) -> dict[str, Any]:
    import numpy as np
    if not available():
        return {"supported": False, "message": "edge indisponível"}
    f = _file(profile)
    if not f.exists():
        return {"supported": True, "fitted": False, "message": "perfil não treinado (fit primeiro)"}
    d = np.load(f)
    X, tau = d["X"], float(d["tau"])
    q = _embed_norm(image_bytes)
    sims = X @ q
    nn_sim = float(sims.max())
    dist = float(np.sqrt(max(0.0, 2.0 - 2.0 * nn_sim)))
    norm = dist / tau if tau > 0 else dist
    return {
        "supported": True, "fitted": True,
        "anomaly_score": round(min(1.0, norm), 3),     # 0..1 (≥1 → anômalo)
        "distance": round(dist, 4), "tau": round(tau, 4),
        "anomalo": dist > tau, "n_ref": int(X.shape[0]),
    }
