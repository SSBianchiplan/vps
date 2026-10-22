"""Login (FaceID/PIN), sessão e controle de acesso (RBAC: admin/operador/view)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from ..auth import auth

router = APIRouter(prefix="/auth", tags=["auth"])


def _require_admin(token: str | None) -> None:
    if auth.bootstrap_needed():
        return  # 1ª configuração: sem admin ainda
    if auth.role_of_token(token) != "admin":
        raise HTTPException(status_code=403, detail={"code": "forbidden", "message": "requer admin"})


class FaceLoginIn(BaseModel):
    image_b64: str


class PinLoginIn(BaseModel):
    operator_id: str
    pin: str


class BootstrapIn(BaseModel):
    name: str
    pin: str


class UserIn(BaseModel):
    name: str
    role: str = "view"
    operator_id: str | None = None
    pin: str | None = None
    face_b64: str | None = None       # cadastro de face opcional no ato


class RoleIn(BaseModel):
    role: str


class ActiveIn(BaseModel):
    active: bool


# ── sessão / login ───────────────────────────────────────────────────
@router.get("/state")
def state() -> dict[str, Any]:
    return {"bootstrap_needed": auth.bootstrap_needed(), "roles": list(auth.ROLES)}


@router.get("/me")
def me(x_auth_token: str | None = Header(default=None)) -> dict[str, Any]:
    s = auth.session(x_auth_token)
    return {"authenticated": bool(s), "user": s}


@router.post("/login/face")
def login_face(body: FaceLoginIn) -> dict[str, Any]:
    return auth.login_face(body.image_b64)


@router.post("/login/pin")
def login_pin(body: PinLoginIn) -> dict[str, Any]:
    return auth.login_pin(body.operator_id, body.pin)


@router.post("/bootstrap")
def bootstrap(body: BootstrapIn) -> dict[str, Any]:
    return auth.bootstrap_admin(body.name, body.pin)


@router.post("/logout")
def logout(x_auth_token: str | None = Header(default=None)) -> dict[str, Any]:
    return auth.logout(x_auth_token)


@router.get("/matrix")
def matrix() -> dict[str, Any]:
    return {"matrix": auth.MATRIX, "roles": list(auth.ROLES)}


# ── usuários (admin) ─────────────────────────────────────────────────
@router.get("/users")
def list_users(x_auth_token: str | None = Header(default=None)) -> dict[str, Any]:
    _require_admin(x_auth_token)
    return {"users": auth.users()}


@router.post("/users")
def create_user(body: UserIn, x_auth_token: str | None = Header(default=None)) -> dict[str, Any]:
    _require_admin(x_auth_token)
    res = auth.upsert_user(body.name, body.role, body.operator_id, body.pin)
    if res.get("ok") and body.face_b64:        # cadastro de face consentido no ato
        from ..biometrics import face
        f = face.enroll(res["operator_id"], body.name, body.face_b64, consent=True)
        res["face"] = f
    return res


@router.post("/users/{operator_id}/role")
def user_role(operator_id: str, body: RoleIn, x_auth_token: str | None = Header(default=None)) -> dict[str, Any]:
    _require_admin(x_auth_token)
    return auth.set_role(operator_id, body.role)


@router.post("/users/{operator_id}/active")
def user_active(operator_id: str, body: ActiveIn, x_auth_token: str | None = Header(default=None)) -> dict[str, Any]:
    _require_admin(x_auth_token)
    return auth.set_active(operator_id, body.active)


@router.post("/users/{operator_id}/face")
def user_face(operator_id: str, body: FaceLoginIn, x_auth_token: str | None = Header(default=None)) -> dict[str, Any]:
    _require_admin(x_auth_token)
    from ..biometrics import face
    u = next((u for u in auth.users() if u["operator_id"] == operator_id), None)
    return face.enroll(operator_id, (u or {}).get("name") or operator_id, body.image_b64, consent=True)


@router.delete("/users/{operator_id}")
def remove_user(operator_id: str, x_auth_token: str | None = Header(default=None)) -> dict[str, Any]:
    _require_admin(x_auth_token)
    return auth.delete_user(operator_id)
