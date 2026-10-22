"""Rastreamento temporal (FlowTracker) — VPS_Rastreamento_Objetos.

Sobre o tracking-by-detection do detector (YOLO track=ByteTrack), acumula o
estado TEMPORAL por stream: identidade no tempo, trajetória, cruzamento de linha
com SENTIDO (IN/OUT), ocupação/dwell de zona (cycle time observado), contagem por
ID único e KPIs de fluxo (`CLD_`). Emite eventos semânticos (LINE_CROSSED,
ZONE_ENTERED/EXITED, DWELL_EXCEEDED) — baixo volume, durável.

Lógica pura (coords normalizadas [0,1]); o estado vive na instância do pipeline.
"""
from __future__ import annotations

from typing import Any

from .line_counter import _side, point_in_polygon

Point = tuple[float, float]
_TRAJ_MAX = 32   # pontos por trajetória (janela curta — downsample p/ overlay)


class FlowTracker:
    def __init__(self) -> None:
        self.start_ts: float | None = None
        self.now_ts: float = 0.0
        # linha (sentido)
        self._last_side: dict[int, float] = {}
        self.line_in = 0
        self.line_out = 0
        # zona (dwell)
        self._enter_ts: dict[int, float] = {}     # tid → ts de entrada na zona
        self._exceeded: set[int] = set()          # já alertou DWELL_EXCEEDED
        self.zone_unique = 0
        self.dwells: list[float] = []             # dwells concluídos (s) = cycle time observado
        self.dwell_exceeded = 0
        # identidade / trajetória
        self._seen: set[int] = set()
        self._traj: dict[int, list[Point]] = {}
        self._cls: dict[int, str] = {}

    def update(
        self,
        centers: dict[int, tuple[str, float, float]],   # tid → (classe, x, y)
        ts: float,
        *,
        line: tuple[Point, Point] | None = None,
        zone: list[Point] | None = None,
        dwell_sla_s: float | None = None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        if self.start_ts is None:
            self.start_ts = ts
        self.now_ts = ts
        events: list[dict[str, Any]] = []
        present = set(centers)

        # identidade + trajetória
        for tid, (cls, x, y) in centers.items():
            self._seen.add(tid)
            self._cls[tid] = cls
            tr = self._traj.setdefault(tid, [])
            tr.append((round(x, 4), round(y, 4)))
            if len(tr) > _TRAJ_MAX:
                del tr[0]

        # cruzamento de linha com SENTIDO
        if line:
            a, b = line
            for tid, (cls, x, y) in centers.items():
                s = _side((x, y), a, b)
                prev = self._last_side.get(tid)
                self._last_side[tid] = s
                if prev is None or s == 0 or prev == 0:
                    continue
                if (prev > 0) != (s > 0):
                    direction = "IN" if s > 0 else "OUT"
                    if direction == "IN":
                        self.line_in += 1
                    else:
                        self.line_out += 1
                    events.append({"action": "LINE_CROSSED", "track_id": tid,
                                   "direction": direction, "object_class": cls})
            for tid in list(self._last_side):
                if tid not in present:
                    del self._last_side[tid]

        # zona: ocupação + dwell
        if zone:
            inside = {tid for tid, (cls, x, y) in centers.items() if point_in_polygon((x, y), zone)}
            for tid in inside - set(self._enter_ts):           # entrou
                self._enter_ts[tid] = ts
                self.zone_unique += 1
                events.append({"action": "ZONE_ENTERED", "track_id": tid,
                               "object_class": self._cls.get(tid, "?")})
            for tid in set(self._enter_ts) - inside:            # saiu → fecha dwell
                d = max(0.0, ts - self._enter_ts.pop(tid))
                self._exceeded.discard(tid)
                self.dwells.append(d)
                events.append({"action": "ZONE_EXITED", "track_id": tid, "dwell_s": round(d, 1),
                               "object_class": self._cls.get(tid, "?")})
            if dwell_sla_s:                                     # parado além do SLA
                for tid, enter in self._enter_ts.items():
                    if (ts - enter) > dwell_sla_s and tid not in self._exceeded:
                        self._exceeded.add(tid)
                        self.dwell_exceeded += 1
                        events.append({"action": "DWELL_EXCEEDED", "track_id": tid,
                                       "dwell_s": round(ts - enter, 1), "sla_s": dwell_sla_s,
                                       "object_class": self._cls.get(tid, "?")})

        return self.summary(centers), events

    def summary(self, centers: dict[int, tuple[str, float, float]]) -> dict[str, Any]:
        elapsed_h = max(1e-6, (self.now_ts - (self.start_ts or self.now_ts)) / 3600.0)
        crossings = self.line_in + self.line_out
        dwell_avg = sum(self.dwells) / len(self.dwells) if self.dwells else 0.0
        dwell_max = max(self.dwells) if self.dwells else 0.0
        wip = len(self._enter_ts)
        # KPIs de fluxo (CLD_)
        kpis = {
            "CLD_Throughput": round(crossings / elapsed_h, 1),          # objetos/hora na linha
            "CLD_Dwell_Time": round(dwell_avg, 1),                      # cycle time observado (s)
            "CLD_Zone_WIP": wip,                                        # ocupação atual
            "CLD_Flow_Rate": {"in": self.line_in, "out": self.line_out},
            "CLD_Counterflow_Events": self.line_out,                    # sentido reverso (segurança)
        }
        # trajetórias ativas (só dos tracks presentes neste frame — leve)
        trajectories = [
            {"track_id": tid, "object_class": self._cls.get(tid, "?"), "points": self._traj.get(tid, [])}
            for tid in centers if len(self._traj.get(tid, [])) > 1
        ]
        return {
            "active": len(centers),
            "unique_total": len(self._seen),
            "line_in": self.line_in,
            "line_out": self.line_out,
            "crossings": crossings,
            "zone_unique": self.zone_unique,
            "wip": wip,
            "dwell_avg_s": round(dwell_avg, 1),
            "dwell_max_s": round(dwell_max, 1),
            "dwell_exceeded": self.dwell_exceeded,
            "kpis": kpis,
            "trajectories": trajectories[:40],
        }
