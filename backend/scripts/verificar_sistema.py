"""Verificacao operacional do VisionDesk no VPS — roda NO servidor, contra a API publica.

Cria os 4 usuarios de perfil operacional, prova o RBAC por sessao, roda o E2E
lado a lado, prova o reconhecimento facial, e passa por todas as tecnologias que
nao dependem de token. Imprime um relatorio JSON compacto no fim.
"""
import os
import base64
import json
import secrets
import sqlite3
import sys
import time
import urllib.request
import urllib.error

API = os.environ.get("VISIONDESK_API", "http://localhost:8200/api")
ADMIN_PIN = sys.argv[1]
REL: dict = {"ok": [], "falhas": [], "aguardando_token": []}


def http(method, path, body=None, token=None, timeout=240):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("X-Auth-Token", token)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except Exception:
            return e.code, {}
    except Exception as e:  # noqa: BLE001
        return 0, {"erro": str(e)[:120]}


def ok(nome, cond, detalhe=""):
    (REL["ok"] if cond else REL["falhas"]).append(f"{nome}" + (f" — {detalhe}" if detalhe else ""))
    print(("  [ok]   " if cond else "  [FALHA] ") + nome + (f" — {detalhe}" if detalhe else ""), flush=True)


def login(oid, pin):
    s, d = http("POST", "/auth/login/pin", {"operator_id": oid, "pin": pin})
    return d.get("token") if d.get("ok") else None


def b64(path):
    return base64.b64encode(open(path, "rb").read()).decode()


from ultralytics.utils import ASSETS  # noqa: E402
BUS = b64(str(ASSETS / "bus.jpg"))
ZID = b64(str(ASSETS / "zidane.jpg"))

print("\n== 1. admin")
ADM = login("op_admin_demo", ADMIN_PIN)
ok("login admin por PIN", bool(ADM))

print("\n== 2. usuarios de perfil operacional (4)")
PERFIS = [("op_operations", "Operacoes (teste)", "Operations"), ("op_supply", "Suprimentos (teste)", "Supply"),
          ("op_quality", "Qualidade (teste)", "Quality"), ("op_projects", "Projetos (teste)", "Projects")]
PINS = {}
for oid, nome, perfil in PERFIS:
    pin = "".join(secrets.choice("0123456789") for _ in range(6))
    s, d = http("POST", "/auth/users", {"name": nome, "role": "operador", "operator_id": oid, "pin": pin, "perfil": perfil}, ADM)
    if d.get("ok"):
        s2, d2 = http("POST", f"/auth/users/{oid}/perfil", {"perfil": perfil}, ADM)
        PINS[oid] = pin
    ok(f"usuario {oid} ({perfil})", d.get("ok") is True, d.get("message", ""))
s, d = http("GET", "/auth/users", None, ADM)
perf = {u["operator_id"]: u.get("perfil") for u in d.get("users", [])}
ok("perfis gravados", all(perf.get(o) == p for o, _, p in PERFIS), str({o: perf.get(o) for o, _, _ in PERFIS}))

print("\n== 3. RBAC por sessao (PLANNING / APS)")
ESPERADO = {"op_operations": (403, 200), "op_supply": (403, 403), "op_quality": (403, 403), "op_projects": (200, 200)}
TOKENS = {}
for oid, _, perfil in PERFIS:
    t = login(oid, PINS[oid]); TOKENS[oid] = t
    sp, dp = http("POST", "/vps/projects", {"code": f"RBAC-{perfil[:3].upper()}-{int(time.time()) % 10000}", "name": f"teste rbac {perfil}"}, t)
    sa, da = http("POST", "/vps/aps/schedule?scenario=rbac_teste&rule=prioridade", None, t)
    esp = ESPERADO[oid]
    ok(f"{oid}: criar projeto={sp} (esp {esp[0]}) · gerar APS={sa} (esp {esp[1]})", (sp, sa) == esp,
       (dp.get("detail") or {}).get("message", "")[:80] if sp == 403 else "")
sa, da = http("POST", "/vps/projects", {"code": "ANON", "name": "anonimo"}, None)
ok(f"anonimo sem sessao: criar projeto={sa} (esp 403)", sa == 403)

