"""Conexão de banco com backend dual: SQLite (default) ou Postgres (#2).

- Sem VISIONDESK_DATABASE_URL → SQLite por thread (WAL + busy_timeout), como antes.
- Com VISIONDESK_DATABASE_URL=postgresql://… e psycopg disponível → Postgres.

O repositório (repository.py) é agnóstico: usa placeholders `?`, `ON CONFLICT … DO
UPDATE SET … excluded.x` e BEGIN/COMMIT/ROLLBACK — compatíveis com ambos. Um
adaptador fino traduz `?`→`%s` e o controle de transação p/ o Postgres.
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from ..config import get_settings
from ..logging_conf import get_logger

log = get_logger("visiondesk.db")
_SCHEMA = Path(__file__).with_name("schema.sql")
_local = threading.local()
_init_lock = threading.Lock()
_initialized = False


def _use_pg() -> bool:
    return bool(get_settings().database_url) and _psycopg() is not None


def _psycopg():
    try:
        import psycopg  # noqa: F401
        return psycopg
    except Exception:
        return None


# ── SQLite ──────────────────────────────────────────────────────────
def _new_sqlite() -> sqlite3.Connection:
    settings = get_settings()
    conn = sqlite3.connect(settings.db_file(), check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    # Performance de escrita (seguro sob WAL): fsync no checkpoint, não a cada commit.
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA temp_store = MEMORY;")
    conn.execute("PRAGMA cache_size = -16000;")   # ~16 MB de cache de página
    conn.execute("PRAGMA mmap_size = 134217728;")  # 128 MB mmap
    return conn


# ── Postgres (adaptador) ────────────────────────────────────────────
class _Empty:
    rowcount = 0
    def fetchone(self): return None
    def fetchall(self): return []


class PgConn:
    """Adapta a API usada pelo repositório (execute/fetch/BEGIN-COMMIT) ao psycopg3."""

    def __init__(self, raw) -> None:
        self._c = raw

    def execute(self, sql: str, params=()):
        s = sql.strip().upper()
        if s == "BEGIN":
            if self._c.autocommit:
                self._c.autocommit = False
            return _Empty()
        if s == "COMMIT":
            self._c.commit(); self._c.autocommit = True; return _Empty()
        if s == "ROLLBACK":
            self._c.rollback(); self._c.autocommit = True; return _Empty()
        return self._c.execute(sql.replace("?", "%s"), tuple(params))

    def close(self) -> None:
        self._c.close()


def _new_pg() -> PgConn:
    psycopg = _psycopg()
    from psycopg.rows import dict_row
    raw = psycopg.connect(get_settings().database_url, autocommit=True, row_factory=dict_row)
    return PgConn(raw)


def _pg_init_schema() -> None:
    psycopg = _psycopg()
    from psycopg.rows import dict_row
    script = _SCHEMA.read_text(encoding="utf-8")
    with psycopg.connect(get_settings().database_url, autocommit=True, row_factory=dict_row) as conn:
        for raw in script.split(";"):
            lines = [ln for ln in raw.splitlines() if not ln.strip().startswith("--")]
            stmt = "\n".join(lines).strip()
            if not stmt or stmt.upper().startswith("PRAGMA"):
                continue
            conn.execute(stmt)
        # TimescaleDB (best-effort): hypertable da série de métricas (time-partition).
        try:
            conn.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
            conn.execute("SELECT create_hypertable('metric_timeseries','time',if_not_exists=>TRUE,migrate_data=>TRUE)")
            log.info("TimescaleDB: hypertable metric_timeseries ativa")
        except Exception as exc:  # noqa: BLE001
            log.info("TimescaleDB indisponível (%s) — metric_timeseries como tabela comum.", str(exc).split(chr(10))[0][:80])


# ── API pública (inalterada) ────────────────────────────────────────
def init_db() -> None:
    global _initialized
    with _init_lock:
        if _initialized:
            return
        if _use_pg():
            _pg_init_schema()
            log.info("DB: Postgres (%s)", get_settings().database_url.split("@")[-1])
        else:
            conn = _new_sqlite()
            try:
                conn.executescript(_SCHEMA.read_text(encoding="utf-8"))
            finally:
                conn.close()
            log.info("DB: SQLite (%s)", get_settings().db_path)
        _initialized = True


def get_connection():
    if not _initialized:
        init_db()
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = _new_pg() if _use_pg() else _new_sqlite()
        _local.conn = conn
    return conn


def close_db() -> None:
    conn = getattr(_local, "conn", None)
    if conn is not None:
        conn.close()
        _local.conn = None
