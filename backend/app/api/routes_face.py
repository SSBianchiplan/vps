"""Reconhecimento facial / biometria de operador (consentida · edge · LGPD).

Enrolamento (com consentimento), identificação 1:N, verificação 1:1 (login),
galeria autorizada, revogação (apaga template) e KPIs. Guarda template, não foto.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from ..auth import auth
from ..biometrics import face

router = APIRouter(prefix="/face", tags=["face"])


def _pode_mexer_na_face(token: str | None, operator_id: str) -> None:
    """Cadastrar/revogar a face de alguém = criar/remover uma credencial dele.

    Antes era aberto: qualquer anônimo cadastrava o próprio rosto no
    operator_id de um admin e entrava como admin pelo login facial. Agora:
    admin mexe em qualquer um; operador só em quem NÃO tem acesso de admin.
    (A sessão já foi exigida pelo portão global; aqui é a regra do alvo.)
    """
    s = auth.session(token)
    if not s:
        raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": "faça login"})
    if s.get("role") == "admin":
        return
    alvo = next((u for u in auth.users() if u["operator_id"] == operator_id), None)
    if s.get("role") != "operador" or (alvo and alvo.get("role") == "admin"):
        raise HTTPException(status_code=403, detail={"code": "forbidden",
                            "message": "só um admin cadastra ou revoga a face deste usuário"})


class EnrollIn(BaseModel):
    operator_id: str
    name: str
    image_b64: str
    consent: bool = False
    consent_ref: str | None = None


class IdentifyIn(BaseModel):
    image_b64: str


class VerifyIn(BaseModel):
    operator_id: str
    image_b64: str


@router.get("/status")
def status() -> dict[str, Any]:
    return {"available": face.available(), **face.kpis()}


@router.get("/gallery")
def gallery() -> dict[str, Any]:
    return {"operators": face.gallery()}


@router.post("/enroll")
def enroll(body: EnrollIn, x_auth_token: str | None = Header(default=None)) -> dict[str, Any]:
    _pode_mexer_na_face(x_auth_token, body.operator_id)
    return face.enroll(body.operator_id, body.name, body.image_b64, body.consent, body.consent_ref)


@router.post("/identify")
def identify(body: IdentifyIn) -> dict[str, Any]:
    return face.identify(body.image_b64)


@router.post("/verify")
def verify(body: VerifyIn) -> dict[str, Any]:
    return face.verify(body.operator_id, body.image_b64)


@router.delete("/template/{operator_id}")
def revoke(operator_id: str, x_auth_token: str | None = Header(default=None)) -> dict[str, Any]:
    _pode_mexer_na_face(x_auth_token, operator_id)
    return face.revoke(operator_id)


@router.get("/kpis")
def kpis() -> dict[str, Any]:
    return face.kpis()
