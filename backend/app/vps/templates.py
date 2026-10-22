"""Process Template Library — o fluxo de fases é DECLARADO, não codificado.

Trocar o template (não a engine) adapta o VPS a qualquer segmento (SPEC_VPS §13).
Cada fase: entry/exit (ações que entram/saem), vision (modo+confiança), blocking_on
(ação que abre pendência bloqueante), sla_hours.
"""
from __future__ import annotations

from typing import Any

# resolução do template na gênese: por entity_type (global) e, p/ OP, por segmento
SEGMENT_OP: dict[str, str] = {
    "PANEL": "PANEL_ETO_V1", "GENERIC": "GENERIC_V1",
    "FOOD": "FOOD_V1", "PHARMA": "PHARMA_V1",
}
ENTITY_TEMPLATE: dict[str, str] = {"SO": "SO_OTC_V1", "PROJ": "PROJ_V1", "SHIP": "SHIP_V1"}

TEMPLATES: dict[str, dict[str, Any]] = {
    "PANEL_ETO_V1": {
        "template_id": "PANEL_ETO_V1",
        "segment": "PANEL",
        "label": "Painel Elétrico (ETO)",
        "phases": [
            {"id": "ENGINEERING", "entry": ["SO_RELEASED", "OP_OPENED"], "exit": ["DRAWINGS_APPROVED"], "sla_hours": 24},
            {"id": "PURCHASING", "exit": ["SUPPLY_LINKED"], "sla_hours": 48},
            {"id": "PICKING", "vision": {"mode": "CONTAR", "min_confidence": 0.95},
             "exit": ["PICK_COMPLETED"], "blocking_on": ["PICK_SHORT"], "sla_hours": 8},
            {"id": "ASSEMBLY", "vision": {"mode": "DESCREVER"}, "exit": ["OP_OPERATION_DONE"], "sla_hours": 40},
            {"id": "TESTING", "vision": {"mode": "ANALISAR"}, "exit": ["MEASUREMENT_APPROVED"], "sla_hours": 8},
            {"id": "SHIPPING", "exit": ["SHIPPED"], "sla_hours": 24},
            {"id": "BILLING", "exit": ["INVOICE_ISSUED"], "sla_hours": 24},
        ],
        "closes_on": ["INVOICE_ISSUED"],
    },
    "GENERIC_V1": {
        "template_id": "GENERIC_V1",
        "segment": "GENERIC",
        "label": "Genérico (recebimento → expedição)",
        "phases": [
            {"id": "INTAKE", "entry": ["OP_OPENED", "RECEIVED"], "exit": ["INTAKE_DONE"], "sla_hours": 8},
            {"id": "PROCESS", "vision": {"mode": "CONTAR"}, "exit": ["PROCESS_DONE"], "blocking_on": ["SHORT"], "sla_hours": 24},
            {"id": "QC", "vision": {"mode": "ANALISAR"}, "exit": ["QC_APPROVED"], "sla_hours": 8},
            {"id": "SHIPPING", "exit": ["SHIPPED"], "sla_hours": 24},
        ],
        "closes_on": ["SHIPPED", "DELIVERED"],
    },
    "SO_OTC_V1": {
        "template_id": "SO_OTC_V1", "segment": "GENERIC", "label": "Pedido de Venda (OTC)",
        "phases": [
            {"id": "CREATED", "entry": ["SO_CREATED"], "exit": ["SO_RELEASED"], "sla_hours": 24},
            {"id": "RELEASED", "exit": ["SO_FULFILLED"], "sla_hours": 168},
        ],
        "closes_on": ["SO_FULFILLED"],
    },
    "PROJ_V1": {
        "template_id": "PROJ_V1", "segment": "GENERIC", "label": "Projeto / Planejamento",
        "phases": [
            {"id": "PLANNING", "entry": ["MILESTONE_REACHED", "BASELINE_SET"], "exit": ["BASELINE_SET"], "sla_hours": 48},
            {"id": "EXECUTION", "exit": ["PROJECT_DELIVERED"], "sla_hours": 720},
        ],
        "closes_on": ["PROJECT_DELIVERED"],
    },
    "SHIP_V1": {
        "template_id": "SHIP_V1", "segment": "GENERIC", "label": "Logística / Expedição",
        "phases": [
            {"id": "LOADING", "entry": ["LOADED"], "exit": ["SHIPPED"], "sla_hours": 8},
            {"id": "TRANSIT", "exit": ["DELIVERED"], "sla_hours": 72},
        ],
        "closes_on": ["DELIVERED"],
    },
    "FOOD_V1": {
        "template_id": "FOOD_V1", "segment": "FOOD", "label": "Alimentos (recebimento→expedição)",
        "phases": [
            {"id": "RECEIVING", "entry": ["OP_OPENED", "RECEIVED"], "exit": ["RECEIVING_DONE"], "sla_hours": 4},
            {"id": "PROCESSING", "vision": {"mode": "CONTAR", "min_confidence": 0.9}, "exit": ["PROCESS_DONE"], "blocking_on": ["SHORT"], "sla_hours": 12},
            {"id": "PACKAGING", "vision": {"mode": "DESCREVER"}, "exit": ["PACKED"], "sla_hours": 6},
            {"id": "COLD_STORAGE", "exit": ["STORED"], "sla_hours": 24},
            {"id": "SHIPPING", "exit": ["SHIPPED"], "sla_hours": 12},
        ],
        "closes_on": ["SHIPPED"],
    },
    "PHARMA_V1": {
        "template_id": "PHARMA_V1", "segment": "PHARMA", "label": "Farma (lote rastreável + QC)",
        "phases": [
            {"id": "DISPENSING", "entry": ["OP_OPENED", "DISPENSED"], "exit": ["DISPENSE_DONE"], "sla_hours": 8},
            {"id": "PRODUCTION", "vision": {"mode": "DESCREVER"}, "exit": ["PRODUCTION_DONE"], "sla_hours": 48},
            {"id": "QC", "vision": {"mode": "ANALISAR", "min_confidence": 0.97}, "exit": ["QC_APPROVED"], "blocking_on": ["QC_FAILED"], "sla_hours": 24},
            {"id": "RELEASE", "exit": ["RELEASED"], "sla_hours": 12},
            {"id": "DISTRIBUTION", "exit": ["SHIPPED"], "sla_hours": 24},
        ],
        "closes_on": ["SHIPPED"],
    },
}

