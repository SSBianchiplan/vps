"""Versão de modelo p/ rastreabilidade (§5.2/§9): todo evento carrega
Model_Version → auditável e reversível (rollback).

- Pesos locais (.pt/.onnx/.mlmodel): hash curto do arquivo (versão do artefato).
- VLM/Claude: o próprio id do modelo já é a versão.
- Demais: versão da app.
"""
from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

APP_VERSION = "0.1.0"


@lru_cache(maxsize=32)
def _file_hash(path: str) -> str | None:
    p = Path(path)
    if not p.exists():
        return None
    h = hashlib.sha1()
    h.update(p.read_bytes())
    return h.hexdigest()[:8]


@lru_cache(maxsize=64)
def version_for(model_name: str) -> str:
    if not model_name:
        return APP_VERSION
    if "claude" in model_name:        # id do modelo já é a versão
        return model_name
    h = _file_hash(model_name)        # ex.: yolo11n.pt → sha curto
    if h:
        return f"{Path(model_name).name}@{h}"
    return f"{model_name}@{APP_VERSION}"
