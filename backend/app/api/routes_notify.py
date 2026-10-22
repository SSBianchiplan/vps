"""Configuração e teste de notificações (WhatsApp Cloud API)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from ..notify import whatsapp

router = APIRouter(prefix="/notify", tags=["notify"])


class WhatsAppConfigIn(BaseModel):
    token: str | None = None              # secreto — só backend; nunca retornado
    phone_number_id: str | None = None
    recipients: list[str] | None = None   # números E.164 (ex.: 5547999998888)
    enabled: bool | None = None
    graph_version: str | None = None      # ex.: v22.0
    template_name: str | None = None      # ex.: hello_world (notificação fora da janela 24h)
    template_lang: str | None = None      # ex.: en_US / pt_BR
    template_param: bool | None = None    # template tem variável de corpo {{1}}


class LinkIn(BaseModel):
    to: str                                # número internacional (ex.: 5548996623955)
    message: str = ""


class TestIn(BaseModel):
    to: list[str] | None = None
    message: str = "VisionDesk: teste de notificação."
    # Por padrão testa via TEMPLATE (entrega fora da janela de 24h, como notificações reais).
    use_template: bool = True
    template_name: str | None = None      # sobrepõe o configurado (ex.: hello_world)


@router.post("/whatsapp/link")
def whatsapp_link(body: LinkIn) -> dict[str, Any]:
    """Gera o link wa.me (Clique para conversar) — envio SEM token/API."""
    return {"url": whatsapp.clicktochat_link(body.to, body.message), "token_required": False}


@router.get("/whatsapp/config")
def get_config() -> dict[str, Any]:
    return whatsapp.public_config()


@router.put("/whatsapp/config")
def put_config(body: WhatsAppConfigIn) -> dict[str, Any]:
    whatsapp.save_config(body.model_dump(exclude_none=True))
    return whatsapp.public_config()


@router.post("/whatsapp/test")
async def test(body: TestIn) -> dict[str, Any]:
    cfg = whatsapp.load_config()
    if body.use_template:
        name = body.template_name or cfg.get("template_name") or "hello_world"
        lang = cfg.get("template_lang", "en_US") if name != "hello_world" else "en_US"
        params = [body.message] if (name == cfg.get("template_name") and cfg.get("template_param")) else None
        return await whatsapp.send_template(name, lang, params, to=body.to)
    return await whatsapp.send_text(body.message, to=body.to)
