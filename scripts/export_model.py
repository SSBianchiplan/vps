#!/usr/bin/env python
"""#4 — Exporta o YOLO p/ runtime otimizado de edge (quantização INT8).

Uso:
  python scripts/export_model.py coreml   # Apple Silicon (Neural Engine)
  python scripts/export_model.py onnx      # portável (onnxruntime)
  python scripts/export_model.py engine    # TensorRT (Jetson/NVIDIA)

CoreML/INT8 reduz latência e consumo na borda (§3.6). Em Jetson, 'engine'
(TensorRT) é o alvo. O peso exportado pode então substituir VISIONDESK_YOLO_WEIGHTS.
"""
from __future__ import annotations

import sys
from pathlib import Path

WEIGHTS = "backend/yolo11n.pt"


def main() -> None:
    fmt = sys.argv[1] if len(sys.argv) > 1 else "coreml"
    try:
        from ultralytics import YOLO
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"ultralytics ausente: instale requirements-edge.txt ({exc})")
    w = WEIGHTS if Path(WEIGHTS).exists() else "yolo11n.pt"
    print(f"Exportando {w} → {fmt} (int8=True)…")
    out = YOLO(w).export(format=fmt, int8=True)
    print(f"OK: {out}")


if __name__ == "__main__":
    main()
