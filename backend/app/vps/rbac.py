"""RBAC por bounded context (SPEC_VPS §15).

Cada Fio tem um dono (owner) derivado do entity_type. Ações de governança exigem o
papel dono OU Admin; Viewer é só leitura. Sem sistema de auth: o cliente envia
`X-VPS-Role` (dev aberto via vps_default_role). Demonstra o controle, não substitui IdP.
"""
from __future__ import annotations

from fastapi import Header, HTTPException

from ..config import get_settings
from . import store

ROLES = ["Admin", "Operations", "Supply", "Finance", "Engineering", "Projects", "Sales", "Quality", "Viewer"]

# entity_type → bounded context dono
ENTITY_OWNER = {
    "OP": "Operations", "PICK": "Supply", "ITEM": "Supply", "STOCK": "Supply",
    "SO": "Sales", "PROJ": "Projects", "SHIP": "Operations", "INV": "Finance",
    "MEAS": "Quality", "OCC": "Quality",
}


def owner_of_tag(tag_id: str) -> str:
    tag = store.get_tag(tag_id)
    et = (tag or {}).get("entity_type", "OP")
    return ENTITY_OWNER.get(et, "Operations")


def default_role() -> str:
    return get_settings().vps_default_role


def current_role(x_vps_role: str | None = Header(default=None)) -> str:
    """Dependency FastAPI: papel atual (header X-VPS-Role) ou default da config."""
    return x_vps_role or default_role()


def can(role: str, owner: str) -> bool:
    if role == "Admin":
        return True
    if role == "Viewer":
        return False
    return role == owner


def require(role: str, tag_id: str) -> None:
    """Levanta 403 se o papel não pode governar o Fio (pelo dono do contexto)."""
    owner = owner_of_tag(tag_id)
    if not can(role, owner):
        raise HTTPException(status_code=403, detail={
            "code": "rbac_denied",
            "message": f"Papel '{role}' não pode agir neste Fio (dono: {owner}). Use {owner} ou Admin.",
            "owner": owner,
        })
