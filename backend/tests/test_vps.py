"""Suíte do módulo VPS — trava as 9 ondas (espinha→conector ERP) contra regressão."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.db.database import init_db
from app.schemas.enums import Mode, ModelType
from app.schemas.results import InferenceResult
import asyncio

from app.db.database import get_connection
from app.vps import aps, bridge, e2e, engine, gold, labels, lgpd, modals, operators, planning, rbac, recon, scan, store, tagid, templates


@pytest.fixture(autouse=True)
def _clean():
    init_db()
    store.reset()
    store.clear_erp_docs()
    for t in ("vps_operator", "vps_resource", "vps_schedule",
              "vps_project", "vps_card", "vps_wbs", "vps_card_dep", "vps_baseline", "vps_baseline_card"):
        get_connection().execute(f"DELETE FROM {t}")
    operators._current.clear()
    aps._priority.clear()
    bridge._bound.clear()
    bridge._last_verif.clear()
    bridge._segment_override = None
    bridge._auto_override = None
    lgpd._blur_override = None
    yield


def _ago(h: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=h)).isoformat()


def _cap(tag: str, action: str, ts: str | None = None, **kw):
    return engine.capture({"tag_id": tag, "action": action, "event_ts": ts or store.now_iso(), **kw})


def _res(mode: Mode, result: dict, conf: float = 0.99, source: str = "cam:x") -> InferenceResult:
    return InferenceResult(detection_id="d", source_id=source, mode=mode, model_name="m", model_version="1",
                           model_type=ModelType.EDGE, timestamp=store.now_iso(), confidence=conf,
                           result=result, pipeline="edge", latency_ms=5)


# ── Onda 1 — Tag-ID + máquina de estados + linhagem ──────────────────
def test_tagid_parse_build():
    t = tagid.build("PANEL", "OP", "OP-2026-1")
    assert t == "VPS:PANEL:OP:OP-2026-1:01"
    p = tagid.parse(t)
    assert p and p.segment == "PANEL" and p.entity_type == "OP" and p.natural_key == "OP-2026-1"
    assert tagid.parse("garbage") is None


def test_genesis_and_phase_advance():
    op = tagid.build("PANEL", "OP", "OP-T1")
    out = _cap(op, "OP_OPENED")
    assert out["state"] == "IN_PROCESS"
    t = store.get_tag(op)
    assert t["template_id"] == "PANEL_ETO_V1" and t["current_phase"] == "ENGINEERING"
    _cap(op, "DRAWINGS_APPROVED")
    assert store.get_tag(op)["current_phase"] == "PURCHASING"


def test_blocking_pending_and_clear():
    op = tagid.build("PANEL", "OP", "OP-T2")
    for a in ("OP_OPENED", "DRAWINGS_APPROVED", "SUPPLY_LINKED", "PICK_SHORT"):
        _cap(op, a)
    t = store.get_tag(op)
    assert t["state"] == "EXCEPTION" and t["current_phase"] == "PICKING"
    assert store.open_pending_count(op) == 1
    pend = store.pendings_for(op)[0]
    res = engine.clear_pending(pend["pending_id"])
    assert res["state"] == "IN_PROCESS" and store.open_pending_count(op) == 0


def test_lineage():
    so, op = tagid.build("PANEL", "SO", "SO-1"), tagid.build("PANEL", "OP", "OP-L1")
    _cap(so, "SO_CREATED")
    _cap(op, "OP_OPENED", parent_tag_id=so)
    th = engine.thread(op)
    assert any(p["parent_tag_id"] == so for p in th["lineage"]["parents"])


def test_low_confidence_occurrence():
    op = tagid.build("PANEL", "OP", "OP-LC")
    for a in ("OP_OPENED", "DRAWINGS_APPROVED", "SUPPLY_LINKED"):
        _cap(op, a)
    _cap(op, "PICK_COMPLETED", vision_mode="CONTAR", confidence=0.5)  # PICKING min 0.95
    assert any(o["kind"] == "LOW_CONFIDENCE" for o in store.occurrences_for(op))


# ── Onda 3 — Ponte Visão→VPS ─────────────────────────────────────────
def test_bridge_genesis_and_vision_nok():
    bridge.set_segment("PANEL")
    bridge.on_inference(_res(Mode.LER, {"leituras": [{"texto": "etiqueta OP-2026-9000"}]}))
    tag = bridge.bindings()["cam:x"]
    assert tag == "VPS:PANEL:OP:OP-2026-9000:01"
    bridge._last_verif.clear()
    bridge.on_inference(_res(Mode.ANALISAR, {"veredito": "NOK", "resumo": "solda"}, conf=0.9))
    assert any(o["kind"] == "VISION_NOK" for o in store.occurrences_for(tag))


# ── Onda 4/8 — Templates por entity_type / segmento ──────────────────
def test_template_resolution():
    assert templates.resolve_template("PANEL", "OP") == "PANEL_ETO_V1"
    assert templates.resolve_template("PANEL", "SO") == "SO_OTC_V1"
    assert templates.resolve_template("PHARMA", "OP") == "PHARMA_V1"
    assert templates.resolve_template("FOOD", "OP") == "FOOD_V1"
    assert templates.resolve_template("UNKNOWN", "OP") == "GENERIC_V1"


def test_board_lanes():
    _cap(tagid.build("PANEL", "OP", "OP-B1"), "OP_OPENED")
    _cap(tagid.build("PANEL", "SO", "SO-B1"), "SO_CREATED")
    b = engine.board(entity="OP")
    assert b["cards"] and all(c["entity_type"] == "OP" for c in b["cards"])
    assert "DONE" in b["columns"]


# ── Onda 5 — Preditivo + governança ──────────────────────────────────
def test_risk_late():
    op = tagid.build("PANEL", "OP", "OP-RK")
    _cap(op, "OP_OPENED", _ago(30))
    _cap(op, "DRAWINGS_APPROVED", _ago(29))
    _cap(op, "SUPPLY_LINKED", _ago(20))  # → PICKING (sla 8), última atividade há 20h
    card = next(c for c in engine.board(entity="OP")["cards"] if c["natural_key"] == "OP-RK")
    assert card["risk"] == "late" and card["eta_breach_h"] < 0


def test_kpis_otif_and_cost():
    op = tagid.build("PANEL", "OP", "OP-K1")
    seq = [("OP_OPENED", 10), ("DRAWINGS_APPROVED", 9), ("SUPPLY_LINKED", 8), ("PICK_COMPLETED", 7),
           ("OP_OPERATION_DONE", 6), ("MEASUREMENT_APPROVED", 5), ("SHIPPED", 4), ("INVOICE_ISSUED", 3)]
    for a, h in seq:
        _cap(op, a, _ago(h))
    op2 = tagid.build("PANEL", "OP", "OP-K2")
    for a, h in (("OP_OPENED", 30), ("DRAWINGS_APPROVED", 29), ("SUPPLY_LINKED", 28), ("PICK_SHORT", 20)):
        _cap(op2, a, _ago(h))
    k = engine.kpis()
    assert k["CLD_OTIF"] == 100.0
    assert k["CLD_Completed_Threads"] >= 1
    assert k["CLD_Cost_of_Pendencies"] >= 900   # ~20h × R$50


def test_correct_compensation_event():
    op = tagid.build("PANEL", "OP", "OP-CC")
    _cap(op, "OP_OPENED")
    engine.correct(op, "ajuste pós-auditoria")
    assert any(e["action"] == "COMPENSATION" for e in store.events_for(op))


# ── Onda 6 — WS delta + LGPD + RBAC ──────────────────────────────────
def test_event_delta():
    before = store.max_event_rowid()
    op = tagid.build("PANEL", "OP", "OP-WS")
    _cap(op, "OP_OPENED")
    assert any(e["action"] == "OP_OPENED" for e in store.events_after(before))


def test_lgpd_blur_off_is_noop():
    assert lgpd.blur_enabled() is False
    data = b"not-a-real-jpeg"
    assert lgpd.anonymize(data) == data


def test_rbac_permissions():
    assert rbac.can("Admin", "Operations")
    assert rbac.can("Operations", "Operations")
    assert not rbac.can("Sales", "Operations")
    assert not rbac.can("Viewer", "Operations")
    op = tagid.build("PANEL", "OP", "OP-RB")
    _cap(op, "OP_OPENED")
    assert rbac.owner_of_tag(op) == "Operations"
    with pytest.raises(HTTPException):
        rbac.require("Sales", op)
    rbac.require("Operations", op)  # não levanta


# ── Onda 7 — Gold / BI ───────────────────────────────────────────────
def test_gold_fact_phase_and_csv():
    op = tagid.build("PANEL", "OP", "OP-G1")
    _cap(op, "OP_OPENED", _ago(50))
    _cap(op, "DRAWINGS_APPROVED", _ago(40))    # sai de ENGINEERING
    _cap(op, "SUPPLY_LINKED", _ago(35))        # 1º evento de PURCHASING → fecha ENGINEERING (15h ≤ 24)
    eng = next(r for r in gold.fact_phase() if r["tag_id"] == op and r["phase"] == "ENGINEERING")
    assert eng["duration_h"] == 15.0 and eng["adherent"] is True
    assert "tag_id" in gold.to_csv(gold.dim_tag()).splitlines()[0]


# ── Onda 9 — Conector ERP/MES (CSV) + reconciliação ──────────────────
def test_recon_csv_parse_and_divergence():
    rows = recon.parse_csv("natural_key;doc;qty\nOP-R1;ERP-1;12")   # delimitador ; + alias
    assert rows[0]["qty"] == 12 and rows[0]["natural_key"] == "OP-R1"

    op = tagid.build("PANEL", "OP", "OP-R1")
    for a in ("OP_OPENED", "DRAWINGS_APPROVED", "SUPPLY_LINKED"):
        _cap(op, a)
    _cap(op, "PICK_COMPLETED", vision_mode="CONTAR", confidence=0.97, payload={"total": 10})
    recon.load_docs(rows)
    r = recon.reconcile()
    assert r["divergent"] >= 1
    assert any(e["recon_status"] == "DIVERGENT" for e in store.events_for(op))
    assert store.erp_docs() and store.get_erp_doc("OP-R1")["qty"] == 12


# ── Gerador de Tags — Tag-ID canônico + QR + deep link ───────────────
def test_label_generate_qr_and_deeplink():
    g = labels.generate({"segment": "PANEL", "entity_type": "OP", "natural_key": "OP-2026-04412",
                         "instance": "01", "encode": "TAGID"})
    assert g["tag_id"] == "VPS:PANEL:OP:OP-2026-04412:01"
    assert g["qr_payload"] == g["tag_id"]
    assert g["print_batch"].startswith("IMP-")
    assert g["qr_svg"] and g["qr_svg"].lstrip().startswith("<svg")  # segno instalado

    dl = labels.generate({"segment": "PANEL", "entity_type": "OP", "natural_key": "X", "encode": "DEEPLINK"})
    assert dl["qr_payload"].endswith("VPS:PANEL:OP:X:01")
    assert dl["qr_payload"].startswith("https://")


# ── Operadores — cadastro + identificação na captura ─────────────────
def test_operators_crud_and_identify():
    operators.upsert_operator({"operator_id": "u1", "name": "A", "badge": "B-1", "role": "Operador"})
    assert any(o["operator_id"] == "u1" for o in operators.list_operators())
    assert operators.identify("ST-1", badge="B-1")["operator_id"] == "u1"
    assert operators.current("ST-1") == "u1"
    operators.set_status("u1", "inativo")
    assert operators.get_operator("u1")["status"] == "inativo"
    assert operators.identify("ST-2", badge="B-1")["operator_id"] is None   # inativo não loga


# ── APS — scheduling de capacidade finita + realimentação ────────────
def test_aps_finite_capacity_schedule():
    for k in ("OP-A1", "OP-A2"):
        op = tagid.build("PANEL", "OP", k)
        _cap(op, "OP_OPENED")
        _cap(op, "DRAWINGS_APPROVED")
    out = aps.generate("base", "prioridade")
    assert out["operations"] > 0
    rows = store.schedule("base")
    by: dict[str, list] = {}
    for r in rows:
        by.setdefault(r["resource_key"], []).append(r)
    for ops in by.values():                                 # capacidade finita: sem sobreposição no recurso
        ops.sort(key=lambda x: x["planned_start"])
        for a, b in zip(ops, ops[1:]):
            assert a["planned_end"] <= b["planned_start"]
    assert aps.kpis("base")["CLD_Operations"] == len(rows)


def test_aps_features():
    for k in ("OP-X1", "OP-X2"):
        op = tagid.build("PANEL", "OP", k)
        _cap(op, "OP_OPENED"); _cap(op, "DRAWINGS_APPROVED")
    store.upsert_resource({"resource_key": "res_pk", "name": "PK", "capacity": 2, "skills": "picking"})
    aps.generate("base", "prioridade")
    rows = store.schedule("base")
    assert {r["resource_key"] for r in rows if r["operation"] == "PICKING"} == {"res_pk"}   # skill-aware
    assert any(d["bottleneck"] for d in aps.load("base"))                                    # gargalo
    cmp = aps.compare(["prioridade", "fifo"])
    assert len(cmp) == 2 and "CLD_Makespan_h" in cmp[0]["kpis"]                              # what-if
    assert aps.ctp(12)["lead_h"] > 0                                                          # CTP
    aps.expedite(tagid.build("PANEL", "OP", "OP-X2")); aps.generate("base", "prioridade")    # expedite
    aps.publish("base")
    assert any(e["action"] == "SCHEDULE_PUBLISHED" for e in store.recent_events(9999))       # vínculo no Fio


# ── Teste ponta a ponta (roteiro real) ───────────────────────────────
def test_e2e_run_passes():
    r = e2e.run()
    assert r["passed"] is True
    assert len(r["steps"]) == 22
    assert all(s["ok"] for s in r["steps"])
    assert r["acceptance"]["lineage_9"] and r["acceptance"]["compensation"] and r["acceptance"]["archived"]
    assert r["kpis"]["estado_final"] == "ARCHIVED"


# ── Scanner de token (QR → registro) ─────────────────────────────────
def test_scan_decodes_qr_and_registers():
    import base64
    import io

    import segno  # type: ignore
    op = tagid.build("PANEL", "OP", "OP-SCAN-1")
    _cap(op, "OP_OPENED")
    buf = io.BytesIO(); segno.make(op, error="q").save(buf, kind="png", scale=8, border=2)
    b64 = base64.b64encode(buf.getvalue()).decode()
    r = asyncio.run(scan.scan("ALMOX-02", "u123", b64, None, None))   # RESOLVE (não grava)
    assert r["ok"] and r["resolved"] and r["tag_id"] == op and r["actions"]
    n0 = len(store.events_for(op))
    out = asyncio.run(scan.apply(op, r["actions"][0]["action"], "ALMOX-02", "u123", None))  # APLICA a ação
    assert out["ok"] and out["operator_id"] == "u123"
    assert len(store.events_for(op)) == n0 + 1


# ── Modais & Vínculos — campos resolvidos das bases ──────────────────
def test_modal_bindings():
    op = tagid.build("PANEL", "OP", "OP-MB")
    _cap(op, "OP_OPENED", vision_mode="LER", confidence=0.99)
    m = modals.resolve(op)
    assert m is not None
    ids = {g["id"] for g in m["modais"]}
    assert {"M2", "M6", "M8"} <= ids
    m2 = next(g for g in m["modais"] if g["id"] == "M2")
    origins = {f["origin"] for f in m2["fields"]}
    assert {"TAG", "VIS", "TPL", "LIN"} <= origins   # dado vinculado a múltiplas bases


# ── Planejamento — projeto rege; card libera → Tag-ID (gênese); CPM ──
def test_planning_project_card_release():
    p = planning.create_project({"code": "PRJ-T1", "name": "Teste", "segment": "PANEL"})
    pid = p["project_id"]
    assert store.get_tag(p["tag_id"])                       # projeto vira nó PROJ na espinha
    c1 = planning.add_card(pid, {"code": "C1", "title": "a", "planned_effort": 8, "resource_key": "r1"})
    c2 = planning.add_card(pid, {"code": "C2", "title": "b", "planned_effort": 16, "resource_key": "r1"})
    planning.add_dependency(pid, c1["card_id"], c2["card_id"], "FS")
    sch = planning.schedule(pid)
    assert sch["ok"] and sch["scheduled"] == 2
    assert planning.critical_path(pid)["makespan_h"] >= 24   # 8+16 em série (FS)
    rc = planning.release_card(c1["card_id"])               # gênese
    assert rc["tag_id"] and store.get_tag(rc["tag_id"])
    assert any(ch["child_tag_id"] == rc["tag_id"] for ch in store.children_of(p["tag_id"]))  # PROJ→OP
    assert planning.set_baseline(pid)["version"] == 1
