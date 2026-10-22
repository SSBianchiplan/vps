"""Ponte Visão → VPS — resultados de inferência viram VPS_EVENT automaticamente.

- LER: detecta Tag-ID/nº de OP na leitura → GÊNESE do Fio Dourado; liga a fonte ao tag.
- CONTAR/DESCREVER/ANALISAR: anexa evento de verificação ao tag ligado à fonte
  (observação; não força transição). ANALISAR com veredito NOK → ocorrência.

Best-effort: NUNCA interrompe a inferência. Dedup: gênese só (re)dispara quando o
tag muda; verificação é throttled por fonte.
"""
from __future__ import annotations

import re
import time

from ..config import get_settings
from ..logging_conf import get_logger
from ..schemas.results import InferenceResult
from . import engine, store, tagid

log = get_logger("visiondesk.vps.bridge")

# estado de sessão (em memória; reseta no restart)
_bound: dict[str, str] = {}        # source_id → tag_id atual
_last_verif: dict[str, float] = {}  # source_id → monotonic do último evento de verificação
_auto_override: bool | None = None  # toggle runtime (UI); None = usa settings
_segment_override: str | None = None  # segmento runtime p/ Tag-IDs gerados da visão
_VERIF_MIN_S = 8.0                  # intervalo mínimo entre verificações por fonte

# Tag-ID canônico completo OU nº de OP solto na leitura
_TAG_RE = re.compile(r"VPS:[A-Z0-9]+:[A-Z0-9]+:[^\s:]+:[0-9]+", re.I)
_OP_RE = re.compile(r"\bOP[-_/ ]?([A-Z0-9][A-Z0-9\-./]{2,})\b", re.I)

_GENESIS_ACTION = {"OP": "OP_OPENED", "SO": "SO_CREATED", "PROJ": "MILESTONE_REACHED"}


def auto_enabled() -> bool:
    return get_settings().vps_auto_capture if _auto_override is None else _auto_override


def set_auto(on: bool) -> None:
    global _auto_override
    _auto_override = on


def segment() -> str:
    return _segment_override or get_settings().vps_segment


def set_segment(seg: str) -> None:
    global _segment_override
    _segment_override = seg


def bindings() -> dict[str, str]:
    return dict(_bound)


def bind(source_id: str, tag_id: str) -> None:
    """Liga manualmente uma fonte a um Tag-ID (p/ verificação sem LER)."""
    _bound[source_id] = tag_id


def unbind(source_id: str) -> None:
    _bound.pop(source_id, None)


def _detect_tag(leituras: list[dict], segment: str) -> str | None:
    for l in leituras:
        txt = (l.get("texto") or "").strip()
        if not txt:
            continue
        m = _TAG_RE.search(txt)
        if m:
            return m.group(0).upper()
        m = _OP_RE.search(txt)
        if m:
            nat = "OP-" + re.sub(r"^OP[-_/ ]?", "", m.group(0), flags=re.I).strip()
            return tagid.build(segment, "OP", nat)
    return None


def on_inference(r: InferenceResult) -> None:
    """Chamado após gravar a inferência (best-effort)."""
    if not auto_enabled():
        return
    try:
        mode = r.mode.value
        src = r.source_id or "ip_camera"
        res = r.result or {}
        from . import operators
        common = {
            "vision_mode": mode, "confidence": r.confidence, "model_version": r.model_version,
            "source_type": src, "station_id": src, "event_ts": r.timestamp,
            "operator_id": operators.current(src),   # operador logado na estação (P05)
        }

        if mode == "LER":
            tag = _detect_tag(res.get("leituras", []) or [], segment())
            if not tag or _bound.get(src) == tag:
                return  # nada legível ou já ligado a este tag (dedup)
            parsed = tagid.parse(tag)
            action = _GENESIS_ACTION.get(parsed.entity_type if parsed else "OP", "OP_OPENED")
            engine.capture({"tag_id": tag, "action": action, "payload": {"genesis_via": "LER"}, **common})
            _bound[src] = tag
            log.info("VPS gênese: %s ← %s (%s)", tag, src, action)
            return

        # verificação contínua → precisa de uma fonte já ligada a um tag
        tag = _bound.get(src)
        if not tag:
            return
        now = time.monotonic()
        if now - _last_verif.get(src, 0.0) < _VERIF_MIN_S:
            return
        _last_verif[src] = now

        if mode == "CONTAR":
            cont = res.get("contagens", {}) or {}
            total = res.get("total")
            if total is None:
                total = sum(int(v) for v in cont.values()) if cont else 0
            action, payload = "VISION_COUNT", {"total": total, "contagens": cont}
        elif mode == "ANALISAR":
            action, payload = "VISION_CHECK", {"veredito": res.get("veredito"), "resumo": res.get("resumo")}
        else:  # DESCREVER
            action, payload = "VISION_DESCRIBE", {"descricao": (res.get("descricao") or "")[:200]}

        out = engine.capture({"tag_id": tag, "action": action, "payload": payload, **common})
        if mode == "ANALISAR":
            ver = (res.get("veredito") or "").strip()
            if ver and ver.upper() not in ("OK", "APROVADO", "CONFORME"):
                store.raise_occurrence(tag, out.get("phase"), "VISION_NOK", "nok",
                                       f"Veredito de visão: {ver}", r.result.get("image_uri") if r.result else None)
    except Exception:  # noqa: BLE001
        log.exception("VPS bridge falhou (não fatal)")
