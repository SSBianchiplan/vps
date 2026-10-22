"""Contagem por cruzamento de linha e por zona (lógica pura, sem dependências).

Trabalha com centros de tracks em coordenadas normalizadas [0,1]. Contar por
cruzamento de linha (em vez de por frame) evita o drift de contagem causado por
oclusão/duplicidade (Seção 12 da spec).
"""
from __future__ import annotations

Point = tuple[float, float]


def _side(p: Point, a: Point, b: Point) -> float:
    """Lado de p em relação à reta orientada a→b (>0, <0 ou 0)."""
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def point_in_polygon(p: Point, polygon: list[Point]) -> bool:
    """Ray casting. Polígono em coords normalizadas."""
    if len(polygon) < 3:
        return False
    x, y = p
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi
        ):
            inside = not inside
        j = i
    return inside


class LineCounter:
    """Conta tracks que cruzam uma linha definida por dois pontos (a, b)."""

    def __init__(self, a: Point, b: Point) -> None:
        self.a = a
        self.b = b
        self._last_side: dict[int, float] = {}
        self.total: int = 0          # cruzamentos absolutos
        self.net: int = 0            # saldo direcional (a→b positivo)

    def update(self, centers: dict[int, Point]) -> int:
        """Atualiza com {track_id: centro} e devolve cruzamentos neste frame."""
        crossings = 0
        for tid, c in centers.items():
            s = _side(c, self.a, self.b)
            prev = self._last_side.get(tid)
            self._last_side[tid] = s
            if prev is None or s == 0 or prev == 0:
                continue
            if (prev > 0) != (s > 0):  # mudou de lado
                crossings += 1
                self.total += 1
                self.net += 1 if s > 0 else -1
        return crossings

    def forget_absent(self, present_ids: set[int]) -> None:
        """Remove tracks que sumiram para não vazar memória em sessões longas."""
        for tid in list(self._last_side):
            if tid not in present_ids:
                del self._last_side[tid]


class ZoneCounter:
    """Conta tracks atualmente dentro de uma zona poligonal + entradas únicas."""

    def __init__(self, polygon: list[Point]) -> None:
        self.polygon = polygon
        self._inside: set[int] = set()
        self.unique_entries: int = 0

    def update(self, centers: dict[int, Point]) -> int:
        """Devolve a contagem instantânea (tracks dentro da zona)."""
        current = {tid for tid, c in centers.items() if point_in_polygon(c, self.polygon)}
        new_entries = current - self._inside
        self.unique_entries += len(new_entries)
        self._inside = current
        return len(current)

    @property
    def inside(self) -> set[int]:
        """Track_ids atualmente dentro da zona (após o último update)."""
        return set(self._inside)


def bbox_center(bbox: list[float]) -> Point:
    """Centro de um bbox normalizado [x, y, w, h]."""
    x, y, w, h = bbox
    return (x + w / 2.0, y + h / 2.0)
