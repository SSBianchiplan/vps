"""Repositório: upsert de dimensões e gravação de fatos de inferência.

Cada thread usa sua própria conexão (ver database.py), portanto não há mais um
lock global: o SQLite (WAL + busy_timeout) cuida da concorrência entre conexões.
A gravação de um evento (fato + agregações derivadas) é feita em transação para
ser atômica.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from ..schemas.enums import Mode
from ..schemas.results import InferenceResult
from ..schemas.tasks import TaskConfig
from .database import get_connection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _rule_row(row: Any) -> dict[str, Any]:
    d = dict(row)
    d["condition"] = json.loads(d.pop("condition_json") or "{}")
    d["actions"] = json.loads(d.pop("actions_json") or "[]")
    d["active"] = bool(d.get("active"))
    return d


class Repository:
    """Camada de acesso ao banco."""

    # Cache em processo de dimensões já gravadas — evita 2 writes redundantes
    # (upsert_model + ensure_source) a cada inferência no caminho quente (#6).
    _seen_models: set[str] = set()
    _seen_sources: set[str] = set()

    # ── Dimensões ───────────────────────────────────────────────
    def upsert_source(
        self,
        source_id: str,
        tipo: str,
        resolucao: str | None = None,
        fps_nominal: int | None = None,
        descricao: str | None = None,
    ) -> str:
        get_connection().execute(
            """
            INSERT INTO dim_source(source_id, tipo, resolucao, fps_nominal, descricao, created_at)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(source_id) DO UPDATE SET
                tipo=excluded.tipo, resolucao=excluded.resolucao,
                fps_nominal=excluded.fps_nominal, descricao=excluded.descricao
            """,
            (source_id, tipo, resolucao, fps_nominal, descricao, _now()),
        )
        return source_id

    def ensure_source(self, source_id: str, tipo: str | None = None) -> None:
        """Garante a existência da fonte (sem sobrescrever registro existente).

        Evita IntegrityError de FK ao gravar fact_detection com um source_id que
        ainda não foi registrado explicitamente via POST /sources.
        """
        if source_id in self._seen_sources:      # cache em processo (#6)
            return
        self._seen_sources.add(source_id)
        get_connection().execute(
            """
            INSERT INTO dim_source(source_id, tipo, resolucao, fps_nominal, descricao, created_at)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(source_id) DO NOTHING
            """,
            (source_id, tipo or source_id, None, None, "auto", _now()),
        )

    def upsert_task(self, task: TaskConfig) -> str:
        task_id = task.task_id or _new_id("task")
        params_json = json.dumps(task.params.model_dump(mode="json"), ensure_ascii=False)
        roi_json = json.dumps(task.roi.model_dump(mode="json"), ensure_ascii=False) if task.roi else None
        get_connection().execute(
            """
            INSERT INTO dim_task(task_id, modo, prompt, parametros_json, roi_json, created_at)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(task_id) DO UPDATE SET
                modo=excluded.modo, prompt=excluded.prompt,
                parametros_json=excluded.parametros_json, roi_json=excluded.roi_json
            """,
            (task_id, task.mode.value, task.prompt, params_json, roi_json, _now()),
        )
        return task_id

    def upsert_model(self, nome: str, tipo: str, versao: str | None = None) -> str:
        model_id = f"model_{tipo}_{nome}"
        if model_id in self._seen_models:        # já existe nesta sessão → pula write
            return model_id
        self._seen_models.add(model_id)
        get_connection().execute(
            """
            INSERT INTO dim_model(model_id, nome, tipo, versao)
            VALUES (?,?,?,?)
            ON CONFLICT(model_id) DO UPDATE SET
                nome=excluded.nome, tipo=excluded.tipo, versao=excluded.versao
            """,
            (model_id, nome, tipo, versao),
        )
        return model_id

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        row = get_connection().execute(
            "SELECT * FROM dim_task WHERE task_id=?", (task_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_tasks(self) -> list[dict[str, Any]]:
        rows = get_connection().execute(
            "SELECT * FROM dim_task ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def list_sources(self) -> list[dict[str, Any]]:
        rows = get_connection().execute(
            "SELECT * FROM dim_source ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Fatos ───────────────────────────────────────────────────
    def save_inference(
        self, result: InferenceResult, frame_ref: str | None = None
    ) -> None:
        """Grava FACT_DETECTION e, conforme o modo, FACT_COUNT / FACT_OCR (atômico)."""
        from .. import metrics
        metrics.record(result.pipeline, result.latency_ms)
        from ..integration import publish as _pub
        _pub.publish_event(result)
        from ..vps import bridge as _vps  # ponte Visão→VPS (gênese/verificação do Fio Dourado)
        _vps.on_inference(result)
        from .. import audit  # trilha de rastreabilidade (toda leitura/contagem/detecção/descrição/análise)
        audit.from_inference(result, frame_ref)
        model_id = self.upsert_model(result.model_name, result.model_type.value, result.model_version)
        if result.source_id:
            self.ensure_source(result.source_id)
        result_json = json.dumps(result.result, ensure_ascii=False)

        conn = get_connection()
        conn.execute("BEGIN")
        try:
            conn.execute(
                """
                INSERT INTO fact_detection(
                    detection_id, source_id, task_id, model_id, timestamp,
                    frame_ref, latency_ms, confidence, pipeline, result_json)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    result.detection_id, result.source_id, result.task_id, model_id,
                    result.timestamp, frame_ref, result.latency_ms, result.confidence,
                    result.pipeline, result_json,
                ),
            )

            if result.mode == Mode.CONTAR:
                contagens: dict[str, int] = result.result.get("contagens", {}) or {}
                cruz = int(result.result.get("cruzamentos_linha", 0) or 0)
                ts = result.timestamp
                for classe, qtd in contagens.items():
                    conn.execute(
                        """
                        INSERT INTO fact_count(
                            count_id, task_id, janela_inicio, janela_fim,
                            classe, quantidade, cruzamentos_linha)
                        VALUES (?,?,?,?,?,?,?)
                        """,
                        (_new_id("count"), result.task_id, ts, ts, classe, int(qtd), cruz),
                    )

            elif result.mode == Mode.LER:
                for leitura in result.result.get("leituras", []) or []:
                    conn.execute(
                        """
                        INSERT INTO fact_ocr(
                            ocr_id, detection_id, texto, campo_logico, confidence, bbox_json)
                        VALUES (?,?,?,?,?,?)
                        """,
                        (
                            _new_id("ocr"), result.detection_id,
                            leitura.get("texto"), leitura.get("campo"),
                            leitura.get("confianca"),
                            json.dumps(leitura.get("bbox"), ensure_ascii=False),
                        ),
                    )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    # ── Consultas para export ───────────────────────────────────
    def query_detections(
        self,
        task_id: str | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM fact_detection"
        params: list[Any] = []
        if task_id:
            sql += " WHERE task_id=?"
            params.append(task_id)
        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        rows = get_connection().execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    # ── Timeline de eventos (dashboard) ──────────────────────────
    def query_events(
        self,
        source_id: str | None = None,
        mode: str | None = None,
        since: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """Eventos de inferência enriquecidos com modo/fonte para a timeline.

        Faz LEFT JOIN com dim_task (modo) e dim_source (descrição) para evitar
        N+1 no roteador. Filtros opcionais por fonte, modo e janela temporal.
        """
        sql = (
            "SELECT f.detection_id, f.source_id, f.task_id, f.timestamp, "
            "       f.frame_ref, f.latency_ms, f.confidence, f.pipeline, "
            "       f.result_json, t.modo AS modo, s.descricao AS source_desc, s.tipo AS source_tipo "
            "FROM fact_detection f "
            "LEFT JOIN dim_task t   ON f.task_id = t.task_id "
            "LEFT JOIN dim_source s ON f.source_id = s.source_id "
        )
        clauses: list[str] = []
        params: list[Any] = []
        if source_id:
            clauses.append("f.source_id = ?")
            params.append(source_id)
        if mode:
            clauses.append("t.modo = ?")
            params.append(mode)
        if since:
            clauses.append("f.timestamp >= ?")
            params.append(since)
        if clauses:
            sql += "WHERE " + " AND ".join(clauses) + " "
        sql += "ORDER BY f.timestamp DESC LIMIT ?"
        params.append(limit)
        rows = get_connection().execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def aggregate_overview(self, since: str | None = None) -> dict[str, Any]:
        """Agrega KPIs e séries em SQL (rápido — evita puxar linhas para o cliente).

        Retorna: total de eventos, alertas (heurística por LIKE no result_json),
        série diária de eventos e contagem por modo. Uma janela temporal opcional
        filtra por `since` (ISO-8601).
        """
        conn = get_connection()
        where = "WHERE f.timestamp >= ?" if since else ""
        p: list[Any] = [since] if since else []

        total = conn.execute(
            f"SELECT COUNT(*) AS n FROM fact_detection f {where}", p
        ).fetchone()["n"]

        # Padrões LIKE como parâmetros (evita '%' literal — compatível SQLite/Postgres).
        like_pat = ["%NOK%", "%pessoa%", "%person%", "%alerta%"]
        alerts = conn.execute(
            f"SELECT COUNT(*) AS n FROM fact_detection f {where}"
            + (" AND" if since else " WHERE")
            + " (f.result_json LIKE ? OR f.result_json LIKE ? OR f.result_json LIKE ? OR f.result_json LIKE ?)",
            p + like_pat,
        ).fetchone()["n"]

        by_day = [
            {"day": r["day"], "count": r["n"]}
            for r in conn.execute(
                f"SELECT substr(f.timestamp,1,10) AS day, COUNT(*) AS n "
                f"FROM fact_detection f {where} GROUP BY day ORDER BY day",
                p,
            ).fetchall()
        ]

        by_mode = {
            (r["modo"] or "?"): r["n"]
            for r in conn.execute(
                f"SELECT t.modo AS modo, COUNT(*) AS n "
                f"FROM fact_detection f LEFT JOIN dim_task t ON f.task_id=t.task_id "
                f"{where} GROUP BY t.modo",
                p,
            ).fetchall()
        }

        return {"total_events": total, "alerts": alerts, "by_day": by_day, "by_mode": by_mode}

    # ── AGIR: regras e ações (M5) ────────────────────────────────
    def create_rule(self, task_id: str | None, label: str,
                    condition: dict[str, Any], actions: list[dict[str, Any]]) -> dict[str, Any]:
        rule_id = _new_id("rule")
        get_connection().execute(
            "INSERT INTO dim_action_rule(rule_id, task_id, label, condition_json, actions_json, active, created_at)"
            " VALUES (?,?,?,?,?,1,?)",
            (rule_id, task_id, label,
             json.dumps(condition, ensure_ascii=False), json.dumps(actions, ensure_ascii=False), _now()),
        )
        from .. import audit
        audit.record("DATA", "CREATE", summary=f"regra AGIR criada: {label}", actor="usuário",
                     entity_type="rule", entity_id=rule_id, payload={"condition": condition, "actions": actions})
        return self.get_rule(rule_id)  # type: ignore[return-value]

    def get_rule(self, rule_id: str) -> dict[str, Any] | None:
        row = get_connection().execute(
            "SELECT * FROM dim_action_rule WHERE rule_id=?", (rule_id,)
        ).fetchone()
        return _rule_row(row) if row else None

    def list_rules(self, task_id: str | None = None, only_active: bool = False) -> list[dict[str, Any]]:
        sql = "SELECT * FROM dim_action_rule"
        clauses, p = [], []
        if task_id:
            clauses.append("task_id=?"); p.append(task_id)
        if only_active:
            clauses.append("active=1")
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at DESC"
        return [_rule_row(r) for r in get_connection().execute(sql, p).fetchall()]

    def delete_rule(self, rule_id: str) -> bool:
        cur = get_connection().execute("DELETE FROM dim_action_rule WHERE rule_id=?", (rule_id,))
        if cur.rowcount > 0:
            from .. import audit
            audit.record("DATA", "DELETE", summary=f"regra AGIR removida: {rule_id}",
                         severity="alerta", actor="usuário", entity_type="rule", entity_id=rule_id)
        return cur.rowcount > 0

    def set_rule_active(self, rule_id: str, active: bool) -> None:
        get_connection().execute(
            "UPDATE dim_action_rule SET active=? WHERE rule_id=?", (1 if active else 0, rule_id)
        )
        from .. import audit
        audit.record("DATA", "UPDATE", summary=f"regra {rule_id} {'ativada' if active else 'desativada'}",
                     actor="usuário", entity_type="rule", entity_id=rule_id, payload={"active": active})

    def record_action(self, rule_id: str | None, detection_id: str | None, task_id: str | None,
                      action_type: str, target: str | None, payload: Any,
                      status: str, http_status: int | None = None,
                      error_message: str | None = None, retry_count: int = 0) -> str:
        action_id = _new_id("act")
        get_connection().execute(
            "INSERT INTO fact_action(action_id, rule_id, detection_id, task_id, timestamp, action_type,"
            " target, payload_json, status, http_status, error_message, retry_count, executed_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (action_id, rule_id, detection_id, task_id, _now(), action_type, target,
             json.dumps(payload, ensure_ascii=False) if payload is not None else None,
             status, http_status, error_message, retry_count, _now()),
        )
        from .. import audit
        audit.record("ACTION", (action_type or "ACTION").upper(),
                     summary=f"{action_type} → {target or ''} ({status})",
                     severity="ok" if status == "success" else "nok" if status else "info",
                     actor="agir", entity_type="action", entity_id=action_id,
                     correlation_id=detection_id, payload={"http_status": http_status, "error": error_message})
        return action_id

    def list_actions(self, status: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        sql = "SELECT * FROM fact_action"
        p: list[Any] = []
        if status:
            sql += " WHERE status=?"; p.append(status)
        sql += " ORDER BY timestamp DESC LIMIT ?"; p.append(limit)
        return [dict(r) for r in get_connection().execute(sql, p).fetchall()]

    def get_action(self, action_id: str) -> dict[str, Any] | None:
        row = get_connection().execute("SELECT * FROM fact_action WHERE action_id=?", (action_id,)).fetchone()
        return dict(row) if row else None

    def update_action(self, action_id: str, status: str, http_status: int | None,
                      error_message: str | None, retry_count: int) -> None:
        get_connection().execute(
            "UPDATE fact_action SET status=?, http_status=?, error_message=?, retry_count=?, executed_at=?"
            " WHERE action_id=?",
            (status, http_status, error_message, retry_count, _now(), action_id),
        )

    # ── Gravações (fact_recording) ──────────────────────────────
    def add_recording(self, rec_id: str, source_id: str, timestamp: str, mode: str,
                      trigger: str, classes: dict[str, int], image_uri: str) -> None:
        get_connection().execute(
            "INSERT INTO fact_recording(rec_id, source_id, timestamp, mode, trigger, classes_json, image_uri)"
            " VALUES (?,?,?,?,?,?,?)",
            (rec_id, source_id, timestamp, mode, trigger,
             json.dumps(classes, ensure_ascii=False), image_uri),
        )
        from .. import audit
        audit.record("RECORDING", "RECORD", summary=f"gravação {trigger or ''} ({mode or ''})",
                     actor="sistema", source_id=source_id, entity_type="recording",
                     entity_id=rec_id, event_ts=str(timestamp), payload={"image_uri": image_uri, "classes": classes})

    def list_recordings(self, source_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        sql = "SELECT * FROM fact_recording"
        p: list[Any] = []
        if source_id:
            sql += " WHERE source_id=?"; p.append(source_id)
        sql += " ORDER BY timestamp DESC LIMIT ?"; p.append(limit)
        out = []
        for r in get_connection().execute(sql, p).fetchall():
            d = dict(r)
            d["classes"] = json.loads(d.pop("classes_json") or "{}")
            d["id"] = d.pop("rec_id")
            d["timestamp"] = str(d["timestamp"])
            out.append(d)
        return out

    # ── Série temporal de rede/buffer (metric_timeseries) ────────
    def record_metric(self, source_id: str, latency_ms: float | None, jitter_ms: float | None,
                      packet_loss: float | None, buffer_pct: float | None,
                      fps: float | None, throughput_kbps: float | None) -> None:
        get_connection().execute(
            "INSERT INTO metric_timeseries(time, source_id, latency_ms, jitter_ms, packet_loss,"
            " buffer_pct, fps, throughput_kbps) VALUES (?,?,?,?,?,?,?,?)",
            (_now(), source_id, latency_ms, jitter_ms, packet_loss, buffer_pct, fps, throughput_kbps),
        )

    def query_metrics(self, source_id: str | None = None, limit: int = 120) -> list[dict[str, Any]]:
        sql = "SELECT * FROM metric_timeseries"
        p: list[Any] = []
        if source_id:
            sql += " WHERE source_id=?"; p.append(source_id)
        sql += " ORDER BY time DESC LIMIT ?"; p.append(limit)
        rows = [dict(r) for r in get_connection().execute(sql, p).fetchall()]
        for r in rows:
            r["time"] = str(r["time"])
        return list(reversed(rows))  # ordem cronológica p/ o gráfico

    def list_event_sources(self) -> list[dict[str, Any]]:
        """Fontes distintas que já geraram eventos (para filtros do dashboard)."""
        rows = get_connection().execute(
            "SELECT DISTINCT f.source_id AS source_id, s.tipo AS tipo, s.descricao AS descricao "
            "FROM fact_detection f LEFT JOIN dim_source s ON f.source_id = s.source_id "
            "WHERE f.source_id IS NOT NULL ORDER BY f.source_id"
        ).fetchall()
        return [dict(r) for r in rows]


repository = Repository()
