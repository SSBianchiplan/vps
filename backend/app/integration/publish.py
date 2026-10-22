"""Publicação de eventos de visão p/ MES/SCADA (#7) — MQTT + OPC UA, opcionais.

Degrada para no-op quando broker/lib ausentes (princípio do projeto). Payload
segue o contrato §5.2 (assíncrono, dado rico). A decisão binária determinística
ao PLC (fieldbus) é responsabilidade de outra camada (não aqui).
"""
from __future__ import annotations

from typing import Any

from ..config import get_settings
from ..logging_conf import get_logger
from ..schemas.results import InferenceResult

log = get_logger("visiondesk.integration")
_mqtt_client: Any | None = None
_mqtt_tried = False
_opcua_warned = False


def _event_payload(r: InferenceResult) -> dict[str, Any]:
    res = r.result or {}
    return {
        "Inspection_ID": r.detection_id,
        "Timestamp": r.timestamp,
        "Station_ID": r.source_id,
        "Mode": r.mode.value,
        "Model_Name": r.model_name,
        "Model_Version": r.model_version,
        "Confidence": r.confidence,
        "Latency_ms": r.latency_ms,
        "Counts": res.get("contagens"),
        "Veredito": res.get("veredito"),
    }


def _mqtt() -> Any | None:
    """Cliente MQTT conectado (lazy, cacheado) ou None se indisponível."""
    global _mqtt_client, _mqtt_tried
    s = get_settings()
    if not s.mqtt_url:
        return None
    if _mqtt_client is not None:
        return _mqtt_client
    if _mqtt_tried:
        return None
    _mqtt_tried = True
    try:
        import paho.mqtt.client as mqtt  # type: ignore
        from urllib.parse import urlparse
        u = urlparse(s.mqtt_url)
        c = mqtt.Client()
        c.connect(u.hostname or "localhost", u.port or 1883, keepalive=30)
        c.loop_start()
        _mqtt_client = c
        log.info("MQTT conectado em %s", s.mqtt_url)
        return c
    except Exception as exc:  # noqa: BLE001
        log.warning("MQTT indisponível (%s) — eventos não publicados.", exc)
        return None


def publish_event(r: InferenceResult) -> None:
    """Publica o evento nos canais configurados. Nunca levanta (best-effort)."""
    s = get_settings()
    if not (s.mqtt_url or s.opcua_url):
        return
    payload = _event_payload(r)
    try:
        c = _mqtt()
        if c is not None:
            import json
            c.publish(s.mqtt_topic, json.dumps(payload, ensure_ascii=False), qos=0)
    except Exception:  # noqa: BLE001
        pass
    if s.opcua_url:
        global _opcua_warned
        if not _opcua_warned:
            _opcua_warned = True
            log.info("OPC UA configurado (%s): bridge via MQTT recomendada; gravação direta = roadmap.", s.opcua_url)
