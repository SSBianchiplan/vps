"""Configurações de sistema persistidas no banco (chave→JSON).

Guarda o catálogo de componentes UI/UX (básicos + avançados), o schema de campos
obrigatórios dos links do supervisório (Automação Industrial), a aparência
sincronizada e o estado de implantação em ondas (alinhado às 8 ondas do VPS).
"""
from __future__ import annotations

import json as _json
from datetime import datetime, timezone
from typing import Any

from .db.database import get_connection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get(key: str, default: Any = None) -> Any:
    r = get_connection().execute("SELECT json FROM app_config WHERE key=?", (key,)).fetchone()
    if r:
        try:
            return _json.loads(dict(r)["json"])
        except Exception:  # noqa: BLE001
            pass
    return default


def put(key: str, value: Any) -> dict[str, Any]:
    get_connection().execute(
        "INSERT INTO app_config(key,json,updated_at) VALUES (?,?,?)"
        " ON CONFLICT(key) DO UPDATE SET json=excluded.json, updated_at=excluded.updated_at",
        (key, _json.dumps(value, ensure_ascii=False), _now()))
    return {"ok": True, "key": key}


def keys() -> list[str]:
    return [dict(r)["key"] for r in get_connection().execute("SELECT key FROM app_config ORDER BY key").fetchall()]


# ── Catálogo UI/UX (átomos→organismos) · wave = onda de implantação (1..8) ──
def _c(cid: str, name: str, en: str, tier: str, group: str, wave: int, enabled: bool) -> dict[str, Any]:
    return {"id": cid, "name": name, "en": en, "tier": tier, "group": group, "wave": wave, "enabled": enabled}


UI_COMPONENTS = [
    # ── Básicos · Controles de entrada ──
    _c("button", "Botão", "Button", "basico", "Controles de entrada", 1, True),
    _c("text-input", "Campo de texto", "Text Input", "basico", "Controles de entrada", 1, True),
    _c("textarea", "Área de texto", "Textarea", "basico", "Controles de entrada", 3, True),
    _c("select", "Menu suspenso", "Dropdown/Select", "basico", "Controles de entrada", 2, True),
    _c("checkbox", "Caixa de seleção", "Checkbox", "basico", "Controles de entrada", 2, True),
    _c("radio", "Botão de opção", "Radio Button", "basico", "Controles de entrada", 2, True),
    _c("toggle", "Chave de alternância", "Toggle Switch", "basico", "Controles de entrada", 2, True),
    _c("slider", "Controle deslizante", "Slider", "basico", "Controles de entrada", 3, True),
    _c("file-input", "Seletor de arquivo", "File Input", "basico", "Controles de entrada", 3, True),
    # ── Básicos · Navegação ──
    _c("link", "Hiperlink", "Link", "basico", "Navegação básica", 1, True),
    _c("navbar", "Barra de navegação", "Navbar", "basico", "Navegação básica", 3, True),
    _c("hamburger", "Menu hambúrguer", "Hamburger Menu", "basico", "Navegação básica", 3, True),
    _c("tabs", "Abas", "Tabs", "basico", "Navegação básica", 3, True),
    _c("footer", "Rodapé", "Footer", "basico", "Navegação básica", 3, True),
    # ── Básicos · Exibição e feedback ──
    _c("icon", "Ícone", "Icon", "basico", "Exibição e feedback", 1, True),
    _c("label", "Rótulo", "Label", "basico", "Exibição e feedback", 1, True),
    _c("tooltip", "Dica de ferramenta", "Tooltip", "basico", "Exibição e feedback", 2, True),
    _c("avatar", "Imagem/Avatar", "Image/Avatar", "basico", "Exibição e feedback", 3, True),
    _c("spinner", "Indicador de carregamento", "Spinner/Loader", "basico", "Exibição e feedback", 2, True),
    _c("progress", "Barra de progresso", "Progress Bar", "basico", "Exibição e feedback", 3, True),
    _c("badge", "Distintivo", "Badge", "basico", "Exibição e feedback", 2, True),
    # ── Avançados · Entradas e seletores ──
    _c("autocomplete", "Preenchimento automático", "Autocomplete/Combobox", "avancado", "Entradas avançadas", 6, True),
    _c("tag-input", "Entrada de tags", "Chips/Tag Input", "avancado", "Entradas avançadas", 6, True),
    _c("date-range", "Seletor de período", "Date Range Picker", "avancado", "Entradas avançadas", 6, True),
    _c("masked-input", "Entrada de máscara", "Masked Input", "avancado", "Entradas avançadas", 6, True),
    _c("rich-text", "Editor de texto rico", "Rich Text Editor", "avancado", "Entradas avançadas", 7, True),
    _c("dropzone", "Área de soltar arquivos", "Drag and Drop Zone", "avancado", "Entradas avançadas", 7, True),
    # ── Avançados · Navegação e estrutura ──
    _c("breadcrumbs", "Caminho de rato", "Breadcrumbs", "avancado", "Navegação avançada", 7, True),
    _c("tree-view", "Navegação em árvore", "Tree View", "avancado", "Navegação avançada", 7, True),
    _c("context-menu", "Menu de contexto", "Context Menu", "avancado", "Navegação avançada", 8, True),
    _c("accordion", "Painel retrátil", "Accordion", "avancado", "Navegação avançada", 7, True),
    _c("stepper", "Passo a passo / Fluxo", "Stepper", "avancado", "Navegação avançada", 7, True),
    _c("fab", "Menu flutuante de ação", "FAB", "avancado", "Navegação avançada", 8, True),
    _c("mega-menu", "Megamenu", "Mega Menu", "avancado", "Navegação avançada", 8, True),
    # ── Avançados · Dados de alta densidade ──
    _c("data-table", "Tabela dinâmica", "Data Table", "avancado", "Dados de alta densidade", 4, True),
    _c("card", "Cartão", "Card", "avancado", "Dados de alta densidade", 4, True),
    _c("virtual-list", "Lista virtual", "Virtual List", "avancado", "Dados de alta densidade", 5, True),
    _c("carousel", "Carrossel", "Carousel", "avancado", "Dados de alta densidade", 5, True),
    _c("charts", "Gráficos interativos", "Charts/Dashboards", "avancado", "Dados de alta densidade", 4, True),
    _c("timeline", "Linha do tempo", "Timeline", "avancado", "Dados de alta densidade", 5, True),
    # ── Avançados · Janelas, feedback e notificações ──
    _c("modal", "Janela modal", "Modal/Dialog", "avancado", "Janelas e notificações", 5, True),
    _c("drawer", "Painel lateral (gaveta)", "Drawer/Off-canvas", "avancado", "Janelas e notificações", 5, True),
    _c("toast", "Toast / Snackbar", "Toast/Snackbar", "avancado", "Janelas e notificações", 5, True),
    _c("system-banner", "Banner do sistema", "System Banner", "avancado", "Janelas e notificações", 8, True),
    _c("skeleton", "Esqueleto de carregamento", "Skeleton Screen", "avancado", "Janelas e notificações", 8, True),
    _c("tour", "Passo a passo guiado", "Tour/Walkthrough", "avancado", "Janelas e notificações", 8, True),
]

