"""Validação dos schemas/contratos (união discriminada por modo)."""
from __future__ import annotations

from app.schemas.enums import Mode, ROIShape
from app.schemas.results import AnalyzeResult, CountResult, ReadResult
from app.schemas.tasks import AnalyzeParams, CountParams, ROI, TaskConfig


def test_taskconfig_discriminated_union_count():
    task = TaskConfig.model_validate(
        {
            "mode": "CONTAR",
            "params": {"mode": "CONTAR", "classes_alvo": ["person"], "conf_threshold": 0.4},
        }
    )
    assert isinstance(task.typed_params(), CountParams)
    assert task.typed_params().classes_alvo == ["person"]


def test_taskconfig_analyze_with_roi():
    task = TaskConfig.model_validate(
        {
            "mode": "ANALISAR",
            "params": {"mode": "ANALISAR", "criterios": ["etiqueta presente"]},
            "roi": {"shape": "rect", "points": [[0.1, 0.1], [0.5, 0.4]]},
        }
    )
    assert isinstance(task.typed_params(), AnalyzeParams)
    assert task.roi is not None and task.roi.shape == ROIShape.RECT
    assert task.roi.as_rect() == (0.1, 0.1, 0.5, 0.4)


def test_roi_line_bbox_fallback():
    roi = ROI(shape=ROIShape.LINE, points=[(0.2, 0.5), (0.8, 0.5)])
    assert roi.as_rect() is None  # linha não é retângulo


def test_result_models_roundtrip():
    r = ReadResult(leituras=[{"texto": "OP-10482", "campo": "n_op", "confianca": 0.97}])
    assert r.leituras[0].texto == "OP-10482"
    c = CountResult(contagens={"peca_a": 12}, total=12)
    assert c.total == 12
    a = AnalyzeResult(veredito="NOK", confianca=0.88, resumo="reprovado")
    assert a.veredito == "NOK"
