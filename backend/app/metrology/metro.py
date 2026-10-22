"""Metrologia óptica / inspeção dimensional (VisionDesk_Metrologia_Inspecao_Dimensional).

Visão como INSTRUMENTO de medição: calibração px→mm rastreável, medição de cotas
(linear/diâmetro/ângulo) entre pontos, comparação com tolerância → CONFORME/NÃO
CONFORME + incerteza. Eventos MEASUREMENT_* + ocorrência na rejeição. KPIs (Cpk).

Sem óptica telecêntrica/sub-pixel industrial: medição por pontos sobre o frame
calibrado (OpenCV) — interface igual à de Cognex/LabVIEW; o que importa é o
**evento de medição padronizado** (o VPS abstrai a fonte).
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from ..db.database import get_connection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Calibração (px→mm, rastreável) ───────────────────────────────────
def set_calibration(ref: str, scale_mm_per_px: float, valid_until: str | None = None) -> dict[str, Any]:
    conn = get_connection()
    conn.execute("UPDATE metro_calibration SET is_current=0")
    conn.execute(
        "INSERT INTO metro_calibration(ref,scale_mm_per_px,valid_until,is_current,created_at) VALUES (?,?,?,1,?)"
        " ON CONFLICT(ref) DO UPDATE SET scale_mm_per_px=excluded.scale_mm_per_px,"
        " valid_until=excluded.valid_until, is_current=1, created_at=excluded.created_at",
        (ref, scale_mm_per_px, valid_until, _now()))
    _event("CALIBRATION_DONE", None, summary=f"calibração {ref}: {scale_mm_per_px:.5f} mm/px",
           payload={"calibration_ref": ref, "scale_mm_per_px": scale_mm_per_px, "valid_until": valid_until})
    return current_calibration() or {}


def current_calibration() -> dict[str, Any] | None:
    r = get_connection().execute(
        "SELECT * FROM metro_calibration WHERE is_current=1 ORDER BY created_at DESC LIMIT 1").fetchone()
    if not r:
        return None
    d = dict(r)
    d["valid"] = (not d.get("valid_until")) or (d["valid_until"] >= _now()[:10])
    return d


def calibrate_from_reference(ref: str, p1: list[float], p2: list[float], known_mm: float,
                             frame_w: int, frame_h: int, valid_until: str | None = None) -> dict[str, Any]:
    """Calibra a partir de um objeto de comprimento conhecido medido na imagem."""
    px = _px_dist(p1, p2, frame_w, frame_h)
    if px <= 0 or known_mm <= 0:
        return {"ok": False, "message": "referência inválida"}
    return {"ok": True, **set_calibration(ref, known_mm / px, valid_until)}


# ── Medição ──────────────────────────────────────────────────────────
def _px_dist(p1: list[float], p2: list[float], w: int, h: int) -> float:
    """Distância em pixels entre dois pontos normalizados [0,1]."""
    return math.hypot((p2[0] - p1[0]) * w, (p2[1] - p1[1]) * h)


def _angle(p1: list[float], vertex: list[float], p2: list[float]) -> float:
    a = math.atan2(p1[1] - vertex[1], p1[0] - vertex[0])
    b = math.atan2(p2[1] - vertex[1], p2[0] - vertex[0])
    d = abs(math.degrees(a - b)) % 360
    return round(d if d <= 180 else 360 - d, 2)


def measure(*, kind: str, points: list[list[float]], frame_w: int, frame_h: int,
            feature: str, nominal: float, tol_lo: float, tol_hi: float,
            op_tag: str | None = None, unit: str = "mm") -> dict[str, Any]:
    cal = current_calibration()
    if kind == "angle":
        if len(points) < 3:
            return {"ok": False, "message": "ângulo precisa de 3 pontos (p1, vértice, p2)"}
        measured = _angle(points[0], points[1], points[2]); unit = "°"
        px = None
    else:  # linear | diameter
        if len(points) < 2:
            return {"ok": False, "message": "medida precisa de 2 pontos"}
        px = _px_dist(points[0], points[1], frame_w, frame_h)
        if not cal:
            return {"ok": False, "message": "sem calibração — defina a escala px→mm primeiro", "px": round(px, 1)}
        measured = round(px * cal["scale_mm_per_px"], 3)

    dev = round(measured - nominal, 3)
    conforme = tol_lo <= dev <= tol_hi
    verdict = "CONFORME" if conforme else "NAO_CONFORME"
    # incerteza: ~1 px convertido (linear) ou 0.2° (ângulo) — repetibilidade simplificada
    uncertainty = round((cal["scale_mm_per_px"] if (cal and kind != "angle") else 0.2), 3)
    cal_ref = cal["ref"] if cal else None
    cal_valid = bool(cal and cal.get("valid"))

    get_connection().execute(
        "INSERT INTO metro_measurement(op_tag,feature,kind,measured,nominal,tol_lo,tol_hi,uncertainty,verdict,calibration_ref,event_ts)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (op_tag, feature, kind, measured, nominal, tol_lo, tol_hi, uncertainty, verdict, cal_ref, _now()))

    _event("MEASUREMENT_TAKEN", op_tag, summary=f"{feature}: {measured}{unit} (nom {nominal}{unit})",
           payload={"feature": feature, "measured": measured, "nominal": nominal,
                    "tol": [tol_lo, tol_hi], "uncertainty": uncertainty, "calibration_ref": cal_ref})
    if conforme:
        _event("MEASUREMENT_APPROVED", op_tag, severity="ok",
               summary=f"{feature} CONFORME: {measured}{unit} (desvio {dev})",
               payload={"feature": feature, "measured": measured})
    else:
        _event("MEASUREMENT_REJECTED", op_tag, severity="nok",
               summary=f"{feature} NÃO CONFORME: {measured}{unit} (desvio {dev}, tol {tol_lo}..{tol_hi})",
               payload={"feature": feature, "measured": measured, "nominal": nominal, "tol": [tol_lo, tol_hi]})
        _occurrence(op_tag, f"Reprovação dimensional: {feature} = {measured}{unit} (tol {tol_lo}..{tol_hi})")

    return {
        "ok": True, "feature": feature, "kind": kind, "measured": measured, "unit": unit,
        "nominal": nominal, "tol": [tol_lo, tol_hi], "deviation": dev, "verdict": verdict,
        "uncertainty": uncertainty, "px": round(px, 1) if px is not None else None,
        "calibration_ref": cal_ref, "calibration_valid": cal_valid,
    }


def kpis() -> dict[str, Any]:
    conn = get_connection()

    def one(sql: str, *p: Any) -> Any:
        r = conn.execute(sql, p).fetchone()
        return list(dict(r).values())[0] if r else 0
    total = int(one("SELECT COUNT(*) FROM metro_measurement") or 0)
    ok = int(one("SELECT COUNT(*) FROM metro_measurement WHERE verdict='CONFORME'") or 0)
    unc = one("SELECT AVG(uncertainty) FROM metro_measurement")
    # Cpk por feature (precisa de variação)
    cpks: dict[str, float] = {}
    for r in conn.execute("SELECT DISTINCT feature FROM metro_measurement").fetchall():
        f = dict(r)["feature"]
        rows = [dict(x) for x in conn.execute(
            "SELECT measured,nominal,tol_lo,tol_hi FROM metro_measurement WHERE feature=? ORDER BY event_ts DESC LIMIT 50", (f,)).fetchall()]
        vals = [x["measured"] for x in rows if x["measured"] is not None]
        if len(vals) >= 3:
            import statistics as st
            mean, sd = st.mean(vals), st.pstdev(vals)
            n = rows[0]
            usl, lsl = n["nominal"] + n["tol_hi"], n["nominal"] + n["tol_lo"]
            if sd > 1e-9:
                cpks[f] = round(min(usl - mean, mean - lsl) / (3 * sd), 2)
    cal = current_calibration()
    return {
        "measurements": total,
        "CLD_Measurement_Pass_Rate": round(100 * ok / total, 1) if total else None,
        "CLD_Cpk": cpks,
        "CLD_Measurement_Uncertainty": round(float(unc), 3) if unc else None,
        "CLD_Calibration_Validity": bool(cal and cal.get("valid")),
        "calibration": cal,
    }


def _occurrence(op_tag: str | None, note: str) -> None:
    if not op_tag:
        return
    try:
        from ..vps import store
        store.raise_occurrence(op_tag, None, "DIMENSIONAL_REJECT", "nok", note)
    except Exception:  # noqa: BLE001
        pass


def _event(action: str, op_tag: str | None, *, severity: str = "info",
           summary: str = "", payload: Any = None) -> None:
    try:
        from .. import audit
        audit.record("SYSTEM", action, severity=severity, actor="metrologia",
                     source_id=op_tag, entity_type="measurement", entity_id=op_tag,
                     correlation_id=op_tag, summary=summary, payload=payload)
    except Exception:  # noqa: BLE001
        pass
