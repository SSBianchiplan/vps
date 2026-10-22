"""Conexão de banco com backend dual: SQLite (default) ou Postgres (#2).

- Sem VISIONDESK_DATABASE_URL → SQLite por thread (WAL + busy_timeout), como antes.
- Com VISIONDESK_DATABASE_URL=postgresql://… e psycopg disponível → Postgres.

O repositório (repository.py) é agnóstico: usa placeholders `?`, `ON CONFLICT … DO
UPDATE SET … excluded.x` e BEGIN/COMMIT/ROLLBACK — compatíveis com ambos. Um
adaptador fino traduz `?`→`%s` e o controle de transação p/ o Postgres.
"""
from __future__ import annotations

import re
import sqlite3
import threading
from contextvars import ContextVar
from pathlib import Path
from typing import Any

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


# ── Tradução de dialeto ─────────────────────────────────────────────
# O código foi escrito em SQLite. Em vez de reescrever cada consulta, um
# tradutor cobre as três construções que o PostgreSQL não aceita. Mantém uma
# base de código só para os dois bancos — e o SQLite continua sendo o caminho
# de quem roda local sem servidor.
_RE_INSERT_IGNORE = re.compile(r"^\s*INSERT\s+OR\s+IGNORE\s+INTO", re.I)
_RE_INSERT_REPLACE = re.compile(r"^\s*INSERT\s+OR\s+REPLACE\s+INTO", re.I)


def traduz_sql(sql: str) -> str:
    """SQLite → PostgreSQL: placeholders, INSERT OR IGNORE e rowid."""
    out = sql
    if _RE_INSERT_IGNORE.match(out):
        out = _RE_INSERT_IGNORE.sub("INSERT INTO", out, count=1)
        if " ON CONFLICT" not in out.upper():
            out = out.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
    elif _RE_INSERT_REPLACE.match(out):
        # sem a chave de conflito não dá para traduzir com segurança: quem usa
        # INSERT OR REPLACE precisa escrever o ON CONFLICT explícito.
        raise ValueError("INSERT OR REPLACE não é portável — escreva ON CONFLICT ... DO UPDATE")
    # rowid do SQLite não existe no PG; o schema cria a coluna `seq` no lugar.
    out = out.replace("rowid AS _rowid", "seq AS _rowid").replace("MAX(rowid)", "MAX(seq)")
    out = re.sub(r"\browid\b", "seq", out)
    return out.replace("?", "%s")


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
        try:
            return self._c.execute(traduz_sql(sql), tuple(params))
        except Exception as exc:  # noqa: BLE001
            # A sessão pode morrer ENTRE a conferência do get_connection e esta
            # query — a janela é pequena, mas com stream de vídeo ela é visitada
            # muitas vezes por minuto. Uma tentativa a mais resolve.
            #
            # Só se repete quando é seguro: conexão comprovadamente morta E fora
            # de transação explícita. Dentro de um BEGIN a reconexão perderia o
            # que já foi escrito antes, e repetir às cegas poderia gravar duas
            # vezes; com a conexão morta, nada foi confirmado.
            if not self._morreu(exc) or not self._c.autocommit:
                raise
            log.warning("DB: sessão caiu durante a query — reconectando e repetindo uma vez")
            self._reconecta()
            return self._c.execute(traduz_sql(sql), tuple(params))

    @staticmethod
    def _morreu(exc: Exception) -> bool:
        try:
            import psycopg

            if not isinstance(exc, psycopg.OperationalError):
                return False
        except Exception:  # noqa: BLE001
            return False
        # A mensagem é o único sinal estável: psycopg usa OperationalError tanto
        # para "servidor sumiu" quanto para outros problemas de sessão.
        t = str(exc).lower()
        return any(p in t for p in ("connection is closed", "connection is lost",
                                    "server closed", "connection already closed",
                                    "consuming input failed", "ssl connection has been closed"))

    def _reconecta(self) -> None:
        try:
            self._c.close()
        except Exception:  # noqa: BLE001
            pass
        self._c = _raw_pg()
        # O ator vive na SESSÃO: a conexão nova não sabe quem está agindo, e sem
        # isto o change_log gravaria a próxima alteração com autor vazio.
        if hasattr(self, "_vd_ator"):
            del self._vd_ator

    def close(self) -> None:
        self._c.close()

    def viva(self) -> bool:
        """A sessão ainda serve para escrever?

        Três estados diferentes se disfarçam de "conexão ruim" e só o primeiro é
        óbvio:

        `closed`   o servidor derrubou a sessão (reinício do Postgres, timeout
                   ocioso, `pg_terminate_backend`). Toda query devolve
                   "the connection is closed".
        `broken`   o socket morreu no meio de uma query — "the connection is
                   lost". O objeto ainda existe e continua sendo reusado.
        ABORTADO   uma query falhou dentro de uma transação e ninguém deu
                   rollback: a sessão vive, mas recusa tudo com "current
                   transaction is aborted". Aqui dá para salvar — um rollback
                   devolve a conexão ao uso, sem reconectar.
        """
        c = self._c
        if getattr(c, "closed", False) or getattr(c, "broken", False):
            return False
        try:
            from psycopg.pq import TransactionStatus

            estado = c.info.transaction_status
            if estado in (TransactionStatus.INERROR, TransactionStatus.UNKNOWN):
                c.rollback()
                c.autocommit = True
            return True
        except Exception:  # noqa: BLE001 - se nem inspecionar dá, troque a conexão
            return False


