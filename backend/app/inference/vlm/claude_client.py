"""Cliente VLM baseado na API Anthropic (Claude vision).

Envia o frame (base64) + prompt e recebe JSON estruturado validado por schema
(output_config.format). Cobre DESCREVER, ANALISAR, LER e CONTAR (fallback).

Modelo padrão: claude-opus-4-8. Para ANALISAR usamos adaptive thinking
(julgamento), os demais modos rodam sem thinking para minimizar latência.
"""
from __future__ import annotations

import json
from typing import Any

from ...config import get_settings
from ...schemas.tasks import AnalyzeParams, CountParams, DescribeParams, ReadParams
from ..errors import VLMRefusalError, VLMUnavailableError
from . import prompts

try:  # SDK Anthropic faz parte do core; import defensivo mesmo assim.
    from anthropic import AsyncAnthropic
    import anthropic as _anthropic
    _SDK_OK = True
except Exception:  # pragma: no cover
    AsyncAnthropic = None  # type: ignore[assignment]
    _anthropic = None  # type: ignore[assignment]
    _SDK_OK = False


class ClaudeVLM:
    """Wrapper assíncrono do Claude para inferência multimodal estruturada."""

    def __init__(self) -> None:
        self._client: Any | None = None

    # ── ciclo de vida ───────────────────────────────────────────
    @property
    def model(self) -> str:
        return get_settings().claude_model

    def available(self) -> bool:
        return _SDK_OK and get_settings().vlm_enabled

    def _ensure_client(self) -> Any:
        if not _SDK_OK:
            raise VLMUnavailableError("SDK 'anthropic' não instalado.")
        settings = get_settings()
        if not settings.anthropic_api_key:
            raise VLMUnavailableError(
                "ANTHROPIC_API_KEY ausente. Configure a chave para usar o VLM."
            )
        if self._client is None:
            self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        return self._client

    # ── chamada genérica ────────────────────────────────────────
    async def _call_json(
        self,
        *,
        image_bytes: bytes,
        media_type: str,
        prompt: str,
        schema: dict[str, Any],
        thinking: bool = False,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        from ...utils.images import bytes_to_b64  # import tardio evita ciclo

        client = self._ensure_client()
        settings = get_settings()
        kwargs: dict[str, Any] = {
            "model": settings.claude_model,
            "max_tokens": max_tokens or settings.vlm_max_tokens,
            "output_config": {"format": {"type": "json_schema", "schema": schema}},
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": bytes_to_b64(image_bytes),
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        }
        if thinking:
            kwargs["thinking"] = {"type": "adaptive"}

        try:
            resp = await client.messages.create(**kwargs)
        except Exception as exc:  # erros de API/rede do SDK
            if _anthropic is not None and isinstance(exc, _anthropic.AuthenticationError):
                raise VLMUnavailableError("Chave da API inválida (401).") from exc
            raise VLMUnavailableError(f"Falha na chamada ao VLM: {exc}") from exc

        if getattr(resp, "stop_reason", None) == "refusal":
            details = getattr(resp, "stop_details", None)
            cat = getattr(details, "category", None) if details else None
            raise VLMRefusalError(f"Conteúdo recusado pelo modelo (categoria={cat}).")

        text = next((b.text for b in resp.content if getattr(b, "type", None) == "text"), None)
        if not text:
            raise VLMRefusalError("Resposta do VLM sem bloco de texto JSON.")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:  # extremamente raro com structured outputs
            raise VLMRefusalError(f"JSON inválido do VLM: {exc}") from exc

    # ── métodos por modo ────────────────────────────────────────
    async def describe(
        self, image_bytes: bytes, media_type: str, params: DescribeParams, prompt: str | None
    ) -> dict[str, Any]:
        return await self._call_json(
            image_bytes=image_bytes,
            media_type=media_type,
            prompt=prompts.describe_prompt(params, prompt),
            schema=prompts.DESCRIBE_SCHEMA,
        )

    async def analyze(
        self, image_bytes: bytes, media_type: str, params: AnalyzeParams, prompt: str | None
    ) -> dict[str, Any]:
        return await self._call_json(
            image_bytes=image_bytes,
            media_type=media_type,
            prompt=prompts.analyze_prompt(params, prompt),
            schema=prompts.ANALYZE_SCHEMA,
            thinking=True,
            max_tokens=max(get_settings().vlm_max_tokens, 8000),
        )

    async def read(
        self, image_bytes: bytes, media_type: str, params: ReadParams, prompt: str | None
    ) -> dict[str, Any]:
        return await self._call_json(
            image_bytes=image_bytes,
            media_type=media_type,
            prompt=prompts.read_prompt(params, prompt),
            schema=prompts.READ_SCHEMA,
        )

    async def count(
        self, image_bytes: bytes, media_type: str, params: CountParams, prompt: str | None
    ) -> dict[str, Any]:
        return await self._call_json(
            image_bytes=image_bytes,
            media_type=media_type,
            prompt=prompts.count_prompt(params, prompt),
            schema=prompts.COUNT_SCHEMA,
        )

    async def detect(
        self, image_bytes: bytes, media_type: str, classes_alvo: list[str], prompt: str | None
    ) -> dict[str, Any]:
        return await self._call_json(
            image_bytes=image_bytes,
            media_type=media_type,
            prompt=prompts.detect_prompt(classes_alvo, prompt),
            schema=prompts.DETECT_SCHEMA,
        )


claude_vlm = ClaudeVLM()
