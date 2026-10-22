"""Reconciliação ERP/MES — cruza eventos VPS com documentos do ERP/MES.

Conector configurável: docs são INGERIDOS (CSV/JSON/seed) e PERSISTIDOS em
`vps_erp_doc` (produção = CDC do SAP B1/HANA ou OPC UA do Opcenter). A reconciliação
marca `recon_status` dos eventos por natural_key e sinaliza divergência (qty doc ≠
contagem por visão). Idempotente. VPS reconcilia e referencia — não escreve transação
financeira (P05).
"""
from __future__ import annotations

import csv
import io
from typing import Any

from . import store


def load_docs(docs: list[dict[str, Any]]) -> int:
    return store.upsert_erp_docs(docs)


def docs() -> list[dict[str, Any]]:
    return store.erp_docs()


def clear() -> None:
    store.clear_erp_docs()


def _num(x: Any) -> Any:
    s = str(x or "").strip()
    if s == "":
        return None
    try:
        return int(s) if s.lstrip("-").isdigit() else float(s)
    except ValueError:
        return None


def parse_csv(text: str) -> list[dict[str, Any]]:
    """CSV → docs. Cabeçalho: natural_key,doc,qty,value,status (separador , ou ;)."""
    sample = text[:2048]
    delim = ";" if sample.count(";") > sample.count(",") else ","
    rows: list[dict[str, Any]] = []
    for r in csv.DictReader(io.StringIO(text), delimiter=delim):
        norm = {(k or "").strip().lower(): v for k, v in r.items()}
        nk = (norm.get("natural_key") or norm.get("chave") or "").strip()
        if not nk:
            continue
        rows.append({
            "natural_key": nk,
            "doc": (norm.get("doc") or norm.get("documento") or "").strip() or None,
            "qty": _num(norm.get("qty") or norm.get("quantidade")),
            "value": _num(norm.get("value") or norm.get("valor")),
            "status": (norm.get("status") or "OPEN").strip(),
            "source": "csv",
        })
    return rows


def _last_vision_count(tag_id: str) -> int | None:
    for e in reversed(store.events_for(tag_id)):
        if e.get("vision_mode") == "CONTAR":
            p = e.get("payload") or {}
            if p.get("total") is not None:
                return int(p["total"])
            cont = p.get("contagens") or {}
            if cont:
                return int(sum(int(v) for v in cont.values()))
    return None


def reconcile() -> dict[str, Any]:
    """Cruza tags×docs (da tabela), grava recon_status e sinaliza divergência. Idempotente."""
    tags = store.all_tags(include_archived=True)
    matched = divergent = unmatched = 0
    items: list[dict[str, Any]] = []
    for t in tags:
        nk = t["natural_key"]
        doc = store.get_erp_doc(nk)
        if not doc:
            status = "PENDING"
            unmatched += 1
        else:
            vc, dq = _last_vision_count(t["tag_id"]), doc.get("qty")
            if vc is not None and dq is not None and int(vc) != int(dq):
                status = "DIVERGENT"
                divergent += 1
                if not store.has_open_occurrence(t["tag_id"], "RECON_DIVERGENCE"):
                    store.raise_occurrence(t["tag_id"], t.get("current_phase"), "RECON_DIVERGENCE", "nok",
                                           f"Divergência: visão {vc} ≠ ERP {int(dq)} (doc {doc.get('doc')})")
            else:
                status = "MATCHED"
                matched += 1
        store.set_recon_status(t["tag_id"], status)
        items.append({"tag_id": t["tag_id"], "natural_key": nk, "entity_type": t["entity_type"],
                      "erp_doc": (doc or {}).get("doc"), "status": status})
    total = matched + divergent + unmatched
    return {"rate": round(100 * matched / total, 1) if total else 0.0,
            "matched": matched, "divergent": divergent, "unmatched": unmatched,
            "docs": docs(), "items": items}


def seed_docs() -> dict[str, Any]:
    """Docs ERP de demo: 1 casa, 1 diverge (qty), 1 sem doc (pendente)."""
    load_docs([
        {"natural_key": "OP-2026-04412", "doc": "ERP-OP-77120", "qty": 12, "value": 18450.0, "status": "OPEN", "source": "seed"},
        {"natural_key": "OP-2026-04414", "doc": "ERP-OP-77122", "qty": 12, "value": 15300.0, "status": "OPEN", "source": "seed"},  # visão=10 → divergente
        {"natural_key": "SO-2026-7781", "doc": "ERP-SO-5510", "qty": 1, "value": 51000.0, "status": "OPEN", "source": "seed"},
        # OP-2026-04413 sem doc → unmatched
    ])
    return reconcile()