def _raw_pg():
    psycopg = _psycopg()
    from psycopg.rows import dict_row
    return psycopg.connect(get_settings().database_url, autocommit=True, row_factory=dict_row)


def _new_pg() -> PgConn:
    return PgConn(_raw_pg())


_CHANGE_LOG = Path(__file__).with_name("change_log.sql")


def _comandos_sql(script: str) -> list[str]:
    """Separa um arquivo .sql em comandos.

    Tirar os comentários ANTES de separar por ";" é o ponto: o schema tem
    comentário com ponto e vírgula no meio ("-- ...; AQUI fica o sumário"), e
    separar primeiro deixava o resto do comentário virar um comando solto — que
    o Postgres recusa com erro de sintaxe apontando para uma palavra do texto.
    """
    limpo: list[str] = []
    for linha in script.splitlines():
        i = linha.find("--")
        # ignora "--" dentro de aspas simples (não ocorre hoje; evita cortar
        # um valor padrão do tipo '--x' se aparecer amanhã)
        if i >= 0 and linha.count("'", 0, i) % 2 == 0:
            linha = linha[:i]
        limpo.append(linha)
    return [c.strip() for c in "\n".join(limpo).split(";") if c.strip()]


def _pg_ddl(stmt: str) -> str:
    """DDL do SQLite → PostgreSQL (só o que aparece no schema deste projeto)."""
    out = stmt.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY")
    out = out.replace("AUTOINCREMENT", "")
    return out


# ── Contrato de dados das superfícies de EVENTO ──────────────────────
# (tabela, chave natural, precisa de `seq`)
#
# POR QUE ISTO EXISTE
#
# Uma carga do lakehouse falhou com `column "id" does not exist`. Ao olhar, as
# três superfícies de evento do sistema chamavam a mesma coisa de três nomes
# diferentes, e nenhuma tinha `id`:
#
#   public.vps_event    chave event_id · tinha `seq` — mas por acidente, porque
#                       o WebSocket do cockpit precisava de um contador
#   public.audit_event  chave event_id · NENHUM contador monotônico
#   audit.audit_event   chave (event_id, event_ts) · event_seq
#
# Resultado: quem consome pelo nome `id` quebra na hora, e a trilha de auditoria
# não podia ser ingerida de forma incremental de jeito nenhum — só varredura
# completa. Isso não é problema de quem consome: é contrato de dados faltando
# do nosso lado.
#
# Agora toda superfície append-only publica:
#   `id`   coluna gerada que espelha a chave natural (consumidor com a
#          convenção `id` funciona; o código da aplicação segue usando
#          event_id, que continua sendo a chave)
#   `seq`  BIGSERIAL monotônico, para carga incremental por marca d'água
#
# Tabelas MUTÁVEIS (vps_tag, vps_card, vps_phase_log, vps_pick_demand…) ficam
# de fora de propósito: uma marca d'água sobre linha que sofre UPDATE avança
# sem levar a alteração, e a carga fica "verde" perdendo dados em silêncio.
_PG_EVENT_SURFACES: tuple[tuple[str, str, bool], ...] = (
    ("vps_event", "event_id", True),
    ("audit_event", "event_id", True),
    ("change_log", "change_id::text", False),   # já tem BIGSERIAL como PK
)


def _pg_contrato_eventos(conn: Any) -> None:
    """Garante `id` e `seq` nas superfícies de evento. Idempotente."""
    for tabela, chave, precisa_seq in _PG_EVENT_SURFACES:
        try:
            if precisa_seq:
                conn.execute(f"ALTER TABLE {tabela} ADD COLUMN IF NOT EXISTS seq BIGSERIAL")
                conn.execute(f"CREATE INDEX IF NOT EXISTS ix_{tabela}_seq ON {tabela}(seq)")
            # `id` é GERADA: não dá para escrever nela por engano, e não existe
            # a chance de divergir da chave natural com o tempo.
            conn.execute(
                f"ALTER TABLE {tabela} ADD COLUMN IF NOT EXISTS id text "
                f"GENERATED ALWAYS AS ({chave}) STORED")
            conn.execute(f"CREATE INDEX IF NOT EXISTS ix_{tabela}_id ON {tabela}(id)")
        except Exception:  # noqa: BLE001
            log.exception("DB: contrato de eventos em %s não pôde ser aplicado (não fatal)", tabela)


