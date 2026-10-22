"""Verificação da rodada: PostgreSQL, log de mudanças, árvore, operadores, kanban e E2E."""
import os
import json
import sys
import urllib.error
import urllib.request

API = os.environ.get("VISIONDESK_API", "http://localhost:8200/api")
ADMIN_PIN, OPER_PIN = sys.argv[1], sys.argv[2]
REL = {"ok": [], "falhas": []}


def http(m, p, body=None, token=None, timeout=300):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(API + p, data=data, method=m)
    if data is not None:
        r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("X-Auth-Token", token)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as x:
            return x.status, json.loads(x.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except Exception:
            return e.code, {}


def ok(nome, cond, det=""):
    (REL["ok"] if cond else REL["falhas"]).append(nome + (f" — {det}" if det else ""))
    print(("  [ok]   " if cond else "  [FALHA] ") + nome + (f" — {det}" if det else ""), flush=True)


def login(oid, pin):
    return http("POST", "/auth/login/pin", {"operator_id": oid, "pin": pin})[1].get("token")


ADM, OPER = login("op_admin_demo", ADMIN_PIN), login("op_operations", OPER_PIN)
ok("logins", bool(ADM and OPER))

print("\n== 1. runtime em PostgreSQL")
s, d = http("GET", "/databases")
prim = next((b for b in d["bases"] if b["key"] == "primary"), {})
ok("banco principal é PostgreSQL", "PostgreSQL" in prim.get("kind", ""), prim.get("kind"))
ok("bases operacionais", d["resumo"]["ok"] >= 16, str(d["resumo"]))

print("\n== 2. gestão de alterações")
s, r = http("GET", "/changes/summary", token=ADM)
ok("change_log disponível", r.get("disponivel") is True, f"{r.get('total')} mudanças · {len(r.get('tabelas_monitoradas', []))} tabelas monitoradas")
s, anon = http("GET", "/changes/summary")
ok(f"sem sessão é recusado ({s})", s == 403)
# provoca uma mudança e confere autor + campos
s, ops = http("GET", "/vps/operators")
alvo = next((o for o in ops["operators"] if o["operator_id"] == "u123"), None)
if alvo:
    novo_turno = "T2" if alvo.get("shift") != "T2" else "T3"
    s, _ = http("POST", "/vps/operators", {**{k: alvo.get(k) for k in ("operator_id", "name", "matricula", "badge", "role", "stations", "skills", "status")}, "shift": novo_turno}, ADM)
    s, l = http("GET", "/changes?table=vps_operator&pk=u123&limit=3", token=ADM)
    ult = (l.get("changes") or [{}])[0]
    ok("mudança registrada com autor e campo", ult.get("actor") == "op_admin_demo" and "shift" in (ult.get("changed_fields") or []),
       f"autor={ult.get('actor')} campos={ult.get('changed_fields')} origem={ult.get('origem')}")
    ok("guarda o antes e o depois", (ult.get("before_json") or {}).get("shift") != (ult.get("after_json") or {}).get("shift"),
       f"{(ult.get('before_json') or {}).get('shift')} → {(ult.get('after_json') or {}).get('shift')}")

print("\n== 3. usuários ↔ operadores")
s, ops = http("GET", "/vps/operators")
com_login = [o for o in ops["operators"] if o.get("tem_login")]
ok("usuários do sistema aparecem como operadores", len(com_login) >= 6, f"{len(com_login)} de {len(ops['operators'])}")
ok("operador carrega papel de acesso e perfil", any(o.get("login_role") and o.get("perfil") for o in com_login),
   str([(o["operator_id"], o.get("login_role"), o.get("perfil")) for o in com_login][:3]))
s, opc = http("GET", "/vps/operators/options")
ok("listas segmentadas por coluna", all(k in opc for k in ("role", "stations", "skills", "shift", "perfil")),
   ", ".join(f"{k}:{len(v)}" for k, v in opc.items()))

print("\n== 4. árvore do planejamento")
s, t = http("GET", "/vps/planning/tree")
ramos = {r["label"]: r for r in t["arvore"]["filhos"]}
ok("três ramos com dados", len(ramos) == 3 and all(r["filhos"] for r in ramos.values()),
   " · ".join(f"{k}={len(v['filhos'])}" for k, v in ramos.items()))
ok("bases vinculadas a cada nó", len(t["bases"]) >= 16, f"{len(t['bases'])} tabelas · {t['resumo']['nos']} nós")
tem_tag = json.dumps(t["arvore"]).count('"tag_id"')
ok("nós carregam o Tag-ID (elo entre os ramos)", tem_tag > 0, f"{tem_tag} nós com Tag-ID")
elo = [c for c in ramos.get("APS — sequenciamento", {}).get("filhos", []) if c.get("vinculo")]
ok("cenário do APS aponta para o projeto", bool(elo), str([e["vinculo"] for e in elo]))

print("\n== 5. kanban: fase de outro template")
s, b = http("GET", "/vps/board")
gen = next((c for c in b["cards"] if c.get("template_id") == "GENERIC_V1" and c["state"] not in ("COMPLETED", "ARCHIVED")), None)
if gen:
    s, d = http("POST", f"/vps/thread/{gen['tag_id']}/move", {"to_phase": "ASSEMBLY", "reason": "teste de fase invalida"}, ADM)
    msg = (d.get("detail") or {}).get("message", "")
    ok(f"recusa explica as fases possíveis ({s})", s == 409 and "Fases possíveis" in msg, msg[:110])
else:
    ok("card GENERIC_V1 disponível para o teste", False, "nenhum encontrado")

print("\n== 6. E2E com linhagem e mudanças")
s, e = http("POST", "/vps/e2e/run", None, ADM, timeout=600)
ok("e2e aprovado", e.get("passed") is True, f"{len(e.get('steps', []))} passos · run {e.get('run_id')}")
lin = e.get("lineage") or []
ok("linhagem detalhada com estado das duas pontas", len(lin) >= 9 and all("pai_estado" in v for v in lin),
   f"{len(lin)} vínculos · ex.: {lin[0]['relacao'] if lin else '—'}")
ok("mudanças da rodada capturadas no banco", len(e.get("changes") or []) > 0, f"{len(e.get('changes') or [])} mudanças")
s, ev = http("GET", "/events?category=E2E&limit=200", token=ADM)
lin_ev = [x for x in ev.get("events", []) if x.get("action") == "E2E_LINEAGE"]
ok("linhagem registrada na trilha", len(lin_ev) >= 9, f"{len(lin_ev)} eventos E2E_LINEAGE")

print("\n== RESUMO")
print(json.dumps({"ok": len(REL["ok"]), "falhas": REL["falhas"]}, ensure_ascii=False, indent=1))