# action → domínio (bounded context) p/ classificar o evento
_DOMAIN_PREFIX: dict[str, str] = {
    "OP": "OP", "PICK": "PICK", "SUPPLY": "SUPPLY", "STOCK": "STOCK",
    "OCCURRENCE": "OCC", "PENDING": "PENDING", "SO": "SALES", "PROJ": "PROJECT",
    "MILESTONE": "PROJECT", "MEASUREMENT": "MEAS", "INVOICE": "BILLING",
    "BILLABLE": "BILLING", "DRAWINGS": "ENGINEERING",
}
_DOMAIN_EXACT: dict[str, str] = {
    "RECEIVED": "ALMOX", "PUTAWAY": "ALMOX", "MOVED": "ALMOX", "ISSUED": "ALMOX",
    "LOADED": "LOGISTICS", "SHIPPED": "LOGISTICS", "DELIVERED": "LOGISTICS",
}

# action → owner (P05: todo dado tem dono)
_OWNER: dict[str, str] = {
    "OP": "Operations", "PICK": "Supply", "SUPPLY": "Supply", "STOCK": "Supply",
    "ALMOX": "Supply", "SALES": "Sales", "PROJECT": "Projects", "MEAS": "Quality",
    "OCC": "Quality", "BILLING": "Finance", "LOGISTICS": "Operations",
    "ENGINEERING": "Engineering",
}


def get(template_id: str) -> dict[str, Any] | None:
    return TEMPLATES.get(template_id)


def resolve_template(segment: str, entity_type: str = "OP") -> str:
    """Template por entity_type (SO/PROJ/SHIP globais); OP varia por segmento."""
    et = (entity_type or "OP").upper()
    if et in ENTITY_TEMPLATE:
        return ENTITY_TEMPLATE[et]
    if et == "OP":
        return SEGMENT_OP.get((segment or "").upper(), "GENERIC_V1")
    return "GENERIC_V1"


def segments() -> list[dict[str, str]]:
    """Segmentos disponíveis (p/ seleção de gênese e filtro do board)."""
    out = []
    for seg, tid in SEGMENT_OP.items():
        tpl = TEMPLATES.get(tid, {})
        out.append({"segment": seg, "template_id": tid, "label": tpl.get("label", seg)})
    return out


def sla_total(template_id: str | None) -> float:
    tpl = get(template_id or "")
    return float(sum(p.get("sla_hours", 0) for p in tpl["phases"])) if tpl else 0.0


GENESIS_ACTION = {"OP": "OP_OPENED", "SO": "SO_CREATED", "PROJ": "MILESTONE_REACHED"}


def genesis_action(entity_type: str) -> str:
    return GENESIS_ACTION.get((entity_type or "OP").upper(), "OP_OPENED")


def domain_of(action: str) -> str:
    if action in _DOMAIN_EXACT:
        return _DOMAIN_EXACT[action]
    return _DOMAIN_PREFIX.get(action.split("_")[0], "GENERIC")


def owner_of(action: str) -> str:
    return _OWNER.get(domain_of(action), "Operations")


def phase_for_action(template_id: str, action: str) -> dict[str, Any] | None:
    """Fase cuja entry OU exit contém a ação (define a fase 'tocada' pelo evento)."""
    tpl = get(template_id)
    if not tpl:
        return None
    for ph in tpl["phases"]:
        if action in (ph.get("entry", []) + ph.get("exit", []) + ph.get("blocking_on", [])):
            return ph
    return None
