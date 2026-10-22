"""Automação Industrial — conector OT (PLC/IHM → eventos do VPS).

Conector híbrido (VisionDesk_PLC_IHM): por PROTOCOLO (OPC UA primário) onde há, por
VISÃO (caminho B) onde não há. **Observador: read-only, não intrusivo** — nunca
escreve no PLC. Cada leitura vira evento semântico normalizado, com timestamp da
FONTE, sob o Tag-ID do ativo → OEE, ocorrências, APS, reconciliação.

Sem hardware/servidor OPC UA aqui: o núcleo demonstrável é o **simulador dos 5
componentes (§14)** + KPIs/OEE. O caminho OPC UA real é best-effort (lib `asyncua`).
"""
from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any

from ..db.database import get_connection

# Ações por severidade (alarme/falha viram ocorrência VPS).
_ALARM = {"ALARM_RAISED", "IO_FAULT", "VISION_FAIL"}
_RUN_STATES = {"RUN", "EXECUTE", "AUTO"}

# 5 componentes da simulação (§14) — cada um com seu caminho de leitura.
DEMO = [
    {"asset_id": "M-301", "name": "Transportador L1 (SINAMICS)", "kind": "drive", "mode": "protocol", "protocol": "opcua"},
    {"asset_id": "RIO-L1", "name": "Remota I/O (ET 200SP)", "kind": "remote_io", "mode": "protocol", "protocol": "profinet"},
    {"asset_id": "TK-12", "name": "Nível de Tanque", "kind": "transmitter", "mode": "protocol", "protocol": "opcua"},
    {"asset_id": "INJ-07", "name": "Injetora 250t (PackML)", "kind": "machine", "mode": "protocol", "protocol": "opcua"},
    {"asset_id": "PR-22", "name": "Prensa — Comfort Panel (legado)", "kind": "legacy_hmi", "mode": "vision", "protocol": "screen"},
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def available_opcua() -> bool:
    import importlib.util
    return importlib.util.find_spec("asyncua") is not None


# ── Ativos ───────────────────────────────────────────────────────────
def upsert_asset(a: dict[str, Any]) -> dict[str, Any]:
    oid = a["asset_id"]
    tag = a.get("tag_id") or f"VPS:PLANT:ASSET:{oid}:01"
    get_connection().execute(
        "INSERT INTO ot_asset(asset_id,name,kind,mode,protocol,endpoint,tag_id,created_at) VALUES (?,?,?,?,?,?,?,?)"
        " ON CONFLICT(asset_id) DO UPDATE SET name=excluded.name, kind=excluded.kind, mode=excluded.mode,"
        " protocol=excluded.protocol, endpoint=excluded.endpoint, tag_id=excluded.tag_id",
        (oid, a.get("name", oid), a.get("kind"), a.get("mode", "protocol"), a.get("protocol"),
         a.get("endpoint"), tag, _now()))
    return get_asset(oid)  # type: ignore[return-value]


def get_asset(oid: str) -> dict[str, Any] | None:
    r = get_connection().execute("SELECT * FROM ot_asset WHERE asset_id=?", (oid,)).fetchone()
    return dict(r) if r else None


def list_assets() -> list[dict[str, Any]]:
    return [dict(r) for r in get_connection().execute("SELECT * FROM ot_asset ORDER BY asset_id").fetchall()]


def _last(asset_id: str, action: str) -> float | None:
    r = get_connection().execute(
        "SELECT value FROM ot_reading WHERE asset_id=? AND action=? ORDER BY id DESC LIMIT 1",
        (asset_id, action)).fetchone()
    try:
        return float(dict(r)["value"]) if r else None
    except (TypeError, ValueError):
        return None


# ── Emissão de evento (leitura → semântico + ocorrência) ─────────────
def _emit(asset: dict[str, Any], action: str, value: Any, *, tag: str | None = None, code: int | None = None,
          quality: str = "Good", source: str = "PLC", note: str | None = None) -> dict[str, Any]:
    sts = _now()
    get_connection().execute(
        "INSERT INTO ot_reading(asset_id,action,tag,value,code,quality,source,source_ts,event_ts)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (asset["asset_id"], action, tag, str(value), code, quality, source, sts, sts))
    sev = "nok" if action in _ALARM else "info"
    try:
        from .. import audit
        audit.record("SYSTEM", action, severity=sev, actor="plc", source_id=asset.get("tag_id"),
                     entity_type="asset", entity_id=asset["asset_id"], correlation_id=asset.get("tag_id"),
                     summary=note or f"{asset['name']}: {action} = {value}",
                     payload={"tag": tag, "value": value, "code": code, "quality": quality,
                              "protocol": asset.get("protocol"), "source": source, "source_ts": sts})
    except Exception:  # noqa: BLE001
        pass
    if action in _ALARM and asset.get("tag_id"):   # alarme/falha → ocorrência no Fio do ativo
        try:
            from ..vps import store
            store.raise_occurrence(asset["tag_id"], None, action, "nok", note or f"{action}: {value}")
        except Exception:  # noqa: BLE001
            pass
    return {"asset_id": asset["asset_id"], "action": action, "value": value, "source": source, "source_ts": sts}


# ── Simulação dos 5 componentes (§14) ────────────────────────────────
def simulate(asset_id: str | None = None) -> dict[str, Any]:
    targets = [a for a in DEMO if (not asset_id or a["asset_id"] == asset_id)]
    events: list[dict[str, Any]] = []
    for d in targets:
        a = upsert_asset(d)
        k = d["kind"]
        if k == "drive":                                   # SINAMICS: estado + velocidade/corrente
            fault = random.random() < 0.08
            st = "FAULT" if fault else "RUN"
            events.append(_emit(a, "MACHINE_STATE", st, tag="ns=2;s=Drive.StateWord", code=412 if fault else 0))
            events.append(_emit(a, "PROCESS_VALUE_READ", round(random.uniform(47.5, 50.2), 1), tag="ns=2;s=Drive.SpeedActual"))
            if fault:
                events.append(_emit(a, "ALARM_RAISED", "F30002 sobrecorrente", tag="ns=2;s=Drive.Fault", code=412, note="SINAMICS M-301 em FALHA"))
        elif k == "remote_io":                             # ET 200SP: I/O + diagnóstico PROFINET
            events.append(_emit(a, "IO_STATE", "8DI=0b10110101 8DO=0b01000110", tag="PNIO:RIO-L1"))
            if random.random() < 0.25:
                events.append(_emit(a, "IO_FAULT", "Módulo 3 4AI · canal 2 fio rompido", code=0x8000, note="Falha de canal PROFINET (ET 200SP)"))
        elif k == "transmitter":                           # nível: analógico escalado + StatusCode + HH
            lvl = round(min(99.0, (_last(a["asset_id"], "PROCESS_VALUE_READ") or 70.0) + random.uniform(-1.5, 3.0)), 1)
            events.append(_emit(a, "PROCESS_VALUE_READ", lvl, tag="ns=2;s=TK12.Level", quality="Good"))
            if lvl >= 90:
                events.append(_emit(a, "ALARM_RAISED", f"Nível HH {lvl}% (SP 90%)", tag="ns=2;s=TK12.HH", note="Nível alto-alto TK-12"))
        elif k == "machine":                               # PackML: estado + contador + ciclo
            cnt = int(_last(a["asset_id"], "COUNTER_READ") or 4400) + random.randint(1, 6)
            events.append(_emit(a, "MACHINE_STATE", "EXECUTE", tag="ns=2;s=PackML.State"))
            events.append(_emit(a, "COUNTER_READ", cnt, tag="ns=2;s=Prod.Counter"))
            events.append(_emit(a, "CYCLE_COMPLETED", round(random.uniform(27.5, 29.5), 1), tag="ns=2;s=Cycle.Time"))
        elif k == "legacy_hmi":                             # caminho B (visão): OCR da tela
            cnt = int(_last(a["asset_id"], "COUNTER_READ") or 18230) + random.randint(1, 4)
            events.append(_emit(a, "MACHINE_STATE", "AUTO", tag="OCR:status", source="SCREEN"))
            events.append(_emit(a, "COUNTER_READ", cnt, tag="OCR:ciclos", source="SCREEN"))
            events.append(_emit(a, "PROCESS_VALUE_READ", round(random.uniform(158, 166), 0), tag="OCR:pressao_bar", source="SCREEN"))
    return {"ok": True, "events": events, "count": len(events)}


def _last_ack(asset_id: str) -> str:
    r = get_connection().execute(
        "SELECT event_ts FROM ot_reading WHERE asset_id=? AND action='ALARM_ACK' ORDER BY id DESC LIMIT 1",
        (asset_id,)).fetchone()
    return dict(r)["event_ts"] if r else ""


def alarms(limit: int = 40) -> list[dict[str, Any]]:
    """Alarmes/falhas recentes; active=True se ainda não reconhecidos (sem ACK posterior)."""
    rows = [dict(r) for r in get_connection().execute(
        "SELECT asset_id,action,value,code,source,source_ts,event_ts FROM ot_reading "
        "WHERE action IN ('ALARM_RAISED','IO_FAULT') ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]
    ack: dict[str, str] = {}
    for a in rows:
        if a["asset_id"] not in ack:
            ack[a["asset_id"]] = _last_ack(a["asset_id"])
        a["active"] = a["event_ts"] > ack[a["asset_id"]]
    return rows


def ack(asset_id: str, by: str | None = None) -> dict[str, Any]:
    """Reconhece alarmes do ativo (supervisório — NÃO escreve no PLC)."""
    a = get_asset(asset_id) or {"asset_id": asset_id, "name": asset_id, "tag_id": None}
    sts = _now()
    get_connection().execute(
        "INSERT INTO ot_reading(asset_id,action,value,source,source_ts,event_ts) VALUES (?,?,?,?,?,?)",
        (asset_id, "ALARM_ACK", by or "supervisor", "SYS", sts, sts))
    try:
        from .. import audit
        audit.record("SYSTEM", "ALARM_ACK", actor=by or "supervisor", source_id=a.get("tag_id"),
                     entity_type="asset", entity_id=asset_id, summary=f"alarmes reconhecidos: {a.get('name', asset_id)}")
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True}


# ── Caminho B: sistema de visão (CV) integrado ao OT ─────────────────
_VISION_DEFECTS = ["rebarba", "falha de injeção", "mancha", "fora de dimensional", "bolha de ar", "risco superficial"]


def vision_inspect(asset_id: str | None = None) -> dict[str, Any]:
    """Inspeção de qualidade por visão computacional → evento OT (source=VISION).
    PASS/FAIL com confiança; FAIL emite VISION_FAIL (vira alarme + ocorrência VPS)."""
    aid = asset_id or "PR-22"
    seed = next((d for d in DEMO if d["asset_id"] == aid), {"asset_id": aid, "name": aid, "kind": "vision", "mode": "vision"})
    a = upsert_asset(seed)
    fail = random.random() < 0.22
    conf = round(random.uniform(0.71, 0.99), 2)
    defect = None
    events: list[dict[str, Any]] = []
    if fail:
        defect = random.choice(_VISION_DEFECTS)
        events.append(_emit(a, "VISION_INSPECTION", "FAIL", tag="CV:inspect", quality="Bad", code=1, source="VISION",
                            note=f"Visão: peça REPROVADA — '{defect}' (conf {conf})"))
        events.append(_emit(a, "VISION_FAIL", f"{defect} (conf {conf})", tag="CV:defect", source="VISION",
                            note=f"Reprovado por visão: {defect}"))
    else:
        events.append(_emit(a, "VISION_INSPECTION", "PASS", tag="CV:inspect", source="VISION",
                            note=f"Visão: aprovado (conf {conf})"))
    return {"ok": True, "asset_id": aid, "result": "FAIL" if fail else "PASS",
            "confidence": conf, "defect": defect, "events": events}


# ── Gerador de etiqueta QR (rastreabilidade de alarme / ordem de serviço) ──
def qr_svg(payload: str, scale: int = 4) -> str:
    import io
    import segno
    qr = segno.make(payload, error="m")
    buf = io.BytesIO()
    qr.save(buf, kind="svg", scale=scale, border=2, dark="#0b1220", light="#ffffff", xmldecl=False)
    return buf.getvalue().decode("utf-8")


def alarm_qr(asset_id: str | None = None) -> dict[str, Any]:
    """Etiqueta QR de rastreabilidade do alarme: gera OS e codifica asset/tipo/valor/ts."""
    al = [x for x in alarms() if (not asset_id or x["asset_id"] == asset_id)]
    cur = next((x for x in al if x["active"]), al[0] if al else None)
    asset = asset_id or (cur["asset_id"] if cur else "—")
    ts = cur["source_ts"] if cur else _now()
    action = cur["action"] if cur else "SEM_ALARME"
    value = cur["value"] if cur else "—"
    digits = "".join(c for c in ts if c.isdigit())[-6:] or "000000"
    wo = f"OS-{asset.replace('-', '')}-{digits}"
    payload = f"VISIONDESK|OT-ALARME|asset={asset}|tipo={action}|valor={value}|ts={ts}|os={wo}"
    return {"asset_id": asset, "alarm": cur, "work_order": wo, "payload": payload,
            "active": bool(cur and cur["active"]), "generated_at": _now(), "svg": qr_svg(payload)}


def ack_all(by: str | None = None) -> dict[str, Any]:
    ids = {x["asset_id"] for x in alarms() if x["active"]}
    for i in ids:
        ack(i, by)
    return {"ok": True, "count": len(ids)}


def events(asset_id: str | None = None, limit: int = 80) -> list[dict[str, Any]]:
    sql = "SELECT asset_id,action,tag,value,code,quality,source,source_ts FROM ot_reading"
    p: list[Any] = []
    if asset_id:
        sql += " WHERE asset_id=?"; p.append(asset_id)
    sql += " ORDER BY id DESC LIMIT ?"; p.append(limit)
    return [dict(r) for r in get_connection().execute(sql, p).fetchall()]


# ── OEE / KPIs (CLD_) ────────────────────────────────────────────────
def kpis() -> dict[str, Any]:
    conn = get_connection()

    def col(sql: str, *p: Any) -> list[Any]:
        return [list(dict(r).values()) for r in conn.execute(sql, p).fetchall()]
    states = col("SELECT value FROM ot_reading WHERE action='MACHINE_STATE'")
    total = len(states) or 1
    run = sum(1 for s in states if s[0] in _RUN_STATES)
    availability = round(100 * run / total, 1)
    # contagem de produção: soma do último contador por ativo
    prod = 0
    for (aid,) in col("SELECT DISTINCT asset_id FROM ot_reading WHERE action='COUNTER_READ'"):
        v = _last(aid, "COUNTER_READ")
        if v is not None:
            prod += int(v)
    cycles = [float(v[0]) for v in col("SELECT value FROM ot_reading WHERE action='CYCLE_COMPLETED'") if _isnum(v[0])]
    cycle_avg = round(sum(cycles) / len(cycles), 1) if cycles else None
    io_faults = len(col("SELECT 1 FROM ot_reading WHERE action='IO_FAULT'"))
    downtime: dict[str, int] = {}
    for s in states:
        if s[0] not in _RUN_STATES:
            downtime[s[0]] = downtime.get(s[0], 0) + 1
    perf, qual = 0.95, 0.98   # estimativas (sem tempo real de ciclo/refugo)
    oee = round(availability / 100 * perf * qual * 100, 1)
    return {
        "CLD_OEE": oee,
        "CLD_Machine_Availability": availability,
        "CLD_Production_Count": prod,
        "CLD_Cycle_Time_Observed": cycle_avg,
        "CLD_IO_Fault_Rate": io_faults,
        "CLD_Downtime_By_Reason": downtime,
        "CLD_Count_Reconciliation": "PLC × visão × ERP (módulo Reconciliação)",
        "samples": total if states else 0,
        "perf_est": perf, "quality_est": qual,
    }


def _isnum(x: Any) -> bool:
    try:
        float(x); return True
    except (TypeError, ValueError):
        return False


# ── Sinóptico (tela supervisória low-code) ───────────────────────────
import json as _json   # noqa: E402

_DEFAULT_WIDGETS = [
    {"id": "t1", "type": "label", "x": 24, "y": 12, "w": 300, "h": 26, "text": "SINÓPTICO — LINHA 1 (HMI)", "color": "#19C3B2"},
    {"id": "tk", "type": "tank", "x": 40, "y": 60, "w": 120, "h": 170, "label": "TK-12", "unit": "%", "asset": "TK-12", "action": "PROCESS_VALUE_READ"},
    {"id": "pp", "type": "pump", "x": 210, "y": 150, "w": 90, "h": 80, "label": "Transfer", "asset": "M-301", "action": "MACHINE_STATE"},
    {"id": "vlv", "type": "valve", "x": 340, "y": 165, "w": 70, "h": 60, "label": "V-1", "asset": "M-301", "action": "MACHINE_STATE"},
    {"id": "fan", "type": "fan", "x": 210, "y": 40, "w": 90, "h": 80, "label": "Fan", "asset": "M-301", "action": "PROCESS_VALUE_READ", "unit": "Hz"},
    {"id": "g1", "type": "gauge", "x": 440, "y": 60, "w": 70, "h": 170, "label": "Pressão", "unit": "bar", "asset": "PR-22", "action": "PROCESS_VALUE_READ", "max": 200},
    {"id": "mc", "type": "machine", "x": 40, "y": 250, "w": 160, "h": 90, "label": "Injetora INJ-07", "asset": "INJ-07", "action": "MACHINE_STATE"},
    {"id": "c1", "type": "tag", "x": 220, "y": 252, "w": 140, "h": 56, "label": "Contador", "unit": "pç", "asset": "INJ-07", "action": "COUNTER_READ", "color": "#2ecc71"},
    {"id": "l1", "type": "lamp", "x": 380, "y": 252, "w": 130, "h": 60, "label": "Remota RIO-L1", "asset": "RIO-L1", "action": "MACHINE_STATE"},
    {"id": "vz", "type": "vision", "x": 560, "y": 250, "w": 120, "h": 92, "label": "Visão PR-22", "asset": "PR-22", "action": "VISION_INSPECTION"},
    {"id": "b1", "type": "button", "x": 220, "y": 360, "w": 140, "h": 42, "label": "▶ Ler tudo", "action_kind": "simulate"},
    {"id": "b2", "type": "button", "x": 372, "y": 360, "w": 138, "h": 42, "label": "Reconhecer", "action_kind": "ackAll"},
    {"id": "b3", "type": "button", "x": 524, "y": 360, "w": 156, "h": 42, "label": "👁 Inspeção visão", "action_kind": "vision", "asset": "PR-22"},
]

# Linhas do diagrama (P&ID) com campos obrigatórios do processo preenchidos.
_DEFAULT_LINKS = [
    {"id": "e1", "from": "tk", "to": "pp", "kind": "process", "animated": True, "tag": "LN-1001", "direction": "uni", "priority": "alta", "medium": "água", "diameter": "DN80"},
    {"id": "e2", "from": "pp", "to": "vlv", "kind": "process", "animated": True, "tag": "LN-1002", "direction": "uni", "priority": "normal", "medium": "água", "diameter": "DN80"},
    {"id": "e3", "from": "vlv", "to": "g1", "kind": "process", "animated": True, "tag": "LN-1003", "direction": "uni", "priority": "alta", "medium": "água", "diameter": "DN50"},
    {"id": "e4", "from": "fan", "to": "pp", "kind": "signal", "tag": "SIG-201", "direction": "uni", "priority": "normal", "signal_type": "4-20mA"},
    {"id": "e5", "from": "mc", "to": "c1", "kind": "signal", "tag": "SIG-202", "direction": "uni", "priority": "normal", "signal_type": "PROFINET"},
    {"id": "e6", "from": "l1", "to": "g1", "kind": "electric", "tag": "ELE-301", "direction": "uni", "priority": "normal", "signal_type": "Digital"},
    {"id": "e7", "from": "vz", "to": "g1", "kind": "vision", "label": "inspeção", "tag": "VIS-401", "direction": "uni", "priority": "alta", "medium": "inspeção/visão"},
]


def get_synoptic(name: str = "default") -> dict[str, Any]:
    r = get_connection().execute("SELECT json FROM ot_synoptic WHERE name=?", (name,)).fetchone()
    if r:
        try:
            d = _json.loads(dict(r)["json"])
            d.setdefault("links", [])
            return d
        except Exception:  # noqa: BLE001
            pass
    syn = {"name": name, "widgets": _DEFAULT_WIDGETS, "links": _DEFAULT_LINKS}
    save_synoptic(name, _DEFAULT_WIDGETS, _DEFAULT_LINKS)
    return syn


def save_synoptic(name: str, widgets: list[dict[str, Any]], links: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    payload = {"name": name, "widgets": widgets, "links": links or []}
    get_connection().execute(
        "INSERT INTO ot_synoptic(name,json,updated_at) VALUES (?,?,?)"
        " ON CONFLICT(name) DO UPDATE SET json=excluded.json, updated_at=excluded.updated_at",
        (name, _json.dumps(payload, ensure_ascii=False), _now()))
    return {"ok": True, "count": len(widgets), "links": len(links or [])}
