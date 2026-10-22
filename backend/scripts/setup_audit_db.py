"""Cria/reconfigura a base PostgreSQL de auditoria (rastreabilidade total).

- Verifica se a base `visiondesk_audit` já existe → se sim, só REconfigura (aplica
  o schema idempotente); se não, cria.
- Aplica db/audit_postgres.sql (schema audit, append-only + partições + trigger).
- Opcional: sincroniza os eventos já gravados no runtime (SQLite) → PG.

Uso: .venv/bin/python scripts/setup_audit_db.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
DDL = ROOT / "app" / "db" / "audit_postgres.sql"
TARGET = os.environ.get("VISIONDESK_AUDIT_DB", "visiondesk_audit")


def split_sql(sql: str) -> list[str]:
    """Divide em statements respeitando blocos dollar-quoted ($$...$$).

    Ignora linhas que são SÓ comentário (`-- ...`) fora de blocos $$ — senão um
    comentário de seção gruda no statement seguinte e quebra a divisão.
    """
    stmts, buf, in_dollar = [], [], False
    for line in sql.splitlines():
        if not in_dollar and line.lstrip().startswith("--"):
            continue
        buf.append(line)
        if line.count("$$") % 2 == 1:
            in_dollar = not in_dollar
        if not in_dollar and line.rstrip().endswith(";"):
            stmts.append("\n".join(buf)); buf = []
    if "".join(buf).strip():
        stmts.append("\n".join(buf))
    return [s for s in stmts if s.strip()]


def maintenance_conn() -> psycopg.Connection:
    for dsn in ("dbname=postgres", "dbname=teste_sistema", ""):
        try:
            return psycopg.connect(dsn or None, autocommit=True, connect_timeout=3)
        except Exception:  # noqa: BLE001
            continue
    raise SystemExit("✗ PostgreSQL indisponível (nenhuma base de manutenção acessível).")


def main() -> None:
    # 1) garante a base (verifica antes — só reconfigura se já existe)
    m = maintenance_conn()
    exists = m.execute("SELECT 1 FROM pg_database WHERE datname=%s", (TARGET,)).fetchone()
    if exists:
        print(f"• base '{TARGET}' já existe → reconfigurando schema (idempotente)")
    else:
        m.execute(f'CREATE DATABASE "{TARGET}"')
        print(f"✓ base '{TARGET}' criada")
    m.close()

    # 2) aplica o schema (idempotente)
    conn = psycopg.connect(f"dbname={TARGET}")
    cur = conn.cursor()
    for stmt in split_sql(DDL.read_text(encoding="utf-8")):
        cur.execute(stmt)
    conn.commit()
    tabs = cur.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_schema='audit'").fetchone()[0]
    print(f"✓ schema 'audit' aplicado · {tabs} tabela(s)/partição(ões)")
    conn.close()

    # 3) sincroniza o que já existe no runtime (SQLite) → PG (best-effort)
    try:
        sys.path.insert(0, str(ROOT))
        os.environ["VISIONDESK_AUDIT_DB"] = TARGET
        from app import audit, audit_pg  # noqa: E402
        audit.backfill(force=True)        # garante trilha a partir dos fatos
        res = audit_pg.sync()
        print(f"✓ sync runtime→PG: {res}")
    except Exception as exc:  # noqa: BLE001
        print(f"• sync pulado ({str(exc)[:80]}) — rode pelo app (Bases → Sincronizar) depois")

    print(f"\nPronto. Conferir: psql -d {TARGET} -c 'SELECT * FROM audit.v_by_category;'")


if __name__ == "__main__":
    main()
