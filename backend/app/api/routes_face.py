"""Reconhecimento facial / biometria de operador (consentida · edge · LGPD).

Enrolamento (com consentimento), identificação 1:N, verificação 1:1 (login),
galeria autorizada, revogação (apaga template) e KPIs. Guarda template, não foto.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from ..biometrics import face

router = APIRouter(prefix="/face", tags=["face"])


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
def enroll(body: EnrollIn) -> dict[str, Any]:
    return face.enroll(body.operator_id, body.name, body.image_b64, body.consent, body.consent_ref)


@router.post("/identify")
def identify(body: IdentifyIn) -> dict[str, Any]:
    return face.identify(body.image_b64)


@router.post("/verify")
def verify(body: VerifyIn) -> dict[str, Any]:
    return face.verify(body.operator_id, body.image_b64)


@router.delete("/template/{operator_id}")
def revoke(operator_id: str) -> dict[str, Any]:
    return face.revoke(operator_id)


@router.get("/kpis")
def kpis() -> dict[str, Any]:
    return face.kpis()
