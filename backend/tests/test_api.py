"""Testes de integração da API REST (sem rede; VLM indisponível por padrão)."""
from __future__ import annotations

import base64
import io

from fastapi.testclient import TestClient  # noqa: F401
from tests.authclient import admin_client
from PIL import Image

from app.main import app


def _jpeg_b64() -> str:
    img = Image.new("RGB", (32, 32), (200, 200, 200))
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    return base64.b64encode(buf.getvalue()).decode()


def test_health_and_capabilities():
    with admin_client(app) as client:
        assert client.get("/api/health").json()["status"] == "ok"
        caps = client.get("/api/capabilities").json()
        assert caps["vlm"] is False  # sem ANTHROPIC_API_KEY nos testes
        assert "LER" in caps["modes"]


def test_task_crud_and_export():
    with admin_client(app) as client:
        payload = {
            "mode": "DESCREVER",
            "params": {"mode": "DESCREVER", "foco": "esteira"},
        }
        resp = client.post("/api/tasks", json=payload)
        assert resp.status_code == 200
        task_id = resp.json()["task_id"]

        got = client.get(f"/api/tasks/{task_id}").json()
        assert got["mode"] == "DESCREVER"

        exp = client.get("/api/export", params={"format": "json"})
        assert exp.status_code == 200 and isinstance(exp.json(), list)


def test_infer_degrada_sem_vlm():
    """Sem chave da API, DESCREVER degrada graciosamente para o motor edge
    (YOLO) em vez de falhar — funcionalidade disponível sem token."""
    from app.orchestrator.router import Orchestrator

    with admin_client(app) as client:
        body = {
            "image_b64": _jpeg_b64(),
            "task": {"mode": "DESCREVER", "params": {"mode": "DESCREVER"}},
        }
        resp = client.post("/api/infer", json=body)
        if Orchestrator.capabilities()["edge_detector"]:
            assert resp.status_code == 200
            data = resp.json()
            assert data["pipeline"] == "edge" and data["model_type"] == "edge"
            assert "descricao" in data["result"]
        else:
            assert resp.status_code == 503
            assert resp.json()["detail"]["code"] == "vlm_unavailable"


def test_events_endpoint_shape():
    """Trilha de rastreabilidade unificada: estrutura esperada + filtros."""
    with admin_client(app) as client:
        resp = client.get("/api/events", params={"limit": 5})
        assert resp.status_code == 200
        body = resp.json()
        assert "events" in body and isinstance(body["events"], list)
        for ev in body["events"]:
            assert {"event_id", "timestamp", "category", "action", "severity", "summary"} <= set(ev)
            assert ev["severity"] in ("info", "ok", "nok", "alerta", "warn")
            assert ev["category"] in (
                "INFERENCE", "CAMERA", "DATA", "ACTION", "RECORDING", "VPS", "MONITOR", "SYSTEM")

        # filtros aceitos (categoria/modo-compat)
        assert client.get("/api/events", params={"category": "INFERENCE"}).status_code == 200
        assert client.get("/api/events", params={"mode": "CONTAR"}).status_code == 200

        srcs = client.get("/api/events/sources")
        assert srcs.status_code == 200 and "sources" in srcs.json()

        cats = client.get("/api/events/categories")
        assert cats.status_code == 200 and len(cats.json()["categories"]) == 8


def test_events_summary_aggregates():
    """Agregação SQL rápida para widgets (sem trafegar linhas)."""
    with admin_client(app) as client:
        r = client.get("/api/events/summary")
        assert r.status_code == 200
        body = r.json()
        assert {"total_events", "alerts", "by_day", "by_category", "by_severity"} <= set(body)
        assert isinstance(body["by_day"], list)


def test_monitor_overview_validation():
    """Rota de monitoramento registrada e valida o período (sem sondar a rede)."""
    with admin_client(app) as client:
        # período inválido é rejeitado antes do handler (sem probe de rede)
        assert client.get("/api/monitor/overview", params={"period": "xx"}).status_code == 422


def test_agir_rules_crud_and_eval():
    """AGIR (M5): catálogo, CRUD de regras e avaliação de condição."""
    from app.actions import engine
    from app.schemas.enums import Mode, ModelType
    from app.schemas.results import InferenceResult
    with admin_client(app) as client:
        cat = client.get("/api/actions/catalog").json()
        assert "alert_visual" in cat["action_types"] and "==" in cat["ops"]
        r = client.post("/api/tasks/TX/rules", json={
            "label": "NOK→alerta",
            "condition": {"field": "veredito", "op": "==", "value": "NOK"},
            "actions": [{"type": "alert_visual", "message": "{value}"}],
        })
        assert r.status_code == 200
        rid = r.json()["rule_id"]
        assert any(x["rule_id"] == rid for x in client.get("/api/tasks/TX/rules").json())

        res = InferenceResult(
            detection_id="d1", task_id="TX", mode=Mode.ANALISAR, model_name="m",
            model_type=ModelType.VLM, pipeline="vlm", timestamp="2026-01-01T00:00:00Z",
            latency_ms=1, confidence=0.9, result={"veredito": "NOK"},
        )
        match, val = engine.evaluate({"field": "veredito", "op": "==", "value": "NOK"}, res)
        assert match and val == "NOK"
        match2, _ = engine.evaluate({"field": "veredito", "op": "==", "value": "OK"}, res)
        assert not match2

        assert client.delete(f"/api/rules/{rid}").json()["deleted"] is True


def test_detectar_and_notify():
    """DETECTAR exposto/roteado e config WhatsApp degrada honestamente."""
    with admin_client(app) as client:
        caps = client.get("/api/capabilities").json()
        assert "DETECTAR" in caps["modes"]
        # sem VLM nem edge nos testes → DETECTAR via /infer falha com 503 claro
        import base64, io
        from PIL import Image
        buf = io.BytesIO(); Image.new("RGB", (16, 16)).save(buf, "JPEG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        r = client.post("/api/infer", json={"image_b64": b64, "task": {"mode": "DETECTAR", "params": {"mode": "DETECTAR"}}})
        assert r.status_code in (200, 503)  # 503 sem backends; 200 se YOLO instalado
        # WhatsApp não configurado por padrão
        wa = client.get("/api/notify/whatsapp/config").json()
        assert wa["configured"] is False and wa["has_token"] is False
        assert "whatsapp" in client.get("/api/actions/catalog").json()["action_types"]
