#!/usr/bin/env python
"""#9 — Gerador de dados sintéticos (augmentations) p/ treino offline.

Expande um diretório de imagens reais com variações (flip, brilho, rotação,
ruído, blur) — balanceia classes e simula condições (low-light, vibração) sem
nova coleta (§3.7). Não toca o runtime; alimenta o treino dos modelos 3.1–3.4.

Uso:
  python scripts/synth_data.py <dir_entrada> <dir_saida> [--n 4]
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter

EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def variants(img: Image.Image) -> dict[str, Image.Image]:
    return {
        "flip": img.transpose(Image.FLIP_LEFT_RIGHT),
        "bright": ImageEnhance.Brightness(img).enhance(1.4),
        "dark": ImageEnhance.Brightness(img).enhance(0.6),
        "rotate": img.rotate(7, expand=False),
        "blur": img.filter(ImageFilter.GaussianBlur(1.2)),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("indir"); ap.add_argument("outdir")
    ap.add_argument("--n", type=int, default=5, help="variações por imagem (máx 5)")
    a = ap.parse_args()
    out = Path(a.outdir); out.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in Path(a.indir).iterdir():
        if f.suffix.lower() not in EXTS:
            continue
        img = Image.open(f).convert("RGB")
        for i, (name, v) in enumerate(variants(img).items()):
            if i >= a.n:
                break
            v.save(out / f"{f.stem}__{name}.jpg", quality=88)
            n += 1
    print(f"Geradas {n} imagens sintéticas em {out}")


if __name__ == "__main__":
    main()
