"""Persistência: a fonte é garantida defensivamente (sem IntegrityError de FK)."""
from __future__ import annotations

from app.db.database import init_db
from app.db.repository import repository
from app.schemas.enums import Mode, ModelType
from app.schemas.results import InferenceResult


def _result(source_id: str | None) -> InferenceResult:
    return InferenceResult(
        detection_id=f"det_test_{source_id}",
        task_id=None,
        source_id=source_id,
        mode=Mode.DESCREVER,
        model_name="claude-opus-4-8",
        model_type=ModelType.VLM,
        pipeline="vlm",
        timestamp="2026-06-26T12:00:00+00:00",
        latency_ms=10,
        confidence=1.0,
        frame_seq=1,
        result={"descricao": "x", "objetos": [], "alertas": []},
    )


def test_save_inference_ensures_unregistered_source():
    init_db()
    # source_id que NUNCA foi registrado via POST /sources não deve quebrar a FK.
    repository.save_inference(_result("cam-nao-registrada"))
    rows = repository.query_detections(limit=50)
    assert any(r["detection_id"] == "det_test_cam-nao-registrada" for r in rows)
    # a fonte foi criada defensivamente
    assert any(s["source_id"] == "cam-nao-registrada" for s in repository.list_sources())


def test_save_inference_accepts_null_source():
    init_db()
    repository.save_inference(_result(None))
    rows = repository.query_detections(limit=50)
    assert any(r["detection_id"] == "det_test_None" for r in rows)
