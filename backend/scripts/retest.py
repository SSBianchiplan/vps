"""Re-teste focado: recuperacao BM25 sobre planilha enviada; pular fases ate DONE."""
import os
import io
import json
import sys
import urllib.error
import urllib.request
import uuid

API = os.environ.get("VISIONDESK_API", "http://localhost:8200/api")
ADMIN_PIN, OPER_PIN = sys.argv[1], sys.argv[2]


def http(method, path, body=None, token=None, raw=None, ctype="application/json"):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(API + path, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", ctype)
    if token:
        req.add_header("X-Auth-Token", token)
    try:
        with urllib.request.urlopen(req, timeout=240) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except Exception:
            return e.code, {}


def login(oid, pin):
    return http("POST", "/auth/login/pin", {"operator_id": oid, "pin": pin})[1].get("token")


ADM, OPER = login("op_admin_demo", ADMIN_PIN), login("op_operations", OPER_PIN)

import openpyxl  # noqa: E402
wb = openpyxl.Workbook(); ws = wb.active; ws.title = "KPIs"
ws.append(["indicador", "meta", "real"]); ws.append(["OEE", 85, 93.1]); ws.append(["OTIF", 95, 100]); ws.append(["Refugo", 2, 1.4])
bx = io.BytesIO(); wb.save(bx)
b = uuid.uuid4().hex
raw = (f"--{b}\r\nContent-Disposition: form-data; name=\"files\"; filename=\"kpis_setembro.xlsx\"\r\nContent-Type: application/octet-stream\r\n\r\n").encode() + bx.getvalue() + f"\r\n--{b}--\r\n".encode()
s, up = http("POST", "/iamac/library/upload", raw=raw, ctype=f"multipart/form-data; boundary={b}", token=ADM)
print("upload:", s, [(r["file"], r.get("lido"), r.get("chunks")) for r in up.get("results", [])])
for q in ["qual a meta e o real de OEE na planilha de KPIs?", "qual o indicador de refugo em setembro?"]:
    s, a = http("POST", "/iamac/ask", {"question": q})
    print(f"P: {q}\n   fontes: {[c['source'] for c in a.get('citations', [])][:3]}\n   resposta: {(a.get('answer') or '')[:120].replace(chr(10), ' ')}")
http("DELETE", "/iamac/library/kpis_setembro.xlsx", token=ADM)

print("\n== pular fases ate DONE (SHIPPING → DONE = 2 saidas, 1 fase pulada)")
s, bd = http("GET", "/vps/board?entity=OP&segment=PANEL")
c = next((x for x in bd["cards"] if x["natural_key"] == "OP-2026-05005"), None)
print("estado atual:", c and (c["phase"], c["state"], c["pendings"]))
if c and c["phase"] != "DONE":
    s, d = http("POST", f"/vps/thread/{c['tag_id']}/move", {"to_phase": "DONE", "reason": "expedicao e faturamento confirmados pelo ERP (teste de fechamento pelo kanban)"}, OPER)
    print("move → DONE:", s, {k: d.get(k) for k in ("from", "to", "state", "phase", "fired", "occurrences")} if s == 200 else d)
    s, th = http("GET", f"/vps/thread/{c['tag_id']}")
    print("ocorrencias:", [o["kind"] for o in th.get("occurrences", [])], "| estado:", th["tag"]["state"], "| closed_ts:", bool(th["tag"].get("closed_ts")))
s, k = http("GET", "/vps/kpis")
print("kpis:", {x: k.get(x) for x in ("CLD_Thread_LeadTime_h", "CLD_OTIF", "CLD_Schedule_Adherence", "CLD_Reconciliation_Rate", "CLD_Completed_Threads")})
