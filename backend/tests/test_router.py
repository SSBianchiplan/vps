"""Roteamento do orquestrador (função pura `route`)."""
from __future__ import annotations

import pytest

from app.orchestrator.router import route
from app.schemas.enums import Mode, PipelineKind
from app.schemas.tasks import TaskConfig


def _task(mode: str, **params) -> TaskConfig:
    return TaskConfig.model_validate(
        {"mode": mode, "params": {"mode": mode, **params}}
    )


def test_describe_sempre_vlm():
    d = route(_task("DESCREVER"), edge_detect=True, edge_ocr_avail=True, vlm=True)
    assert d.kind == PipelineKind.VLM and d.use_edge is False


def test_analisar_sempre_vlm():
    d = route(_task("ANALISAR"), edge_detect=True, edge_ocr_avail=True, vlm=True)
    assert d.kind == PipelineKind.VLM


def test_contar_prefere_edge_quando_disponivel():
    d = route(_task("CONTAR"), edge_detect=True, edge_ocr_avail=False, vlm=True)
    assert d.use_edge is True and d.kind == PipelineKind.EDGE


def test_contar_cai_no_vlm_sem_edge():
    d = route(_task("CONTAR"), edge_detect=False, edge_ocr_avail=False, vlm=True)
    assert d.use_edge is False and d.kind == PipelineKind.VLM


def test_ler_prefere_edge_ocr():
    d = route(_task("LER"), edge_detect=False, edge_ocr_avail=True, vlm=True)
    assert d.use_edge is True


def test_ler_prefer_vlm_flag_forca_vlm():
    d = route(_task("LER", prefer_vlm=True), edge_detect=False, edge_ocr_avail=True, vlm=True)
    assert d.use_edge is False and d.kind == PipelineKind.VLM


def test_ler_sem_nada_disponivel_aponta_vlm_para_erro_claro():
    d = route(_task("LER"), edge_detect=False, edge_ocr_avail=False, vlm=False)
    assert d.kind == PipelineKind.VLM