print("\n== 4. eventos de planejamento (toda mutacao vira evento)")
t = TOKENS["op_projects"]
sp, proj = http("POST", "/vps/projects", {"code": f"PLN-{int(time.time()) % 100000}", "name": "Projeto rastreado", "planned_start": "2026-09-08T08:00:00+00:00"}, t)
pid = proj.get("project_id")
sc1, c1 = http("POST", f"/vps/project/{pid}/card", {"code": "T1", "title": "Engenharia", "planned_effort": 8, "resource_key": "res_eng-01"}, t)
sc2, c2 = http("POST", f"/vps/project/{pid}/card", {"code": "T2", "title": "Montagem", "planned_effort": 16, "resource_key": "res_cel-mont-01"}, t)
sw, w = http("POST", f"/vps/project/{pid}/wbs", {"code": "1", "name": "Fase 1"}, t)
sd, dd = http("POST", f"/vps/project/{pid}/dependency", {"pred_card_id": c1.get("card_id"), "succ_card_id": c2.get("card_id")}, t)
ss, sch = http("POST", f"/vps/project/{pid}/schedule", None, t)
sas, asg = http("POST", f"/vps/card/{c2.get('card_id')}/assign", {"operator": "op_operations"}, t)
scp_, cpm = http("GET", f"/vps/project/{pid}/critical-path", None, t)
ok("projeto + 2 cards + WBS + dependencia + cronograma + atribuicao", all(x == 200 for x in (sp, sc1, sc2, sw, sd, ss, sas)),
   f"criticos={len([c for c in cpm.get('cards', []) if c.get('critical')])} makespan={cpm.get('makespan_h')}h")
se, ev = http("GET", "/events?category=VPS&limit=50", None, ADM)
acoes = sorted({e["action"] for e in ev.get("events", []) if e.get("entity_id") == pid})
ok("eventos na trilha para o projeto", {"PROJECT_CREATED", "CARD_CREATED", "WBS_ADDED", "DEPENDENCY_ADDED", "PROJECT_SCHEDULED", "CARD_ASSIGNED"} <= set(acoes) or len(acoes) >= 5, ", ".join(acoes))
sg, gs = http("GET", "/vps/aps/schedule?scenario=proj:" + proj.get("code", ""), None, t)
ok("cronograma do projeto virou cenario no APS", sg == 200 and len(gs.get("rows", [])) >= 2, f"{len(gs.get('rows', []))} operacoes")

print("\n== 5. E2E lado a lado (nao destrutivo)")
se, e2e = http("POST", "/vps/e2e/run", None, ADM, timeout=300)
ok("e2e.run passed", se == 200 and e2e.get("passed") is True,
   f"run={e2e.get('run_id')} passos={len(e2e.get('steps', []))} reset={e2e.get('reset')} kpis={e2e.get('kpis', {}).get('vinculos')}")
sr, rej = http("POST", "/vps/e2e/run?reset=true", None, TOKENS["op_projects"])
ok(f"reset por operador recusado ({sr}, esp 403)", sr == 403)

print("\n== 6. reconhecimento facial (YuNet + SFace)")
si, idn = http("POST", "/face/identify", {"image_b64": ZID})
ok("identify sem galeria responde (antes: 500)", si == 200 and idn.get("ok") is True, f"faces={idn.get('faces')} algo={idn.get('algo')}")
sen, enr = http("POST", "/face/enroll", {"operator_id": "op_smoke_face", "name": "Smoke Face", "image_b64": ZID, "consent": True})
ok("enroll com consentimento", enr.get("ok") is True, f"{enr.get('algo')} {enr.get('dim')}d nitidez={enr.get('sharpness')}")
si2, idn2 = http("POST", "/face/identify", {"image_b64": ZID})
ok("identify reconhece o cadastrado", idn2.get("matched") is True and idn2.get("operator_id") == "op_smoke_face", f"score={idn2.get('score')} thr={idn2.get('threshold')}")
sv, ver = http("POST", "/face/verify", {"operator_id": "op_smoke_face", "image_b64": BUS})
ok("verify com outra pessoa NAO confirma", ver.get("verified") is False or ver.get("ok") is False, f"score={ver.get('score')} · {ver.get('message', '')}")
sdel, rv = http("DELETE", "/face/op_smoke_face", None, ADM)
if sdel != 200:
    sdel, rv = http("POST", "/face/revoke", {"operator_id": "op_smoke_face"}, ADM)
ok("revogacao (LGPD)", rv.get("ok") is True or sdel == 200, str(sdel))

print("\n== 7. tecnologias sem token (edge)")
def infer(mode, extra=None):
    p = {"mode": mode, **(extra or {})}
    return http("POST", "/infer", {"image_b64": BUS, "task": {"mode": mode, "params": p}})
s, d = infer("DETECTAR", {"conf_threshold": 0.3}); ok("DETECTAR (YOLO26 Objects365)", s == 200 and d.get("pipeline") == "edge", f"{d.get('latency_ms')}ms {d.get('result', {}).get('contagens')}")
s, d = infer("RASTREAR", {"conf_threshold": 0.3}); ok("RASTREAR (ByteTrack)", s == 200 and d.get("pipeline") == "edge", f"{d.get('latency_ms')}ms")
s, d = infer("CONTAR", {"classes_alvo": ["person"], "conf_threshold": 0.3}); ok("CONTAR (edge)", s == 200 and d.get("model_type") == "edge", f"total={d.get('result', {}).get('total')}")
s, d = infer("LER", {}); ok("LER (edge OCR ou fallback)", s in (200, 503), f"pipeline={d.get('pipeline')} {str((d.get('detail') or {}).get('code', ''))}")
for bb in ("cnn", "vit"):
    s, d = http("POST", "/classify", {"image_b64": BUS, "backbone": bb, "topk": 3})
    ok(f"classificar {bb.upper()}", s == 200 and d.get("supported") is True, f"{(d.get('results') or [{}])[0].get('label')} {d.get('latency_ms')}ms")
