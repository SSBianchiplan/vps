"""Inventário e status das bases de dados/armazenamentos do sistema (#4).

Cada "base" reporta: tipo, status (ok/warn/off), detalhe e métricas. Tudo
best-effort — uma base indisponível não derruba o relatório.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import get_settings
from .db.database import _use_pg, get_connection


def _motor() -> str:
    """O motor de verdade, perguntado ao runtime — nunca escrito à mão.

    Estes três painéis diziam "SQLite" desde antes da migração e continuaram
    dizendo depois dela: quem abria a tela de Bases concluía que o Fio Dourado e
    a trilha de auditoria rodavam em SQLite, enquanto as duas já estavam em
    Postgres. Um rótulo fixo sobre um fato que muda vira mentira na primeira
    migração; perguntar custa uma chamada de função.
    """
    return "PostgreSQL" if _use_pg() else "SQLite"


def _grupo_runtime() -> str:
    return f"Runtime ({_motor()})"



def _count(sql: str) -> int | None:
    try:
        row = get_connection().execute(sql).fetchone()
        return int(dict(row)["n"]) if row else 0
    except Exception:  # noqa: BLE001
        return None


def _primary() -> dict[str, Any]:
    s = get_settings()
    pg = _use_pg()
    ev = _count("SELECT COUNT(*) AS n FROM fact_detection")
    return {
        "key": "primary", "name": "Banco principal · Visão CV (star schema)",
        "kind": "PostgreSQL/TimescaleDB" if pg else "SQLite",
        "status": "ok" if ev is not None else "off",
        "detail": (s.database_url.split("@")[-1] if pg and s.database_url else s.db_path),
        "metrics": {"inferências": ev, "gravações": _count("SELECT COUNT(*) AS n FROM fact_recording"),
                    "ações": _count("SELECT COUNT(*) AS n FROM fact_action"),
                    "regras": _count("SELECT COUNT(*) AS n FROM dim_action_rule"),
                    "modelos": _count("SELECT COUNT(*) AS n FROM dim_model")},
        # As consultas que produzem cada metrica: a tela mostra o SQL ao lado do
        # numero, para o numero ser conferivel em vez de acreditado.
        "sql": {
            "inferências": "SELECT COUNT(*) FROM fact_detection",
            "por pipeline (24h)": "SELECT pipeline, COUNT(*) FROM fact_detection WHERE timestamp > datetime('now','-1 day') GROUP BY pipeline",
            "gravações": "SELECT COUNT(*) FROM fact_recording",
            "modelos": "SELECT * FROM dim_model",
        },
    }


def _vps_runtime() -> dict[str, Any]:
    """VPS Fio Dourado AO VIVO (event store + projeções no banco de runtime)."""
    ev = _count("SELECT COUNT(*) AS n FROM vps_event")
    return {"key": "vps_rt", "name": "VPS · Fio Dourado (runtime)", "kind": _motor() + " · event-sourced",
            "status": "ok" if ev is not None else "off",
            "detail": "cockpit ao vivo: event store + projeções (Tag-ID) — distinto do teste_sistema (PG)",
            "metrics": {"eventos": ev, "tags": _count("SELECT COUNT(*) AS n FROM vps_tag"),
                        "vínculos": _count("SELECT COUNT(*) AS n FROM vps_lineage"),
                        "projetos": _count("SELECT COUNT(*) AS n FROM vps_project"),
                        "cards": _count("SELECT COUNT(*) AS n FROM vps_card"),
                        "ocorrências": _count("SELECT COUNT(*) AS n FROM vps_occurrence"),
                        "pendências abertas": _count("SELECT COUNT(*) AS n FROM vps_pending WHERE cleared_ts IS NULL"),
                        "programações APS": _count("SELECT COUNT(DISTINCT scenario_id) AS n FROM vps_schedule")},
            "sql": {
                "eventos por ação": "SELECT action, COUNT(*) FROM vps_event GROUP BY action ORDER BY 2 DESC",
                "tags por estado": "SELECT entity_type, state, COUNT(*) FROM vps_tag GROUP BY 1,2",
                "linhagem": "SELECT relation, COUNT(*) FROM vps_lineage GROUP BY relation",
                "fio de uma tag": "SELECT * FROM vps_event WHERE tag_id = :tag ORDER BY event_ts",
                "cards por projeto": "SELECT p.code, c.state, COUNT(*) FROM vps_card c JOIN vps_project p USING(project_id) GROUP BY 1,2",
            }}


def _audit_runtime() -> dict[str, Any]:
    """Trilha de rastreabilidade total AO VIVO (audit_event no banco de runtime)."""
    n = _count("SELECT COUNT(*) AS n FROM audit_event")
    return {"key": "audit_rt", "name": "Trilha de auditoria (runtime)", "kind": _motor() + " · append-only",
            "status": "ok" if n is not None else "off",
            "detail": "rastreabilidade total (audit_event) — espelha no PG visiondesk_audit",
            "metrics": {"eventos": n, "categorias": _count("SELECT COUNT(DISTINCT category) AS n FROM audit_event"),
                        "negativas RBAC": _count("SELECT COUNT(*) AS n FROM audit_event WHERE action='RBAC_DENIED'"),
                        "rodadas E2E": _count("SELECT COUNT(DISTINCT correlation_id) AS n FROM audit_event WHERE category='E2E'"),
                        "eventos VPS": _count("SELECT COUNT(*) AS n FROM audit_event WHERE category='VPS'")},
            "sql": {
                "por categoria": "SELECT category, COUNT(*) FROM audit_event GROUP BY category ORDER BY 2 DESC",
                "últimas 24h": "SELECT * FROM audit_event WHERE event_ts > datetime('now','-1 day') ORDER BY event_ts DESC",
                "negativas de acesso": "SELECT event_ts, actor, summary FROM audit_event WHERE action='RBAC_DENIED' ORDER BY event_ts DESC",
                "uma rodada E2E": "SELECT * FROM audit_event WHERE correlation_id = :run_id ORDER BY event_ts",
            }}


def _timescale() -> dict[str, Any]:
    if not _use_pg():
        return {"key": "timescale", "name": "TimescaleDB (séries temporais)", "kind": "extensão Postgres",
                "status": "off", "detail": "ativa só no backend Postgres", "metrics": {}}
    active, n = False, _count("SELECT COUNT(*) AS n FROM metric_timeseries")
    try:
        r = get_connection().execute(
            "SELECT COUNT(*) AS n FROM timescaledb_information.hypertables WHERE hypertable_name='metric_timeseries'"
        ).fetchone()
        active = bool(dict(r)["n"]) if r else False
    except Exception:  # noqa: BLE001
        active = False
    return {"key": "timescale", "name": "TimescaleDB (métricas rede/buffer)", "kind": "hypertable",
            "status": "ok" if active else "warn",
            "detail": "hypertable metric_timeseries ativa" if active else "tabela comum (extensão ausente)",
            "metrics": {"amostras": n}}


def _object_store() -> dict[str, Any]:
    s = get_settings()
    rec_dir = Path(s.db_path).parent / "recordings"
    local_n = len(list(rec_dir.glob("*.jpg"))) if rec_dir.exists() else 0
    if s.s3_endpoint:
        try:
            import boto3  # type: ignore
            c = boto3.client("s3", endpoint_url=s.s3_endpoint)
            objs = c.list_objects_v2(Bucket=s.s3_bucket).get("Contents", [])
            return {"key": "objstore", "name": "Object store (frames/gravações)", "kind": "MinIO/S3",
                    "status": "ok", "detail": f"{s.s3_endpoint} · bucket {s.s3_bucket}",
                    "metrics": {"objetos": len(objs), "local_cache": local_n}}
        except Exception as exc:  # noqa: BLE001
            return {"key": "objstore", "name": "Object store (frames/gravações)", "kind": "MinIO/S3",
                    "status": "warn", "detail": f"S3 inacessível ({str(exc)[:40]}) — usando local", "metrics": {"local": local_n}}
    return {"key": "objstore", "name": "Armazenamento de frames/gravações", "kind": "Filesystem local",
            "status": "ok", "detail": str(rec_dir), "metrics": {"arquivos": local_n}}


def _mqtt() -> dict[str, Any]:
    s = get_settings()
    if not s.mqtt_url:
        return {"key": "mqtt", "name": "Broker de eventos (MES/SCADA)", "kind": "MQTT",
                "status": "off", "detail": "não configurado (VISIONDESK_MQTT_URL)", "metrics": {}}
    from .integration import publish
    connected = publish._mqtt() is not None
    return {"key": "mqtt", "name": "Broker de eventos (MES/SCADA)", "kind": "MQTT",
            "status": "ok" if connected else "warn",
            "detail": f"{s.mqtt_url} · tópico {s.mqtt_topic}" + ("" if connected else " (sem conexão)"),
            "metrics": {}}


def _json_stores() -> list[dict[str, Any]]:
    s = get_settings()
    base = Path(s.db_path).parent
    out = []
    # config WhatsApp
    wa = base / "whatsapp.json"
    out.append({"key": "whatsapp", "name": "Config Notificações (WhatsApp)", "kind": "JSON (gitignored)",
                "status": "ok" if wa.exists() else "warn", "detail": "token só no backend",
                "metrics": {"configurado": wa.exists()}})
    # câmeras salvas
    cams = base / "cameras.json"
    n = 0
    try:
        from .discovery import saved
        n = len(saved.list_public())
    except Exception:  # noqa: BLE001
        pass
    out.append({"key": "cameras", "name": "Câmeras salvas (credenciais)", "kind": "JSON (gitignored)",
                "status": "ok" if n else "warn", "detail": str(cams), "metrics": {"câmeras": n}})
    # bancos de anomalia (perfis normais)
    adir = base / "anomaly"
    an = len(list(adir.glob("*.npz"))) if adir.exists() else 0
    out.append({"key": "anomaly", "name": "Bancos de anomalia (normais)", "kind": "NumPy .npz",
                "status": "ok" if an else "warn", "detail": "PatchCore-lite (embeddings)",
                "metrics": {"perfis": an}})
    # config de auto-gravar por detecção (classes-alvo + cooldown)
    rec = base / "recording.json"
    rcfg: dict[str, Any] = {}
    try:
        from . import recording
        rcfg = recording.load_config()
    except Exception:  # noqa: BLE001
        pass
    out.append({"key": "recording", "name": "Config Auto-gravar (detecção)", "kind": "JSON",
                "status": "ok" if rcfg.get("enabled") else "warn",
                "detail": f"classes: {', '.join(rcfg.get('classes', [])) or '—'}",
                "metrics": {"ativo": bool(rcfg.get("enabled")), "cooldown_s": rcfg.get("cooldown_s")}})
    return out


def _mediamtx() -> dict[str, Any]:
    s = get_settings()
    if not s.restream_base:
        return {"key": "mediamtx", "name": "Media server (WebRTC/HLS fan-out)", "kind": "MediaMTX",
                "status": "off", "detail": "não configurado (VISIONDESK_RESTREAM_BASE)", "metrics": {}}
    import socket
    from urllib.parse import urlparse
    u = urlparse(s.restream_base)
    reachable = False
    try:
        with socket.create_connection((u.hostname or "localhost", u.port or 8889), timeout=0.6):
            reachable = True
    except Exception:  # noqa: BLE001
        reachable = False
    return {"key": "mediamtx", "name": "Media server (WebRTC/HLS fan-out)", "kind": "MediaMTX",
            "status": "ok" if reachable else "warn",
            "detail": s.restream_base + (" · WHEP/HLS" if reachable else " (inacessível)"),
            "metrics": {"alcançável": reachable}}


_TS_SCHEMAS = {
    "vps_core": "Event Store + linhagem (verdade física)",
    "vps_md": "Master data (SCD2)",
    "vps_proj": "Projeções (estado/leitura · CQRS)",
    "vps_aps": "Planejamento / scheduling (APS)",
    "vps_recon": "Reconciliação (físico × ERP/MES)",
    "glx": "Semântico / Gold (BI)",
    "vps_stg": "Staging / migração",
    "vps_plan": "Planejamento (projetos/cards)",
}


def _vps_test_system() -> list[dict[str, Any]]:
    """Projeto 'Teste Sistema' (PostgreSQL): 1 base por schema, com tabelas/linhas."""
    try:
        import psycopg  # type: ignore
        conn = psycopg.connect("dbname=teste_sistema", connect_timeout=2)
    except Exception:  # noqa: BLE001
        return [{"key": "vps_teste", "name": "VPS · Teste Sistema (PostgreSQL)", "kind": "PostgreSQL",
                 "status": "off", "detail": "banco 'teste_sistema' indisponível (rode scripts/seed_teste_sistema.py)", "metrics": {}}]
    out: list[dict[str, Any]] = []
    try:
        cur = conn.cursor()
        for sch, desc in _TS_SCHEMAS.items():
            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=%s AND table_type='BASE TABLE'", (sch,))
            tabs = [t[0] for t in cur.fetchall() if not t[0].startswith("vps_event_")]
            total = 0
            for tn in tabs:
                cur.execute(f'SELECT count(*) FROM {sch}."{tn}"')
                total += int(cur.fetchone()[0])
            out.append({"key": f"ts_{sch}", "name": f"Teste Sistema · {sch}", "kind": "PostgreSQL schema",
                        "status": "ok" if total else "warn", "detail": desc,
                        "metrics": {"tabelas": len(tabs), "linhas": total}})
    finally:
        conn.close()
    return out


def test_system_inventory() -> dict[str, Any]:
    """Inventário do projeto 'Teste Sistema': tabelas/linhas por schema + relacionamentos."""
    try:
        import psycopg  # type: ignore
        conn = psycopg.connect("dbname=teste_sistema", connect_timeout=2)
    except Exception:  # noqa: BLE001
        return {"available": False, "message": "banco 'teste_sistema' indisponível"}
    try:
        cur = conn.cursor()
        schemas: dict[str, list[dict[str, Any]]] = {}
        total_tables = total_rows = 0
        for sch, desc in _TS_SCHEMAS.items():
            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=%s AND table_type='BASE TABLE' ORDER BY table_name", (sch,))
            tabs = [t[0] for t in cur.fetchall() if not t[0].startswith("vps_event_")]
            rows = []
            for tn in tabs:
                cur.execute(f'SELECT count(*) FROM {sch}."{tn}"')
                n = int(cur.fetchone()[0]); rows.append({"name": tn, "rows": n})
                total_rows += n
            total_tables += len(tabs)
            schemas[sch] = {"desc": desc, "tables": rows}  # type: ignore[assignment]

        def grp(sql: str) -> list[dict[str, Any]]:
            cur.execute(sql)
            return [{"k": r[0], "n": int(r[1])} for r in cur.fetchall()]

        rel = {
            "por_tipo": grp("SELECT entity_type, count(*) FROM vps_proj.vps_dim_tag GROUP BY 1 ORDER BY 2 DESC"),
            "por_estado": grp("SELECT current_state, count(*) FROM vps_proj.vps_dim_tag GROUP BY 1 ORDER BY 2 DESC"),
            "linhagem": grp("SELECT relation, count(*) FROM vps_core.vps_lineage GROUP BY 1 ORDER BY 2 DESC"),
            "reconciliacao": grp("SELECT status, count(*) FROM vps_recon.vps_reconciliation GROUP BY 1 ORDER BY 2 DESC"),
            "eventos_top": grp("SELECT action, count(*) FROM vps_core.vps_event GROUP BY 1 ORDER BY 2 DESC LIMIT 8"),
        }
        ops = grp("SELECT 'OPs', count(*) FROM vps_proj.vps_dim_tag WHERE entity_type='OP'")
    finally:
        conn.close()
    return {"available": True, "db": "teste_sistema", "schemas": schemas, "relationships": rel,
            "totals": {"schemas": len(_TS_SCHEMAS), "tables": total_tables, "rows": total_rows, "ops": ops[0]["n"] if ops else 0}}


def _audit_pg() -> dict[str, Any]:
    from .audit_pg import status as _s
    return _s()


# Agrupamento por categoria (p/ o módulo Bases listar organizado).
_GROUPS = {
    "primary": _grupo_runtime(), "vps_rt": _grupo_runtime(), "audit_rt": _grupo_runtime(),
    "audit_pg": "PostgreSQL", "timescale": "PostgreSQL",
    "objstore": "Infraestrutura", "mqtt": "Infraestrutura", "mediamtx": "Infraestrutura",
    "whatsapp": "Config & stores", "cameras": "Config & stores",
    "anomaly": "Config & stores", "recording": "Config & stores",
}
_GROUP_ORDER = [_grupo_runtime(), "PostgreSQL", "Infraestrutura", "Config & stores"]


def status() -> dict[str, Any]:
    bases = [_primary(), _vps_runtime(), _audit_runtime(),
             _timescale(), _object_store(), _mqtt(), _mediamtx(),
             *_json_stores(), _audit_pg(), *_vps_test_system()]
    for b in bases:
        b["group"] = _GROUPS.get(b["key"], "PostgreSQL" if b["key"].startswith("ts_") else "Outras")
    ok = sum(1 for b in bases if b["status"] == "ok")
    return {"bases": bases, "resumo": {"total": len(bases), "ok": ok},
            "groups": _GROUP_ORDER}