# ── Schema de campos dos links do supervisório (Automação) ──
# required = lista de kinds para os quais o campo é OBRIGATÓRIO.
SUP_LINK_FIELDS = [
    {"name": "tag", "label": "Tag da linha (P&ID)", "type": "text",
     "required": ["process", "signal", "electric", "vision"], "placeholder": "LN-1001 / SIG-204"},
    {"name": "direction", "label": "Sentido do fluxo", "type": "select",
     "options": ["uni", "bi"], "required": ["process", "signal", "electric", "vision"], "default": "uni"},
    {"name": "priority", "label": "Criticidade", "type": "select",
     "options": ["baixa", "normal", "alta", "critica"], "required": ["process", "signal", "electric", "vision"], "default": "normal"},
    {"name": "medium", "label": "Meio / fluido", "type": "select",
     "options": ["água", "vapor", "ar comprimido", "óleo", "gás", "produto", "efluente", "inspeção/visão"],
     "required": ["process", "vision"]},
    {"name": "signal_type", "label": "Tipo de sinal", "type": "select",
     "options": ["4-20mA", "0-10V", "Digital", "PROFINET", "PROFIBUS", "Modbus", "OPC UA", "HART", "IO-Link"],
     "required": ["signal", "electric"]},
    {"name": "diameter", "label": "Bitola / seção", "type": "text", "required": [], "placeholder": "DN50 / 2.5mm²"},
    {"name": "engineering_unit", "label": "Unidade de engenharia", "type": "text", "required": []},
    {"name": "interlock", "label": "Participa de intertravamento", "type": "bool", "required": []},
    {"name": "description", "label": "Descrição", "type": "text", "required": []},
]

DEFAULT_ROLLOUT = {"current_wave": 3, "waves": 8, "vps_aligned": True,
                   "note": "Ondas alinhadas às 8 ondas do VPS: componentes com onda ≤ atual ficam ativos no sistema."}


def required_for(kind: str) -> list[str]:
    return [f["name"] for f in (get("sup_link_fields") or SUP_LINK_FIELDS) if kind in f.get("required", [])]


def validate_link(link: dict[str, Any]) -> list[str]:
    """Retorna lista de campos obrigatórios faltando para o link (vazio = válido)."""
    kind = link.get("kind", "process")
    missing = []
    for name in required_for(kind):
        v = link.get(name)
        if v is None or (isinstance(v, str) and not v.strip()):
            missing.append(name)
    return missing


def seed() -> None:
    if get("ui_components") is None:
        put("ui_components", UI_COMPONENTS)
    if get("sup_link_fields") is None:
        put("sup_link_fields", SUP_LINK_FIELDS)
    if get("ui_rollout") is None:
        put("ui_rollout", DEFAULT_ROLLOUT)