def _pg_init_schema() -> None:
    psycopg = _psycopg()
    from psycopg.rows import dict_row
    script = _SCHEMA.read_text(encoding="utf-8")
    with psycopg.connect(get_settings().database_url, autocommit=True, row_factory=dict_row) as conn:
        for stmt in _comandos_sql(script):
            if stmt.upper().startswith("PRAGMA"):
                continue
            conn.execute(_pg_ddl(stmt))
        _pg_contrato_eventos(conn)
        # Gestão de alterações: triggers de log em cada tabela que importa.
        try:
            conn.execute(_CHANGE_LOG.read_text(encoding="utf-8"))
            log.info("DB: gestão de alterações ativa (change_log + triggers)")
        except Exception:  # noqa: BLE001
            log.exception("DB: change_log não pôde ser instalado (não fatal)")
        # TimescaleDB (best-effort): hypertable da série de métricas (time-partition).
        try:
            conn.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
            conn.execute("SELECT create_hypertable('metric_timeseries','time',if_not_exists=>TRUE,migrate_data=>TRUE)")
            log.info("TimescaleDB: hypertable metric_timeseries ativa")
        except Exception as exc:  # noqa: BLE001
            log.info("TimescaleDB indisponível (%s) — metric_timeseries como tabela comum.", str(exc).split(chr(10))[0][:80])


# ── Migrações aditivas ──────────────────────────────────────────────
# schema.sql usa CREATE TABLE IF NOT EXISTS: nao altera tabela que ja existe.
# Coluna nova em base ja criada precisa de ALTER, idempotente por table_info.
_ADD_COLUMNS: list[tuple[str, str, str]] = [
    # (tabela, coluna, definicao)
    ("vps_access", "perfil", "TEXT"),   # perfil operacional (Operations|Supply|Quality|Projects)
]


def _migrate_sqlite(conn: sqlite3.Connection) -> None:
    for tabela, coluna, defn in _ADD_COLUMNS:
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({tabela})").fetchall()}
        if cols and coluna not in cols:
            conn.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {defn}")
            log.info("DB: migração — %s.%s adicionada", tabela, coluna)


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
                _migrate_sqlite(conn)
            finally:
                conn.close()
            log.info("DB: SQLite (%s)", get_settings().db_path)
        _initialized = True


# Quem está agindo, por contexto de requisição. ContextVar e não variável de
# conexão: `set_config` vale por SESSÃO do Postgres, e as conexões aqui são
# por THREAD. O middleware roda numa thread e o handler pode rodar em outra —
# foi por isso que o primeiro teste gravou o log com ator vazio. Guardar no
# contexto (que o FastAPI propaga para a thread do handler) e aplicar na hora
# de pegar a conexão resolve: a variável é definida na conexão que vai escrever.
_ATOR: ContextVar[tuple[str, str]] = ContextVar("vd_ator", default=("", ""))


def set_actor(actor: str | None, origem: str | None = None) -> None:
    """Publica quem está agindo para os triggers de change_log (PostgreSQL)."""
    _ATOR.set((actor or "", origem or ""))


def _aplica_ator(conn) -> None:
    """Sincroniza app.actor/app.origem NESTA conexão, se mudou."""
    alvo = _ATOR.get()
    if getattr(conn, "_vd_ator", None) == alvo:
        return
    try:
        conn.execute("SELECT set_config('app.actor', %s, false)", (alvo[0],))
        conn.execute("SELECT set_config('app.origem', %s, false)", (alvo[1],))
        conn._vd_ator = alvo
    except Exception:  # noqa: BLE001
        pass


def get_connection():
    """Conexão desta thread — conferida antes de entregar.

    POR QUE CONFERIR, E NÃO SÓ CACHEAR

    A conexão é guardada por THREAD e as threads vêm de um pool que o
    `asyncio.to_thread` reusa por horas. Quando o Postgres derruba UMA dessas
    sessões (reinício, timeout ocioso, rede), o objeto morto continuava no
    `_local.conn` daquela thread para sempre: toda requisição que caísse nela
    falhava com "the connection is closed", e as que caíssem nas outras
    funcionavam. O sintoma na tela é um sistema que "às vezes funciona" —
    inferência boa, YOLO respondendo em 200 ms, e mesmo assim erro no frame.
    Foi exatamente esse o defeito dos modos de visão: o modelo nunca esteve em
    causa, quem falhava era a gravação do resultado.

    Trocar uma conexão morta é barato (uma reconexão) e acontece uma vez por
    thread envenenada. Deixá-la no lugar custa a funcionalidade inteira.
    """
    if not _initialized:
        init_db()
    conn = getattr(_local, "conn", None)
    if conn is not None and _use_pg() and not conn.viva():
        try:
            conn.close()
        except Exception:  # noqa: BLE001 - já estava ruim; o que importa é soltar
            pass
        _local.conn = conn = None
        log.warning("DB: sessão Postgres morta nesta thread — reconectando")
    if conn is None:
        conn = _new_pg() if _use_pg() else _new_sqlite()
        _local.conn = conn
    if _use_pg():
        _aplica_ator(conn)
    return conn


def close_db() -> None:
    conn = getattr(_local, "conn", None)
    if conn is not None:
        conn.close()
        _local.conn = None
