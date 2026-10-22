"""RBAC por bounded context (SPEC_VPS §15) — agora derivado da SESSÃO.

O QUE MUDOU E POR QUÊ

Antes o papel vinha de um cabeçalho `X-VPS-Role` que o PRÓPRIO cliente
escolhia, com default "Admin". Funcionava como demonstração, mas num endereço
público qualquer um mandava `X-VPS-Role: Admin` e governava o Fio inteiro. O
controle era cosmético.

Agora o papel sai do token de sessão (`X-Auth-Token`, o mesmo do login):

  papel de acesso  →  papel VPS
  admin            →  Admin      (tudo)
  view             →  Viewer     (só leitura)
  operador         →  o PERFIL OPERACIONAL do usuário (Operations, Supply,
                      Quality, Projects), ou Operations se não tiver perfil

O cabeçalho só vale em modo de desenvolvimento aberto (VISIONDESK_DEV_LOGIN
ligado) e sem sessão — para não quebrar o fluxo local. Em produção, sem sessão
é Viewer.

PERFIS OPERACIONAIS

Quatro tipos de permissão, um por área que governa o chão de fábrica. Cada um
é dono de certos tipos de entidade do Fio Dourado (ENTITY_OWNER) e de certos
contextos de ação (CONTEXT_ACTIONS). Quem não é dono lê, não governa. Toda
negativa vira evento na trilha (RBAC_DENIED) — rastreabilidade inclui o que o
sistema recusou.
"""
from __future__ import annotations

from typing import Any

from fastapi import Header, HTTPException

from ..config import get_settings
from . import store

# Papéis VPS aceitos (compat com o que já existia + os 4 perfis operacionais).
ROLES = ["Admin", "Operations", "Supply", "Finance", "Engineering", "Projects", "Sales", "Quality", "Viewer"]

# Os 4 perfis operacionais atribuíveis a um usuário com papel "operador".
PERFIS_OPERACIONAIS: dict[str, dict[str, Any]] = {
    "Operations": {
        "label": "Operações (produção)",
        "descricao": "Governa OPs, expedição e o APS: sequencia, publica programação, expedita.",
        "contextos": ["OP", "SHIP", "APS", "STATION", "PCP"],
    },
    "Supply": {
        "label": "Suprimentos (almoxarifado/compras)",
        "descricao": "Governa picking, itens, estoque e lacunas de compra.",
        "contextos": ["PICK", "ITEM", "STOCK", "PO"],
    },
    "Quality": {
        "label": "Qualidade (inspeção)",
        "descricao": "Governa medições, ocorrências, termografia e metrologia.",
        "contextos": ["MEAS", "OCC", "QUALITY"],
    },
    "Projects": {
        "label": "Projetos (planejamento)",
        "descricao": "Governa projetos, WBS, cards, dependências, baseline e cronograma.",
        "contextos": ["PROJ", "PLANNING", "PCP"],
    },
}

# entity_type → bounded context dono
ENTITY_OWNER = {
    "OP": "Operations", "PICK": "Supply", "ITEM": "Supply", "STOCK": "Supply", "PO": "Supply",
    "SO": "Sales", "PROJ": "Projects", "SHIP": "Operations", "INV": "Finance",
    "MEAS": "Quality", "OCC": "Quality",
}

# contexto de ação → perfis que podem executar (Admin sempre pode)
CONTEXT_ACTIONS: dict[str, set[str]] = {
    "PLANNING": {"Projects"},                 # projetos, WBS, cards, deps, baseline, cronograma
    "APS": {"Operations", "Projects"},        # gerar/publicar programação, CTP, expedite
    "STATION": {"Operations", "Supply", "Quality"},   # ações de estação (scan/atuar)
    "QUALITY": {"Quality"},
    "SUPPLY": {"Supply"},
    # PCP fica entre planejamento e chao de fabrica: quem sequencia (Operations)
    # e quem planeja (Projects) estruturam o produto; Supply consome o resultado.
    "PCP": {"Operations", "Projects"},
}


def owner_of_tag(tag_id: str) -> str:
    tag = store.get_tag(tag_id)
    et = (tag or {}).get("entity_type", "OP")
    return ENTITY_OWNER.get(et, "Operations")


def default_role() -> str:
    return get_settings().vps_default_role


def role_from_session(token: str | None) -> str | None:
    """Papel VPS a partir do token de sessão; None se não há sessão válida."""
    if not token:
        return None
    from ..auth import auth as _auth
    s = _auth.session(token)
    if not s:
        return None
    if s.get("role") == "admin":
        return "Admin"
    if s.get("role") == "view":
        return "Viewer"
    perfil = s.get("perfil")
    return perfil if perfil in PERFIS_OPERACIONAIS else "Operations"


def current_role(
    x_auth_token: str | None = Header(default=None),
    x_vps_role: str | None = Header(default=None),
) -> str:
    """Dependency FastAPI: papel atual.

    Sessão manda. Sem sessão: em dev aberto aceita o cabeçalho (compat local);
    em produção é Viewer — nunca mais "Admin por padrão" para um anônimo.
    """
    r = role_from_session(x_auth_token)
    if r:
        return r
    if get_settings().dev_login and not get_settings().api_key:
        return x_vps_role or default_role()
    return "Viewer"


def can(role: str, owner: str) -> bool:
    if role == "Admin":
        return True
    if role == "Viewer":
        return False
    return role == owner


def _deny(role: str, message: str, **extra: Any) -> HTTPException:
    try:
        from .. import audit
        audit.record("SYSTEM", "RBAC_DENIED", severity="warn", actor=role,
                     entity_type=extra.get("entity_type"), entity_id=extra.get("entity_id"),
                     summary=message[:200], payload={"role": role, **extra})
    except Exception:  # noqa: BLE001
        pass
    return HTTPException(status_code=403, detail={"code": "rbac_denied", "message": message, **extra})


def require(role: str, tag_id: str) -> None:
    """Levanta 403 se o papel não pode governar o Fio (pelo dono do contexto)."""
    owner = owner_of_tag(tag_id)
    if not can(role, owner):
        raise _deny(role, f"Papel '{role}' não pode agir neste Fio (dono: {owner}). Use {owner} ou Admin.",
                    owner=owner, entity_type="tag", entity_id=tag_id)


def require_ctx(role: str, contexto: str, entity_id: str | None = None) -> None:
    """Levanta 403 se o papel não pode executar ações deste contexto (PLANNING, APS...)."""
    if role == "Admin":
        return
    permitidos = CONTEXT_ACTIONS.get(contexto, set())
    if role not in permitidos:
        quem = ", ".join(sorted(permitidos)) or "Admin"
        raise _deny(role, f"Papel '{role}' não pode executar ações de {contexto}. Perfis permitidos: {quem} (ou Admin).",
                    contexto=contexto, entity_type=contexto.lower(), entity_id=entity_id)


def perfis() -> list[dict[str, Any]]:
    """Lista dos perfis operacionais com os contextos que cada um governa."""
    out = []
    for k, v in PERFIS_OPERACIONAIS.items():
        acoes = sorted(c for c, quem in CONTEXT_ACTIONS.items() if k in quem)
        entidades = sorted(e for e, o in ENTITY_OWNER.items() if o == k)
        out.append({"perfil": k, **v, "acoes": acoes, "entidades": entidades})
    return out
