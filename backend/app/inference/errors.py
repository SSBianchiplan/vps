"""Erros de inferência compartilhados."""
from __future__ import annotations


class InferenceError(Exception):
    """Erro genérico de inferência (código + mensagem para a UI)."""

    code = "inference_error"

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code


class VLMUnavailableError(InferenceError):
    code = "vlm_unavailable"


class VLMRefusalError(InferenceError):
    code = "vlm_refusal"


class EdgeUnavailableError(InferenceError):
    code = "edge_unavailable"
