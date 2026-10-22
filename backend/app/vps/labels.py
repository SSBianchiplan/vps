"""Gerador de Tags — Tag-ID canônico + QR (segno) p/ etiqueta física.

Ver `VPS_Gerador_de_Tags.md`. O QR codifica o Tag-ID (ou deep link). A geração NÃO
abre a instância — quem abre é a LEITURA do token pela câmera (P01). QR correção
nível Q (industrial). Degrada p/ qr_svg=None se segno ausente (etiqueta vira texto OCR).
"""
from __future__ import annotations

import io
import uuid
from typing import Any

from . import engine, rbac, store, tagid


def prefill(tag_id: str) -> dict[str, Any] | None:
    """Deriva todos os campos da etiqueta a partir de um Fio existente (auto-fill)."""
    tag = store.get_tag(tag_id)
    if not tag:
        return None
    parent = ""
    parents = store.parents_of(tag_id)
    if parents:
        p = tagid.parse(parents[0]["parent_tag_id"])
        if p:
            parent = f"{p.entity_type}:{p.natural_key}"
    sla = (engine._phase_def(tag["template_id"], tag.get("current_phase")) or {}).get("sla_hours")  # noqa: SLF001
    return {
        "segment": tag["segment"], "entity_type": tag["entity_type"], "natural_key": tag["natural_key"],
        "instance": tag.get("instance", "01"), "parent": parent, "estado": tag["state"],
        "phase": tag.get("current_phase"), "template_id": tag["template_id"],
        "owner": rbac.ENTITY_OWNER.get(tag["entity_type"], "Operations"),
        "sla": f"{int(sla)}h" if sla else "",
    }


def print_batch() -> str:
    return "IMP-" + uuid.uuid4().hex[:5].upper()


def qr_svg(text: str, ec: str = "Q", dark: str = "#14110e") -> str | None:
    """QR como <svg> inline (sem prolog XML), pronto p/ embutir em HTML."""
    try:
        import segno  # type: ignore
    except Exception:  # noqa: BLE001
        return None
    try:
        qr = segno.make(text, error=ec.lower())
        buf = io.BytesIO()
        qr.save(buf, kind="svg", scale=4, border=1, dark=dark, xmldecl=False, svgns=True)
        return buf.getvalue().decode("utf-8")
    except Exception:  # noqa: BLE001
        return None


def payload_of(segment: str, entity_type: str, natural_key: str, instance: str,
               encode: str = "TAGID") -> tuple[str, str]:
    tid = tagid.build(segment, entity_type, natural_key, instance)
    if encode == "DEEPLINK":
        return tid, f"https://vps.gplan/thread/{tid}"
    return tid, tid


def generate(d: dict[str, Any]) -> dict[str, Any]:
    tid, payload = payload_of(d["segment"], d["entity_type"], d["natural_key"],
                              d.get("instance", "01"), d.get("encode", "TAGID"))
    return {
        **d,
        "tag_id": tid,
        "qr_payload": payload,
        "qr_svg": qr_svg(payload),
        "print_batch": d.get("print_batch") or print_batch(),
        "printable": True,
    }


def batch(items: list[dict[str, Any]], defaults: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    base = defaults or {}
    return [generate({**base, **it}) for it in items]
