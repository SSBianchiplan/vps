"""Integração WhatsApp Cloud API (Meta Graph) para notificações.

Config persistida em data/whatsapp.json (gitignored) — o token NUNCA é exposto
ao frontend (mascarado em public_config).

IMPORTANTE (janela de 24h): mensagens iniciadas pela empresa FORA da janela de
24h desde a última resposta do usuário SÓ são entregues como **template aprovado**
(ex.: hello_world). Texto livre só funciona dentro da janela de 24h. Por isso, se
um `template_name` estiver configurado, as notificações usam template; senão caem
para texto (entregue apenas na janela de 24h).
"""
from __future__ import annotations

import io
import json
import time
from pathlib import Path
from typing import Any

import httpx

from ..config import get_settings

_DEFAULT_VERSION = "v22.0"

# Throttle anti-flood: no máx. 1 envio por conjunto de destinatários a cada N s.
_SEND_MIN_INTERVAL = 8.0
_last_send: dict[str, float] = {}


def clicktochat_link(phone: str, text: str = "") -> str:
    """Link 'Clique para conversar' (wa.me) — abre o WhatsApp com a mensagem
    pré-preenchida, SEM token/API e sem salvar o contato (Meta FAQ 425247423114725).
    O envio final é confirmado pelo usuário no app. `phone` em formato
    internacional só com dígitos (ex.: 5548996623955)."""
    from urllib.parse import quote

    digits = "".join(ch for ch in phone if ch.isdigit())
    base = f"https://wa.me/{digits}"
    return f"{base}?text={quote(text)}" if text else base


def _file() -> Path:
    return Path(get_settings().db_path).parent / "whatsapp.json"


def load_config() -> dict[str, Any]:
    f = _file()
    if f.exists():
        try:
            return json.loads(f.read_text())
        except Exception:  # noqa: BLE001
            return {}
    return {}


def save_config(partial: dict[str, Any]) -> dict[str, Any]:
    cfg = load_config()
    cfg.update({k: v for k, v in partial.items() if v is not None})
    f = _file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))
    return cfg


def configured() -> bool:
    c = load_config()
    return bool(
        c.get("enabled", True) and c.get("token") and c.get("phone_number_id") and c.get("recipients")
    )


def public_config() -> dict[str, Any]:
    c = load_config()
    return {
        "enabled": bool(c.get("enabled", True)),
        "phone_number_id": c.get("phone_number_id"),
        "recipients": c.get("recipients", []),
        "graph_version": c.get("graph_version", _DEFAULT_VERSION),
        "template_name": c.get("template_name", ""),
        "template_lang": c.get("template_lang", "en_US"),
        "template_param": bool(c.get("template_param", False)),
        "has_token": bool(c.get("token")),
        "configured": configured(),
    }


def _recipients() -> list[str]:
    return load_config().get("recipients", []) or []


def _base(c: dict[str, Any]) -> str:
    return f"https://graph.facebook.com/{c.get('graph_version', _DEFAULT_VERSION)}/{c['phone_number_id']}"


def _precheck(c: dict[str, Any], to: list[str] | None) -> tuple[list[str] | None, dict[str, Any] | None]:
    if not c.get("enabled", True):
        return None, {"ok": False, "error": "WhatsApp desativado"}
    if not (c.get("token") and c.get("phone_number_id")):
        return None, {"ok": False, "error": "WhatsApp não configurado (token/phone_number_id)"}
    targets = to or _recipients()
    if not targets:
        return None, {"ok": False, "error": "sem destinatários configurados"}
    key = "|".join(sorted(targets))
    now = time.monotonic()
    if now - _last_send.get(key, 0.0) < _SEND_MIN_INTERVAL:
        return None, {"ok": True, "skipped": True, "reason": "throttle"}
    _last_send[key] = now
    return targets, None


async def _post_messages(c: dict[str, Any], targets: list[str], make_payload) -> dict[str, Any]:
    url = f"{_base(c)}/messages"
    headers = {"Authorization": f"Bearer {c['token']}"}
    results, ok_any = [], False
    async with httpx.AsyncClient(timeout=8.0) as client:
        for dest in targets:
            try:
                r = await client.post(url, headers=headers, json=make_payload(dest))
                ok = 200 <= r.status_code < 300
                ok_any = ok_any or ok
                results.append({"to": dest, "status": r.status_code, "ok": ok,
                                "error": None if ok else r.text[:300]})
            except Exception as exc:  # noqa: BLE001
                results.append({"to": dest, "ok": False, "error": str(exc)})
    return {"ok": ok_any, "results": results}


async def send_text(body: str, to: list[str] | None = None) -> dict[str, Any]:
    """Texto livre — entregue apenas dentro da janela de 24h."""
    c = load_config()
    targets, blocked = _precheck(c, to)
    if blocked:
        return blocked
    assert targets is not None
    return await _post_messages(
        c, targets,
        lambda dest: {"messaging_product": "whatsapp", "to": dest, "type": "text", "text": {"body": body[:4000]}},
    )


async def send_template(
    name: str, lang: str = "en_US", body_params: list[str] | None = None, to: list[str] | None = None
) -> dict[str, Any]:
    """Template aprovado — único caminho válido p/ mensagem iniciada pela empresa fora das 24h."""
    c = load_config()
    targets, blocked = _precheck(c, to)
    if blocked:
        return blocked
    assert targets is not None
    template: dict[str, Any] = {"name": name, "language": {"code": lang}}
    if body_params:
        template["components"] = [
            {"type": "body", "parameters": [{"type": "text", "text": p[:1000]} for p in body_params]}
        ]
    return await _post_messages(
        c, targets,
        lambda dest: {"messaging_product": "whatsapp", "to": dest, "type": "template", "template": template},
    )


async def notify(text: str, to: list[str] | None = None) -> dict[str, Any]:
    """Escolhe template (se configurado) ou texto. Use para notificações reais."""
    c = load_config()
    name = c.get("template_name")
    if name:
        params = [text] if c.get("template_param") else None
        return await send_template(name, c.get("template_lang", "en_US"), params, to)
    return await send_text(text, to)


async def send_image(image_bytes: bytes, caption: str, to: list[str] | None = None) -> dict[str, Any]:
    """Upload de mídia + envio de imagem (dentro da janela de 24h). Cai p/ notify()."""
    c = load_config()
    targets, blocked = _precheck(c, to)
    if blocked:
        return blocked
    assert targets is not None
    headers = {"Authorization": f"Bearer {c['token']}"}
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            up = await client.post(
                f"{_base(c)}/media", headers=headers,
                data={"messaging_product": "whatsapp", "type": "image/jpeg"},
                files={"file": ("frame.jpg", io.BytesIO(image_bytes), "image/jpeg")},
            )
            up.raise_for_status()
            media_id = up.json().get("id")
            if not media_id:
                return await notify(caption, targets)
            return await _post_messages(
                c, targets,
                lambda dest: {"messaging_product": "whatsapp", "to": dest, "type": "image",
                              "image": {"id": media_id, "caption": caption[:1000]}},
            )
    except Exception:  # noqa: BLE001
        return await notify(caption, targets)
