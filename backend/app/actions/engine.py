"""Action Engine (M5 — AGIR / Vision-Language-Action).

Avalia regras no-code contra um resultado de inferência e executa ações
(webhook, Slack, log, alerta visual, clipboard, snapshot). MQTT/email/push
degradam honestamente ("não configurado") até a Fase 5.
"""
from __future__ import annotations

import csv
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from ..config import get_settings
from ..db.repository import repository
from ..schemas.results import InferenceResult

_TEMPLATE = re.compile(r"\{([a-zA-Z0-9_.]+)\}")
NETWORK_ACTIONS = {"webhook_post", "webhook_slack"}
LOCAL_ALERTS = {"alert_visual", "clipboard"}
UNSUPPORTED = {"mqtt_publish": "MQTT", "email": "SMTP/email", "alert_push": "push PWA"}


def _unsafe_target(url: str) -> str | None:
    """Guard SSRF leve. Bloqueia esquema não-http(s) e o IP de metadados de nuvem.
    RFC1918 (LAN) é PERMITIDO de propósito — uso on-prem mira ERP/serviços locais.
    """
    try:
        p = urlparse(url)
    except Exception:  # noqa: BLE001
        return "URL inválida"
    if p.scheme not in ("http", "https"):
        return f"esquema não permitido: {p.scheme or '?'} (use http/https)"
    host = (p.hostname or "").lower()
    if host in ("169.254.169.254", "metadata.google.internal") or host.startswith("169.254."):
        return "destino bloqueado (metadados de nuvem / link-local)"
    return None


def _accessor(result: InferenceResult) -> dict[str, Any]:
    """Achata o resultado num dict de acesso por campo (top-level + leituras por campo)."""
    flat: dict[str, Any] = {"confidence": result.confidence, "mode": result.mode.value}
    r = result.result or {}
    for k, v in r.items():
        if not isinstance(v, (list, dict)):
            flat[k] = v
    flat["total"] = r.get("total", flat.get("total"))
    flat["veredito"] = r.get("veredito")
    for leitura in r.get("leituras", []) or []:
        if leitura.get("campo"):
            flat[leitura["campo"]] = leitura.get("texto")
    for classe, qtd in (r.get("contagens") or {}).items():
        flat[f"contagens.{classe}"] = qtd
    return flat


def evaluate(condition: dict[str, Any], result: InferenceResult) -> tuple[bool, Any]:
    """Retorna (match, valor_do_campo). Condição: {field, op, value, min_confidence}."""
    flat = _accessor(result)
    field = condition.get("field", "veredito")
    op = condition.get("op", "present")
    expected = condition.get("value")
    min_conf = condition.get("min_confidence")
    if min_conf is not None and (result.confidence or 0) < float(min_conf):
        return False, None
    val = flat.get(field)
    if op == "present":
        return val not in (None, "", []), val
    if op == "absent":
        return val in (None, "", []), val
    if val is None:
        return False, None
    try:
        if op == "==":
            return str(val) == str(expected), val
        if op == "!=":
            return str(val) != str(expected), val
        if op == "contains":
            return str(expected).lower() in str(val).lower(), val
        if op in (">", "<", ">=", "<="):
            a, b = float(val), float(expected)
            return {">": a > b, "<": a < b, ">=": a >= b, "<=": a <= b}[op], val
    except (ValueError, TypeError):
        return False, val
    return False, val


def _render(template: Any, flat: dict[str, Any], value: Any, ts: str) -> Any:
    if isinstance(template, dict):
        return {k: _render(v, flat, value, ts) for k, v in template.items()}
    if isinstance(template, list):
        return [_render(v, flat, value, ts) for v in template]
    if not isinstance(template, str):
        return template

    def sub(m: re.Match) -> str:
        key = m.group(1)
        if key == "timestamp":
            return ts
        if key == "value":
            return str(value)
        if key.startswith("result."):
            return str(flat.get(key[len("result."):], ""))
        return str(flat.get(key, ""))

    return _TEMPLATE.sub(sub, template)


