"""Pipelines via caminho VLM com o cliente Claude monkeypatchado (sem rede)."""
from __future__ import annotations

import io

import pytest
from PIL import Image

from app.inference.vlm.claude_client import claude_vlm
from app.pipelines.analyze_pipeline import AnalyzePipeline
from app.pipelines.base import FrameContext
from app.pipelines.count_pipeline import CountPipeline
from app.pipelines.read_pipeline import ReadPipeline
from app.schemas.tasks import TaskConfig


def _jpeg() -> bytes:
    img = Image.new("RGB", (64, 48), (120, 120, 120))
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    return buf.getvalue()


def _ctx() -> FrameContext:
    return FrameContext(image_bytes=_jpeg(), media_type="image/jpeg", frame_seq=1, continuous=False)


async def test_count_vlm_mapping(monkeypatch):
    async def fake_count(image_bytes, media_type, params, prompt):
        return {"itens": [{"classe": "caixa", "quantidade": 3}, {"classe": "palete", "quantidade": 1}], "total": 4}

    monkeypatch.setattr(claude_vlm, "count", fake_count)
    task = TaskConfig.model_validate({"mode": "CONTAR", "params": {"mode": "CONTAR"}})
    result = await CountPipeline(use_edge=False).run(_ctx(), task)
    assert result.pipeline == "vlm"
    assert result.result["contagens"] == {"caixa": 3, "palete": 1}
    assert result.result["total"] == 4


async def test_analyze_label_mapping(monkeypatch):
    async def fake_analyze(image_bytes, media_type, params, prompt):
        return {
            "veredito": "OK",
            "confianca": 0.91,
            "itens_verificados": [{"criterio": "etiqueta", "atende": True, "observacao": ""}],
            "resumo": "tudo certo",
        }

    monkeypatch.setattr(claude_vlm, "analyze", fake_analyze)
    task = TaskConfig.model_validate(
        {
            "mode": "ANALISAR",
            "params": {"mode": "ANALISAR", "criterios": ["etiqueta presente"], "rotulo_ok": "APROVADO"},
        }
    )
    result = await AnalyzePipeline().run(_ctx(), task)
    assert result.result["veredito"] == "APROVADO"
    assert result.confidence == pytest.approx(0.91, abs=1e-3)


async def test_read_roi_filter_and_regex(monkeypatch):
    async def fake_read(image_bytes, media_type, params, prompt):
        return {
            "leituras": [
                {"texto": "OP-10482", "campo": "n_op", "confianca": 0.95, "bbox": [0.1, 0.1, 0.2, 0.05]},
                {"texto": "RUIDO", "campo": "", "confianca": 0.5, "bbox": [0.9, 0.9, 0.05, 0.05]},
            ]
        }

    monkeypatch.setattr(claude_vlm, "read", fake_read)
    task = TaskConfig.model_validate(
        {
            "mode": "LER",
            "params": {"mode": "LER", "pattern_regex": r"OP-\d+", "prefer_vlm": True},
            "roi": {"shape": "rect", "points": [[0.0, 0.0], [0.5, 0.5]]},
        }
    )
    result = await ReadPipeline(use_edge=False).run(_ctx(), task)
    leituras = result.result["leituras"]
    assert len(leituras) == 1  # "RUIDO" fora da ROI foi filtrado
    assert leituras[0]["texto"] == "OP-10482"
    assert leituras[0]["valido"] is True
