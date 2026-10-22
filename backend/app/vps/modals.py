"""Modais & Vínculos de Dados — resolve cada campo a partir da sua fonte real.

Materializa o princípio do doc: "dado vinculado a dado". Cada campo carrega a
origem (MD/TAG/LIN/EVT/PROJ/VIS/TPL/REC/CALC/IN) e se é read-only (vínculo) ou
entrada (vira evento). Ver VPS_Modais_Vinculos_Dados.md.
"""
from __future__ import annotations

from typing import Any

from . import engine, store, tagid

ORIGINS = {
    "MD": "Master data (VPS_DIM_*)", "TAG": "Tag-ID", "LIN": "Linhagem", "EVT": "Event store",
    "PROJ": "Projeção/estado", "VIS": "Visão", "TPL": "Template", "REC": "Reconciliação",
    "CALC": "Derivado", "IN": "Entrada → evento",
}

_TITLES = {
    "M2": "M2 · Leitura / Resolução", "M4": "M4 · Pendência", "M5": "M5 · Ocorrência",
    "M6": "M6 · Fio Dourado", "M8": "M8 · Reconciliação",
}


def _f(modal: str, label: str, value: Any, origin: str, editable: bool = False) -> dict[str, Any]:
    return {"modal": modal, "label": label, "value": None if value is None else str(value),
            "origin": origin, "editable": editable}


def resolve(tag_id: str) -> dict[str, Any] | None:
    tag = store.get_tag(tag_id)
    if not tag:
        return None
    p = tagid.parse(tag_id)
    th = engine.thread(tag_id)
    events = th["timeline"]
    parents, children = th["lineage"]["parents"], th["lineage"]["children"]
    pend = th["pendencies"]
    occ = [o for o in th["occurrences"] if not o["resolved_ts"]]
    ler = next((e for e in reversed(events) if e.get("vision_mode") == "LER"), None)
    vis_imgs = sum(1 for e in events if e.get("image_uri"))
    last_owner = next((e.get("owner") for e in reversed(events) if e.get("owner")), None)
    recon_status = next((e.get("recon_status") for e in reversed(events) if e.get("recon_status")), "PENDING")
    parent_lbl = "—"
    if parents:
        pp = tagid.parse(parents[0]["parent_tag_id"])
        parent_lbl = f"{pp.entity_type} {pp.natural_key}" if pp else parents[0]["parent_tag_id"]

    f: list[dict[str, Any]] = []
    # M6 — Fio Dourado (consulta-âncora)
    f += [
        _f("M6", "Tag-ID", tag_id, "TAG"), _f("M6", "Estado", tag["state"], "PROJ"),
        _f("M6", "Fase atual", tag.get("current_phase"), "PROJ"),
        _f("M6", "Timeline", f"{len(events)} evento(s)", "EVT"),
        _f("M6", "Linhagem", f"{len(parents)} pai · {len(children)} filho(s)", "LIN"),
        _f("M6", "Gargalo", th["kpis"]["bottleneck"] or "—", "CALC"),
        _f("M6", "Lead time (h)", th["kpis"]["lead_time_h"], "CALC"),
        _f("M6", "Evidências", f"{vis_imgs} imagem(ns)", "VIS"),
    ]
    # M2 — Leitura / Resolução
    f += [
        _f("M2", "Valor lido", (ler or {}).get("payload", {}).get("token") if ler else None, "VIS"),
        _f("M2", "Tag-ID canônico", tag_id, "TAG"),
        _f("M2", "Segmento", p.segment if p else None, "TAG"),
        _f("M2", "Tipo", p.entity_type if p else None, "TAG"),
        _f("M2", "Chave natural", p.natural_key if p else None, "TAG"),
        _f("M2", "Origem (pai)", parent_lbl, "LIN"),
        _f("M2", "Fase esperada", tag.get("current_phase"), "TPL"),
        _f("M2", "Template", tag["template_id"], "TPL"),
        _f("M2", "Confiança", (ler or {}).get("confidence"), "VIS"),
        _f("M2", "Owner", last_owner, "MD"),
    ]
    # M4 — Pendência (se houver)
    if pend:
        pd = pend[0]
        f += [
            _f("M4", "Causa", pd["reason"], "EVT"), _f("M4", "Fase", pd["phase"], "TPL"),
            _f("M4", "Idade (h)", round(engine._hours_since(pd["opened_ts"]), 1), "CALC"),  # noqa: SLF001
            _f("M4", "Ação tomada", "", "IN", True),
        ]
    # M5 — Ocorrência (se houver)
    if occ:
        oc = occ[0]
        f += [
            _f("M5", "Tipo", oc["kind"], "EVT"), _f("M5", "Severidade", oc["severity"], "IN", True),
            _f("M5", "Descrição", oc["note"], "VIS", True), _f("M5", "Resolução", "", "IN", True),
        ]
    # M8 — Reconciliação
    doc = store.get_erp_doc(tag["natural_key"])
    f += [
        _f("M8", "Documento ERP", (doc or {}).get("doc") or "—", "REC"),
        _f("M8", "Status", recon_status, "REC"),
    ]

    groups: dict[str, list] = {}
    for x in f:
        groups.setdefault(x["modal"], []).append(x)
    return {
        "tag_id": tag_id,
        "modais": [{"id": k, "title": _TITLES.get(k, k), "fields": v} for k, v in groups.items()],
        "origins": ORIGINS,
    }