async def _execute(action: dict[str, Any], flat: dict[str, Any], value: Any, ts: str) -> dict[str, Any]:
    """Executa uma ação. Retorna {status, http_status, error, payload, message}."""
    atype = action.get("type", "")
    target = _render(action.get("target", ""), flat, value, ts)
    message = _render(action.get("message", ""), flat, value, ts)
    payload = _render(action.get("payload_template") or {"value": value, "timestamp": ts}, flat, value, ts)

    if atype in LOCAL_ALERTS:
        return {"status": "success", "http_status": None, "error": None,
                "payload": payload, "message": message, "target": None}

    if atype in NETWORK_ACTIONS:
        if not target:
            return {"status": "error", "http_status": None, "error": "target ausente", "payload": payload, "target": target}
        blocked = _unsafe_target(target)
        if blocked:
            return {"status": "error", "http_status": None, "error": blocked, "payload": payload, "target": target}
        body = {"text": message or str(payload)} if atype == "webhook_slack" else payload
        last_err, last_code = None, None
        for attempt in range(2):  # tentativa + 1 retry em falha transitória (rede/5xx/429)
            try:
                async with httpx.AsyncClient(timeout=4.0) as client:
                    resp = await client.post(target, json=body)
                if 200 <= resp.status_code < 300:
                    return {"status": "success", "http_status": resp.status_code, "error": None,
                            "payload": body, "message": message, "target": target}
                last_code = resp.status_code
                last_err = f"HTTP {resp.status_code}"
                if not (resp.status_code >= 500 or resp.status_code == 429):
                    break  # 4xx não-transitório: não retenta
            except Exception as exc:  # noqa: BLE001
                last_err = str(exc)
        return {"status": "error", "http_status": last_code, "error": last_err, "payload": body, "target": target}

    if atype == "log_external":
        try:
            path = Path(target) if target else (get_settings().frames_path().parent / "actions_log.csv")
            path.parent.mkdir(parents=True, exist_ok=True)
            new = not path.exists()
            with path.open("a", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                if new:
                    w.writerow(["timestamp", "value", "message", "payload"])
                w.writerow([ts, value, message, payload])
            return {"status": "success", "http_status": None, "error": None, "payload": payload, "target": str(path)}
        except Exception as exc:  # noqa: BLE001
            return {"status": "error", "http_status": None, "error": str(exc), "payload": payload, "target": target}

    if atype == "whatsapp":
        from ..notify import whatsapp
        to = [t.strip() for t in target.split(",") if t.strip()] if target else None
        res = await whatsapp.notify(message or str(payload), to=to)
        return {"status": "success" if res.get("ok") else "error", "http_status": None,
                "error": None if res.get("ok") else str(res.get("error")), "payload": {"body": message},
                "message": message, "target": ",".join(to) if to else "destinatários configurados"}

    if atype == "snapshot":
        return {"status": "success", "http_status": None, "error": None, "payload": payload,
                "message": message or "snapshot marcado", "target": target}

    if atype in UNSUPPORTED:
        return {"status": "error", "http_status": None, "error": f"{UNSUPPORTED[atype]} não configurado (Fase 5)",
                "payload": payload, "target": target}

    return {"status": "error", "http_status": None, "error": f"tipo desconhecido: {atype}", "payload": payload, "target": target}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def run_rules(task_id: str | None, result: InferenceResult) -> list[dict[str, Any]]:
    """Avalia regras ativas da task; executa ações; grava FACT_ACTION; retorna alertas p/ o WS."""
    if not task_id:
        return []
    import asyncio
    rules = await asyncio.to_thread(repository.list_rules, task_id, True)
    rules += await asyncio.to_thread(repository.list_rules, "*", True)  # regras globais
    if not rules:
        return []
    flat = _accessor(result)
    ts = _now()
    alerts: list[dict[str, Any]] = []
    for rule in rules:
        match, value = evaluate(rule.get("condition", {}), result)
        if not match:
            continue
        for action in rule.get("actions", []):
            res = await _execute(action, flat, value, ts)
            await asyncio.to_thread(
                repository.record_action, rule["rule_id"], result.detection_id, task_id,
                action.get("type", ""), res.get("target"), res.get("payload"),
                res["status"], res.get("http_status"), res.get("error"), 0,
            )
            if action.get("type") in LOCAL_ALERTS and res["status"] == "success":
                alerts.append({
                    "action_type": action["type"],
                    "message": res.get("message") or "",
                    "payload": res.get("payload"),
                    "rule": rule.get("label") or rule["rule_id"],
                })
    return alerts


async def retry_action(action_id: str) -> dict[str, Any] | None:
    """Reexecuta uma ação registrada (mesmo target/payload)."""
    import asyncio
    import json
    act = await asyncio.to_thread(repository.get_action, action_id)
    if not act:
        return None
    payload = json.loads(act["payload_json"]) if act.get("payload_json") else None
    fake = {"type": act["action_type"], "target": act.get("target"),
            "payload_template": payload, "message": ""}
    res = await _execute(fake, {}, None, _now())
    await asyncio.to_thread(
        repository.update_action, action_id, res["status"], res.get("http_status"),
        res.get("error"), int(act.get("retry_count", 0)) + 1,
    )
    return {"status": res["status"], "error": res.get("error"), "http_status": res.get("http_status")}
