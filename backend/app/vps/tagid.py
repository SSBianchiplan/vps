"""Tag-ID — chave universal do Fio Dourado.

Formato canônico (tolerante a legado):
    VPS:{segment}:{entity_type}:{natural_key}:{instance}
    ex.: VPS:PANEL:OP:OP-2026-04412:01
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TagId:
    segment: str
    entity_type: str
    natural_key: str
    instance: str = "01"

    def __str__(self) -> str:
        return f"VPS:{self.segment}:{self.entity_type}:{self.natural_key}:{self.instance}"


def build(segment: str, entity_type: str, natural_key: str, instance: str = "01") -> str:
    return str(TagId(segment.upper(), entity_type.upper(), natural_key, instance))


def parse(tag_id: str) -> TagId | None:
    """Quebra o Tag-ID canônico. None se não casar o formato VPS:..."""
    p = (tag_id or "").split(":")
    if len(p) >= 5 and p[0] == "VPS":
        # natural_key pode conter ':' → junta o miolo, instance é o último
        return TagId(p[1], p[2], ":".join(p[3:-1]), p[-1])
    if len(p) == 5 and p[0] == "VPS":
        return TagId(p[1], p[2], p[3], p[4])
    return None
