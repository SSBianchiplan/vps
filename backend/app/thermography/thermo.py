"""Manutenção preditiva por termografia (VisionDesk_Manutencao_Preditiva_Termografia).

Térmico → hotspot → ΔT vs baseline → tendência → predição → evento (ocorrência + APS).
É o modo ANALISAR no espectro térmico (VPS_06).

Captura: o ideal é FLIR radiométrico (temperatura por pixel). Sem hardware FLIR,
fazemos **pseudo-radiometria**: luminância → °C numa faixa [t_min, t_max] calibrável
por ativo. A interface (leitura/baseline/tendência/evento) é a mesma — trocar a
fonte por um frame radiométrico real preserva todo o pipeline.

Disciplina de dados (igual ao tracking): eventos semânticos no Event Store (trilha);
série radiométrica em `thermal_reading` (analítico → baseline/tendência).
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import Any

import numpy as np

from ..db.database import get_connection

_ALGO = "thermo-pseudo-v1"
_SEV_ORDER = {"NORMAL": 0, "OBSERVAR": 1, "AGIR": 2, "CRITICO": 3}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def available() -> bool:
    try:
        import cv2  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


# ── Ativos (config + baseline) ───────────────────────────────────────
def upsert_asset(asset_id: str, name: str | None = None, **kw: Any) -> dict[str, Any]:
    a = get_asset(asset_id) or {}
    rec = {
        "name": name or a.get("name") or asset_id,
        "emissivity": kw.get("emissivity", a.get("emissivity", 0.95)),
        "t_min": kw.get("t_min", a.get("t_min", 20)),
        "t_max": kw.get("t_max", a.get("t_max", 120)),
        "t_abs_limit": kw.get("t_abs_limit", a.get("t_abs_limit", 75)),
        "delta_t_limit": kw.get("delta_t_limit", a.get("delta_t_limit", 15)),
        "tag_id": kw.get("tag_id", a.get("tag_id")),
    }
    get_connection().execute(
        "INSERT INTO thermal_asset(asset_id,name,emissivity,t_min,t_max,t_abs_limit,delta_t_limit,tag_id,created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?)"
        " ON CONFLICT(asset_id) DO UPDATE SET name=excluded.name, emissivity=excluded.emissivity,"
        " t_min=excluded.t_min, t_max=excluded.t_max, t_abs_limit=excluded.t_abs_limit,"
        " delta_t_limit=excluded.delta_t_limit, tag_id=excluded.tag_id",
        (asset_id, rec["name"], rec["emissivity"], rec["t_min"], rec["t_max"],
         rec["t_abs_limit"], rec["delta_t_limit"], rec["tag_id"], _now()))
    return get_asset(asset_id)  # type: ignore[return-value]


def get_asset(asset_id: str) -> dict[str, Any] | None:
    r = get_connection().execute("SELECT * FROM thermal_asset WHERE asset_id=?", (asset_id,)).fetchone()
    return dict(r) if r else None


def list_assets() -> list[dict[str, Any]]:
    return [dict(r) for r in get_connection().execute(
        "SELECT * FROM thermal_asset ORDER BY created_at DESC").fetchall()]


# ── Pseudo-radiometria ───────────────────────────────────────────────
def _temp_field(image_b64: str, t_min: float, t_max: float) -> tuple[np.ndarray, bytes]:
    """Decodifica → campo de temperatura (°C por pixel) + preview com colormap térmico."""
    import cv2
    raw = base64.b64decode(image_b64)
    bgr = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)            # reduz ruído de pixel único
    temp = t_min + (gray.astype(np.float32) / 255.0) * (t_max - t_min)
    color = cv2.applyColorMap(gray, cv2.COLORMAP_INFERNO)
    ok, buf = cv2.imencode(".jpg", color)
    return temp, (buf.tobytes() if ok else b"")


def _severity(asset: dict[str, Any], t_max: float, delta_t: float, trend_c_week: float) -> str:
    lim, dlim = asset["t_abs_limit"], asset["delta_t_limit"]
    if t_max >= lim * 1.2 or delta_t >= dlim * 2:
        return "CRITICO"
    if t_max >= lim or delta_t >= dlim:
        return "AGIR"
    if delta_t >= dlim * 0.6 or trend_c_week >= 3:
        return "OBSERVAR"
    return "NORMAL"


def _trend(asset_id: str) -> float:
    """Taxa de subida de T_max (°C/semana) por regressão linear nas leituras recentes."""
    rows = get_connection().execute(
        "SELECT t_max, event_ts FROM thermal_reading WHERE asset_id=? ORDER BY event_ts DESC LIMIT 40",
        (asset_id,)).fetchall()
    pts = [dict(r) for r in rows if dict(r)["t_max"] is not None]
    if len(pts) < 3:
        return 0.0
    t0 = datetime.fromisoformat(pts[-1]["event_ts"])
    xs = np.array([(datetime.fromisoformat(p["event_ts"]) - t0).total_seconds() / 86400.0 for p in pts])  # dias
    ys = np.array([p["t_max"] for p in pts], dtype=float)
    if xs.max() - xs.min() < 1e-6:
        return 0.0
    slope = float(np.polyfit(xs, ys, 1)[0])   # °C/dia
    return round(slope * 7.0, 2)


def analyze(image_b64: str, asset_id: str) -> dict[str, Any]:
    """Mede T_max/T_avg/ΔT, severidade, tendência e emite eventos. Grava na série."""
    asset = upsert_asset(asset_id)  # garante o ativo
    temp, preview = _temp_field(image_b64, asset["t_min"], asset["t_max"])
    t_max = round(float(np.percentile(temp, 99.5)), 1)        # ignora outlier de 1 pixel
    t_avg = round(float(temp.mean()), 1)
    # hotspot: posição do ponto mais quente (suavizado)
    yx = np.unravel_index(int(np.argmax(temp)), temp.shape)
    hy, hx = round(yx[0] / temp.shape[0], 3), round(yx[1] / temp.shape[1], 3)
    baseline = asset.get("baseline_tmax")
    delta_t = round(t_max - baseline, 1) if baseline is not None else 0.0
    trend = _trend(asset_id)
    sev = _severity(asset, t_max, delta_t, trend)

    get_connection().execute(
        "INSERT INTO thermal_reading(asset_id,t_max,t_avg,delta_t,severity,hotspot_x,hotspot_y,emissivity,event_ts)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (asset_id, t_max, t_avg, delta_t, sev, hx, hy, asset["emissivity"], _now()))

    # predição: dias até atingir o limite absoluto (se aquecendo)
    lead_days = None
    if trend > 0.1 and t_max < asset["t_abs_limit"]:
        lead_days = round((asset["t_abs_limit"] - t_max) / (trend / 7.0), 1)

    _event("THERMAL_READING", asset, severity="info",
           summary=f"{asset['name']}: T_max {t_max}°C · ΔT {delta_t}°C · {sev}",
           payload={"t_max": t_max, "t_avg": t_avg, "delta_t": delta_t, "severity": sev})
    if _SEV_ORDER[sev] >= 2:
        _event("HOTSPOT_DETECTED", asset, severity="nok" if sev == "CRITICO" else "alerta",
               summary=f"HOTSPOT {sev} em {asset['name']}: {t_max}°C (lim {asset['t_abs_limit']}) ΔT {delta_t}",
               payload={"t_max": t_max, "delta_t": delta_t, "severity": sev, "baseline": baseline})
        _occurrence(asset, "THERMAL_HOTSPOT", "nok" if sev == "CRITICO" else "alerta",
                    f"Hotspot {sev}: {t_max}°C em {asset['name']} (ΔT {delta_t})")
    if lead_days is not None and trend >= 3:
        _event("TREND_ALERT", asset, severity="alerta",
               summary=f"{asset['name']}: subindo {trend}°C/sem → ~{lead_days} dia(s) até o limite",
               payload={"trend_c_per_week": trend, "lead_days": lead_days})
        _event("MAINTENANCE_RECOMMENDED", asset, severity="alerta",
               summary=f"Manutenção recomendada em {asset['name']} (janela ~{lead_days} dia(s))",
               payload={"window_days": lead_days, "trend_c_per_week": trend})

    return {
        "ok": True, "asset_id": asset_id, "name": asset["name"],
        "t_max": t_max, "t_avg": t_avg, "delta_t": delta_t, "severity": sev,
        "baseline": baseline, "trend_c_per_week": trend, "lead_days": lead_days,
        "hotspot": [hx, hy], "emissivity": asset["emissivity"],
        "t_abs_limit": asset["t_abs_limit"], "delta_t_limit": asset["delta_t_limit"],
        "thermal_b64": base64.b64encode(preview).decode() if preview else None,
        "algo": _ALGO,
    }


def set_baseline(asset_id: str, image_b64: str) -> dict[str, Any]:
    """Define a assinatura térmica saudável (datada) do ativo a partir de um frame."""
    asset = upsert_asset(asset_id)
    temp, _ = _temp_field(image_b64, asset["t_min"], asset["t_max"])
    tmax = round(float(np.percentile(temp, 99.5)), 1)
    get_connection().execute(
        "UPDATE thermal_asset SET baseline_tmax=?, baseline_ts=? WHERE asset_id=?", (tmax, _now(), asset_id))
    _event("BASELINE_SET", asset, summary=f"baseline térmica de {asset['name']}: {tmax}°C")
    return {"ok": True, "baseline_tmax": tmax}


def trend_series(asset_id: str, limit: int = 60) -> list[dict[str, Any]]:
    rows = get_connection().execute(
        "SELECT t_max, delta_t, severity, event_ts FROM thermal_reading WHERE asset_id=? ORDER BY event_ts DESC LIMIT ?",
        (asset_id, limit)).fetchall()
    return list(reversed([dict(r) for r in rows]))


def kpis() -> dict[str, Any]:
    conn = get_connection()
    assets = list_assets()
    by_sev: dict[str, int] = {}
    at_risk = 0
    leads: list[float] = []
    for a in assets:
        last = conn.execute(
            "SELECT severity, t_max FROM thermal_reading WHERE asset_id=? ORDER BY event_ts DESC LIMIT 1",
            (a["asset_id"],)).fetchone()
        sev = (dict(last)["severity"] if last else "—")
        by_sev[sev] = by_sev.get(sev, 0) + 1
        tr = _trend(a["asset_id"])
        if tr >= 3 or _SEV_ORDER.get(sev, 0) >= 2:
            at_risk += 1
    return {
        "assets": len(assets),
        "CLD_Assets_At_Risk": at_risk,
        "CLD_Hotspots_By_Severity": by_sev,
        "CLD_Predictive_Lead_Time": round(sum(leads) / len(leads), 1) if leads else None,
        "algo": _ALGO,
    }


def _occurrence(asset: dict[str, Any], kind: str, severity: str, note: str) -> None:
    """Hotspot grave vira OCORRÊNCIA VPS no Fio do ativo (VPS_07 §5), se tiver Tag-ID."""
    tag = asset.get("tag_id")
    if not tag:
        return
    try:
        from ..vps import store
        store.raise_occurrence(tag, None, kind, severity, note)
    except Exception:  # noqa: BLE001
        pass


def _event(action: str, asset: dict[str, Any], *, severity: str = "info",
           summary: str = "", payload: Any = None) -> None:
    """Evento térmico na trilha (Event Store). Ativo = entity; liga ao Tag-ID do ativo."""
    try:
        from .. import audit
        audit.record("SYSTEM", action, severity=severity, actor="termografia",
                     source_id=asset.get("tag_id"), entity_type="asset", entity_id=asset.get("asset_id"),
                     correlation_id=asset.get("tag_id"), summary=summary, payload=payload)
    except Exception:  # noqa: BLE001
        pass
