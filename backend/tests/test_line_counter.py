"""Contagem por cruzamento de linha e por zona (lógica pura)."""
from __future__ import annotations

from app.tracking.line_counter import (
    LineCounter,
    ZoneCounter,
    bbox_center,
    point_in_polygon,
)


def test_line_crossing_counts_once_per_traversal():
    # Linha vertical em x=0.5; track cruza da esquerda para a direita.
    lc = LineCounter((0.5, 0.0), (0.5, 1.0))
    assert lc.update({1: (0.2, 0.5)}) == 0  # primeira observação, define lado
    assert lc.update({1: (0.4, 0.5)}) == 0  # mesmo lado
    assert lc.update({1: (0.7, 0.5)}) == 1  # cruzou
    assert lc.total == 1
    assert lc.update({1: (0.9, 0.5)}) == 0  # já do outro lado


def test_line_counts_each_distinct_track():
    lc = LineCounter((0.5, 0.0), (0.5, 1.0))
    lc.update({1: (0.2, 0.5), 2: (0.2, 0.2)})
    n = lc.update({1: (0.8, 0.5), 2: (0.8, 0.2)})
    assert n == 2 and lc.total == 2


def test_forget_absent_frees_state():
    lc = LineCounter((0.5, 0.0), (0.5, 1.0))
    lc.update({1: (0.2, 0.5)})
    lc.forget_absent(present_ids=set())
    assert 1 not in lc._last_side


def test_point_in_polygon_square():
    sq = [(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)]
    assert point_in_polygon((0.5, 0.5), sq) is True
    assert point_in_polygon((0.1, 0.5), sq) is False


def test_zone_counter_unique_entries():
    zc = ZoneCounter([(0.4, 0.4), (0.6, 0.4), (0.6, 0.6), (0.4, 0.6)])
    assert zc.update({1: (0.5, 0.5)}) == 1  # dentro
    assert zc.update({1: (0.5, 0.5)}) == 1  # ainda dentro, sem nova entrada
    zc.update({1: (0.0, 0.0)})              # saiu
    zc.update({1: (0.5, 0.5)})              # entrou de novo
    assert zc.unique_entries == 2


def test_zone_inside_property_reflects_current():
    zc = ZoneCounter([(0.4, 0.4), (0.6, 0.4), (0.6, 0.6), (0.4, 0.6)])
    zc.update({1: (0.5, 0.5), 2: (0.0, 0.0)})
    assert zc.inside == {1}
    zc.update({1: (0.0, 0.0), 2: (0.5, 0.5)})
    assert zc.inside == {2}


def test_bbox_center():
    assert bbox_center([0.0, 0.0, 0.4, 0.6]) == (0.2, 0.3)
