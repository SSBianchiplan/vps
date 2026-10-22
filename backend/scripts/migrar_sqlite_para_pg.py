"""Migra o runtime do SQLite para o PostgreSQL, preservando o histórico.

POR QUE MIGRAR EM VEZ DE COMEÇAR DO ZERO

O banco de runtime carrega a trilha de auditoria, o Event Store do Fio Dourado
e as contas. Recomeçar apagaria a rastreabilidade — exatamente o que o sistema
existe para não perder.

COMO RODA

    VISIONDESK_DATABASE_URL=postgresql://... \\
    python scripts/migrar_sqlite_para_pg.py [--sqlite CAMINHO] [--truncar]

O destino é criado pelo próprio backend (`init_db` aplica schema + change_log).
Este script só copia dados. É idempotente: usa ON CONFLICT DO NOTHING, então
rodar duas vezes não duplica.

TRIGGERS DURANTE A CARGA

A carga histórica é desligada dos triggers de change_log: importar 900 eventos
antigos geraria 900 "mudanças" com a data de hoje e ator nulo, poluindo o log
que deveria mostrar o que mudou DEPOIS da migração. O histórico já está no
audit_event, que vem junto.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Ordem importa: pai antes de filho (chaves estrangeiras).
ORDEM = [
    "app_config", "dim_source", "dim_task", "dim_model", "dim_action_rule",
    "vps_access", "vps_operator", "vps_face_template", "vps_resource",
    "vps_tag", "vps_event", "vps_lineage", "vps_pending", "vps_occurrence",
    "vps_erp_doc", "vps_project", "vps_wbs", "vps_card", "vps_card_dep",
    "vps_baseline", "vps_baseline_card", "vps_schedule",
    "auth_session", "audit_event", "audit",
    "fact_detection", "fact_count", "fact_ocr", "fact_recording", "fact_action",
    "thermal_asset", "thermal_reading", "metro_calibration", "metro_measurement",
    "ot_asset", "ot_reading", "ot_synoptic", "vps_track_summary",
    "ia_interaction", "ia_eval", "metric_timeseries",
]


def colunas_pg(cur, tabela: str) -> list[str]:
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name=%s AND table_schema='public'", (tabela,))
    return [r[0] for r in cur.fetchall()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sqlite", default=os.environ.get("VISIONDESK_DB_PATH", "./data/visiondesk.db"))
    ap.add_argument("--truncar", action="store_true", help="esvazia o destino antes (perde o que já estiver lá)")
    a = ap.parse_args()

    dsn = os.environ.get("VISIONDESK_DATABASE_URL")
    if not dsn:
        print("defina VISIONDESK_DATABASE_URL"); return 1
    origem = Path(a.sqlite)
    if not origem.exists():
        print(f"SQLite não encontrado: {origem}"); return 1

    import psycopg

    src = sqlite3.connect(str(origem))
    src.row_factory = sqlite3.Row
    tabelas_src = {r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    total = 0
    with psycopg.connect(dsn, autocommit=False) as dst:
        cur = dst.cursor()
        # Sem triggers durante a carga histórica (ver cabeçalho).
        # `session_replication_role` exigiria superusuário; desligar o trigger
        # tabela a tabela é permitido ao DONO da tabela — que é o papel da
        # aplicação. Fica também mais preciso: só o log de mudanças sai do ar,
        # as chaves estrangeiras continuam valendo.
        cur.execute("""SELECT event_object_table FROM information_schema.triggers
                       WHERE trigger_name='trg_change_log' GROUP BY 1""")
        com_log = [r[0] for r in cur.fetchall()]
        for t in com_log:
            cur.execute(f'ALTER TABLE "{t}" DISABLE TRIGGER trg_change_log')
        print(f"log de mudanças desligado em {len(com_log)} tabela(s) durante a carga")

        if a.truncar:
            for t in reversed(ORDEM):
                if t in tabelas_src:
                    cur.execute(f'TRUNCATE TABLE "{t}" CASCADE')
            print("destino truncado")

        for tabela in ORDEM:
            if tabela not in tabelas_src:
                continue
            cols_dst = set(colunas_pg(cur, tabela))
            if not cols_dst:
                print(f"  · {tabela}: não existe no destino, pulando")
                continue
            linhas = src.execute(f'SELECT * FROM "{tabela}"').fetchall()
            if not linhas:
                continue
            # só as colunas que existem nos DOIS lados: o schema evolui e uma
            # coluna a mais de um lado não pode derrubar a migração inteira
            cols = [c for c in linhas[0].keys() if c in cols_dst]
            if not cols:
                continue
            campos = ", ".join(f'"{c}"' for c in cols)
            marcas = ", ".join(["%s"] * len(cols))
            sql = f'INSERT INTO "{tabela}" ({campos}) VALUES ({marcas}) ON CONFLICT DO NOTHING'
            dados = [tuple(r[c] for c in cols) for r in linhas]
            cur.executemany(sql, dados)
            print(f"  · {tabela}: {len(dados)} linha(s)")
            total += len(dados)

        # Sequências (BIGSERIAL) precisam ser reposicionadas: sem isto o
        # próximo INSERT tentaria o id 1, que já existe, e falharia.
        cur.execute("""
            SELECT c.table_name, c.column_name, pg_get_serial_sequence(c.table_name, c.column_name)
            FROM information_schema.columns c
            WHERE c.table_schema='public' AND pg_get_serial_sequence(c.table_name, c.column_name) IS NOT NULL
        """)
        for tabela, coluna, seq in cur.fetchall():
            cur.execute(f'SELECT setval(%s, COALESCE((SELECT MAX("{coluna}") FROM "{tabela}"), 0) + 1, false)', (seq,))
        print("sequências reposicionadas")

        for t in com_log:
            cur.execute(f'ALTER TABLE "{t}" ENABLE TRIGGER trg_change_log')
        print("log de mudanças religado")
        dst.commit()

        cur.execute("SELECT COUNT(*) FROM change_log")
        print(f"\\nmigradas {total} linha(s) · change_log com {cur.fetchone()[0]} registro(s) (a carga não gera log)")
    src.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
