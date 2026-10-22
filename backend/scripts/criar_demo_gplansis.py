"""Cria o "Projeto Teste Demo Gplansis" completo, do zero até a conclusão.

Para que serve: deixar no sistema um projeto de referência que percorreu o
processo INTEIRO e que exibe, ao mesmo tempo, os três desfechos que a operação
real tem — o que fecha, o que trava por falta de material e o que trava por
falta de estrutura. Um seed que só mostra o caminho feliz não prova nada.

  OP-DEMO-0001  separação completa  → atravessa as 8 fases e FECHA
  OP-DEMO-0002  separação parcial   → trava no PICKING (pendência bloqueante)
  OP-DEMO-0003  produto sem BOM     → trava no PCP (BOM_INCOMPLETE)

Uso, na máquina do servidor:
    cd /opt/visiondesk && sudo -u visiondesk .venv/bin/python \
        scripts/criar_demo_gplansis.py [--refazer]

Idempotente por recusa: se o projeto já existir, não faz nada. `--refazer` apaga
projeto, WBS e cards e abre a INSTÂNCIA seguinte das mesmas ordens (`:02`, `:03`
…), arquivando as anteriores. Os eventos do Fio nunca são apagados: um Tag-ID é
um fato do processo, e refazer é abrir outra instância, não reescrever a história.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import get_connection, init_db, set_actor  # noqa: E402
from app.vps import engine, orders, pcp, phases, planning, store  # noqa: E402

CODIGO = "PRJ-DEMO-GPLANSIS"
NOME = "Projeto Teste Demo Gplansis"
ATOR = "op_admin_demo"

SAIDAS = ["DRAWINGS_APPROVED", "SUPPLY_LINKED", "STRUCTURE_RELEASED", "PICK_COMPLETED",
          "OP_OPERATION_DONE", "MEASUREMENT_APPROVED", "SHIPPED", "INVOICE_ISSUED"]


def _proxima_instancia() -> str:
    """A maior instância já usada pelas OPs de demonstração, mais um."""
    linhas = get_connection().execute(
        # O % vai por PARÂMETRO: escrito no SQL, o psycopg o lê como placeholder
        # e recusa a query. Vale para toda consulta com LIKE neste código.
        "SELECT instance FROM vps_tag WHERE entity_type=? AND natural_key LIKE ?",
        ("OP", "OP-DEMO-%"),
    ).fetchall()
    maior = 0
    for r in linhas:
        v = str(dict(r).get("instance") or "01")
        if v.isdigit():
            maior = max(maior, int(v))
    return f"{maior + 1:02d}"


def _andar(tag: str, ate: str | None = None) -> str:
    """Dispara as ações de saída em ordem, parando onde a guarda de fase travar.

    Começa da fase ATUAL, não do início da lista: disparar a saída de uma fase
    já vencida é transição inválida, e o motor (corretamente) abre ocorrência
    `INVALID_TRANSITION`. Retomar do começo enchia o Fio de ocorrências que não
    aconteceram na operação — ruído no exato lugar onde se procura sinal.
    """
    tpl = store.get_tag(tag)["template_id"]
    from app.vps import templates as _t
    fases = [p["id"] for p in (_t.get(tpl) or {}).get("phases", [])]
    atual = store.get_tag(tag)["current_phase"]
    inicio = fases.index(atual) if atual in fases else 0
    for acao in SAIDAS[inicio:]:
        t = store.get_tag(tag)
        if t["state"] in ("COMPLETED", "ARCHIVED"):
            break
        if ate and t["current_phase"] == ate:
            break
        antes = t["current_phase"]
        engine.capture({"tag_id": tag, "action": acao, "owner": "Operations",
                        "operator_id": ATOR, "payload": {"actor": ATOR, "via": "demo gplansis"}})
        if store.get_tag(tag)["current_phase"] == antes and store.get_tag(tag)["state"] != "COMPLETED":
            break
    t = store.get_tag(tag)
    return f"{t['state']} em {t['current_phase']}"


def main(refazer: bool = False) -> None:
    init_db()
    # O ator vai para os triggers de change_log: sem isto a criação inteira
    # apareceria na gestão de alterações com autor vazio.
    set_actor(ATOR, "script:criar_demo_gplansis")

    ja = get_connection().execute(
        "SELECT project_id FROM vps_project WHERE code=?", (CODIGO,)).fetchone()
    if ja and not refazer:
        print(f"{CODIGO} já existe ({dict(ja)['project_id']}). Use --refazer para recriar.")
        return
    instancia = "01"
    if ja:
        pid_velho = dict(ja)["project_id"]
        conn = get_connection()
        conn.execute("DELETE FROM vps_card_dep WHERE project_id=?", (pid_velho,))
        conn.execute("DELETE FROM vps_card WHERE project_id=?", (pid_velho,))
        conn.execute("DELETE FROM vps_wbs WHERE project_id=?", (pid_velho,))
        conn.execute("DELETE FROM vps_project WHERE project_id=?", (pid_velho,))
        # As ORDENS não são apagadas: um Tag-ID é um fato do processo e o Event
        # Store é imutável. Refazer é abrir a INSTÂNCIA seguinte da mesma chave
        # natural — é para isso que o último campo do Tag-ID existe — e arquivar
        # a anterior, que continua consultável.
        instancia = _proxima_instancia()
        for r in get_connection().execute(
                "SELECT tag_id, state FROM vps_tag WHERE entity_type=? AND natural_key LIKE ?",
                ("OP", "OP-DEMO-%"),
        ).fetchall():
            t = dict(r)
            if t["state"] not in ("ARCHIVED",):
                get_connection().execute("UPDATE vps_tag SET state='ARCHIVED' WHERE tag_id=?", (t["tag_id"],))
        print(f"projeto anterior removido ({pid_velho}); ordens antigas arquivadas; "
              f"nova instância das OPs: {instancia}")

    pcp.seed()  # garante que existe estrutura PANEL para explodir

    proj = planning.create_project({"code": CODIGO, "name": NOME, "segment": "PANEL",
                                    "owner": "Projects"})
    pid = proj["project_id"]
    print(f"projeto {proj['code']} · {pid} · tag {proj['tag_id']}")

    planning.add_wbs(pid, "1", "Fornecimento")
    planning.add_wbs(pid, "2", "Montagem e ensaios")

    pedidos = [
        {"code": "OP-DEMO-0001", "title": "Painel QGBT — obra Norte", "product_key": "PANEL",
         "qty": 2, "planned_start": "2026-09-14T08:00:00-03:00",
         "planned_end": "2026-09-21T17:00:00-03:00", "resource_key": "res_montagem"},
        {"code": "OP-DEMO-0002", "title": "Painel de comando CCM-2", "product_key": "PANEL",
         "qty": 1, "planned_start": "2026-09-16T08:00:00-03:00",
         "planned_end": "2026-09-25T17:00:00-03:00", "resource_key": "res_montagem"},
        {"code": "OP-DEMO-0003", "title": "Painel especial — produto sem estrutura",
         "qty": 1, "planned_start": "2026-09-18T08:00:00-03:00",
         "planned_end": "2026-09-30T17:00:00-03:00"},
    ]
    lote = orders.abrir_lote(pedidos, {"project_id": pid, "segment": "PANEL",
                                       "actor": ATOR, "instance": instancia})
    print(f"ordens abertas: {lote['ok']}/{lote['total']}")
    for r in lote["recusadas"]:
        print(f"  recusada: {r.get('message')}")
    ops = [a["tag_id"] for a in lote["abertas"]]
    if len(ops) < 3:
        print("ATENÇÃO: nem todas as ordens abriram — o restante do roteiro fica parcial")

    sched = planning.schedule(pid)
    print(f"agendamento: {sched['scheduled']} card(s), {sched['ancorados']} com janela própria")
    print(f"janela do projeto: {sched['janela']}")
    bl = planning.set_baseline(pid, by=ATOR)
    print(f"baseline versão {bl.get('version')} congelado")

    # OP 1 — separação completa, segue até faturar
    _andar(ops[0], ate="PICKING")
    for d in pcp.demands(ops[0]):
        pcp.set_demand(d["demand_id"], d["qty_planned"], actor=ATOR)
    print(f"OP-DEMO-0001: {_andar(ops[0])}")

    # OP 2 — separação PARCIAL: falta material, trava no picking
    _andar(ops[1], ate="PICKING")
    dem2 = pcp.demands(ops[1])
    for i, d in enumerate(dem2):
        pcp.set_demand(d["demand_id"], d["qty_planned"] if i else d["qty_planned"] / 2, actor=ATOR)
    print(f"OP-DEMO-0002: {_andar(ops[1])}")

    # OP 3 — sem estrutura: trava no PCP
    print(f"OP-DEMO-0003: {_andar(ops[2])}")

    # replanejamento manual de uma etapa, para o projeto já nascer com histórico
    et = phases.rows(ops[1])
    if len(et) > 4:
        phases.set_window(ops[1], et[4]["phase"], "2026-09-28T08:00:00-03:00",
                          "2026-10-02T17:00:00-03:00", actor=ATOR)

    planning.refresh_progress(pid)
    pva = planning.plan_vs_actual(pid)
    print("\nplanejado × realizado:")
    for c in pva["cards"]:
        print(f"  {c['code']:14} {c['state']:14} plano {str(c['planned_start'])[:10]}"
              f" → {str(c['planned_end'])[:10]}  {c['pct']}%")
    print(f"KPIs: {pva['kpis']}")
    print(f"\npronto: {CODIGO} ({pid})")


if __name__ == "__main__":
    main(refazer="--refazer" in sys.argv)