s, d = http("POST", "/anomaly/fit", {"profile": "smoke_bus", "images_b64": [BUS, BUS, ZID]})
s2, d2 = http("POST", "/anomaly/score", {"profile": "smoke_bus", "image_b64": BUS})
ok("anomalia fit + score", d.get("ok") is True and d2.get("fitted") is True, f"tau={d.get('tau')} score={d2.get('anomaly_score')} modelo={d.get('modelo')}")
s, d = http("POST", "/thermo/asset", {"asset_id": "smoke_motor", "name": "Motor smoke", "t_max": 80})
s, d = http("POST", "/thermo/analyze", {"asset_id": "smoke_motor", "image_b64": BUS})
ok("termografia analyze", s == 200 and "severity" in d, f"{d.get('severity')} Tmax={d.get('t_max')}")
s, d = http("POST", "/metro/calibrate", {"ref": "smoke", "p1": {"x": 100, "y": 100}, "p2": {"x": 300, "y": 100}, "known_mm": 50.0, "frame_w": 640, "frame_h": 480})
s2, d2 = http("POST", "/metro/measure", {"kind": "linear", "points": [{"x": 100, "y": 200}, {"x": 200, "y": 200}], "frame_w": 640, "frame_h": 480, "feature": "cota_smoke", "nominal": 25.0})
ok("metrologia calibrar + medir", s == 200 and s2 == 200, f"{json.dumps(d2)[:90]}")
s, d = http("POST", "/automation/simulate", None); s2, d2 = http("GET", "/automation/kpis", None)
ok("automacao (PLC/IHM simulado) + KPIs", s == 200 and s2 == 200, f"OEE={d2.get('CLD_OEE')}")
s, d = http("POST", "/iamac/ask", {"question": "como funciona a reconciliacao fisico x ERP?"})
ok("iaMAC RAG extrativo", s == 200 and len(d.get("citations", [])) > 0, ", ".join(c["source"] for c in d.get("citations", [])[:2]))

print("\n== 8. tecnologias com token (VLM) — ativas, aguardando credito")
for mode in ("DESCREVER", "ANALISAR"):
    s, d = infer(mode, {"foco": "a cena"} if mode == "DESCREVER" else {"criterios": ["presenca de pessoas"]})
    code = (d.get("detail") or {}).get("code") if isinstance(d.get("detail"), dict) else None
    msg = (d.get("detail") or {}).get("message", "") if isinstance(d.get("detail"), dict) else ""
    if s == 200:
        REL["ok"].append(f"{mode} via VLM respondeu")
    elif "credit" in msg.lower():
        REL["aguardando_token"].append(f"{mode}: chave valida, sem credito (400 credit balance)")
    else:
        REL["falhas"].append(f"{mode}: {s} {code} {msg[:80]}")
    print(f"  {mode}: {s} {code or ''} {msg[:70]}")

print("\n== 9. trilha de auditoria e espelho PostgreSQL")
c = sqlite3.connect("/var/lib/visiondesk/visiondesk.db")
cats = dict(c.execute("SELECT category, COUNT(*) FROM audit_event GROUP BY category").fetchall())
den = c.execute("SELECT COUNT(*) FROM audit_event WHERE action='RBAC_DENIED'").fetchone()[0]
e2e_runs = c.execute("SELECT COUNT(DISTINCT correlation_id) FROM audit_event WHERE category='E2E'").fetchone()[0]
print("  por categoria:", cats); print("  RBAC_DENIED:", den, "| rodadas E2E:", e2e_runs)
ok("negativas RBAC auditadas", den >= 5, str(den))
ok("rodada E2E auditada", e2e_runs >= 1, str(e2e_runs))
try:
    import psycopg
    pg = psycopg.connect("dbname=visiondesk_audit", connect_timeout=3)
    n = pg.execute("SELECT count(*) FROM audit.audit_event").fetchone()[0]
    ok("espelho PostgreSQL da auditoria recebendo", n > 0, f"{n} eventos no PG")
except Exception as e:  # noqa: BLE001
    ok("espelho PostgreSQL da auditoria", False, str(e)[:80])

print("\n== RESUMO")
print(json.dumps({"ok": len(REL["ok"]), "falhas": REL["falhas"], "aguardando_token": REL["aguardando_token"],
                  "pins_teste": PINS}, ensure_ascii=False, indent=1))
