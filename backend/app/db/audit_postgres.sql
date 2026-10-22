-- ═════════════════════════════════════════════════════════════════════
-- VisionDesk — Trilha de auditoria / rastreabilidade total (PostgreSQL).
-- Base: visiondesk_audit · schema: audit. Aplicação IDEMPOTENTE (reconfigura).
-- Espelha audit_event do runtime SQLite. Append-only (imutável) + partições.
-- ═════════════════════════════════════════════════════════════════════
CREATE SCHEMA IF NOT EXISTS audit;

-- EVENT STORE de auditoria — grão = 1 ação do sistema (append-only)
CREATE TABLE IF NOT EXISTS audit.audit_event (
    event_seq      bigint      GENERATED ALWAYS AS IDENTITY,
    event_id       text        NOT NULL,
    event_ts       timestamptz NOT NULL,
    category       text        NOT NULL,   -- INFERENCE|CAMERA|DATA|ACTION|RECORDING|VPS|MONITOR|SYSTEM
    action         text        NOT NULL,   -- READ|COUNT|DETECT|DESCRIBE|ANALYZE|CREATE|UPDATE|DELETE|...
    severity       text        NOT NULL DEFAULT 'info',
    actor          text,
    source_id      text,                    -- câmera/fonte (vínculo c/ câmeras)
    entity_type    text,
    entity_id      text,
    summary        text,
    correlation_id text,
    payload_json   text,
    ingested_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (event_id, event_ts)
) PARTITION BY RANGE (event_ts);

-- `id` para consumidores que usam essa convenção (lakehouse/BI). É coluna
-- GERADA a partir da chave natural: espelha event_id sem poder divergir dele.
-- Sem ela, uma carga que valida "id não nulo" falha com
-- `column "id" does not exist` — foi o que aconteceu na carga 123 do
-- pipe:visiondesk_eventos. `event_seq` já servia de marca d'água.
ALTER TABLE audit.audit_event ADD COLUMN IF NOT EXISTS id text GENERATED ALWAYS AS (event_id) STORED;

-- Partições mensais (cobertura corrente) + default (catch-all).
CREATE TABLE IF NOT EXISTS audit.audit_event_2026m06 PARTITION OF audit.audit_event FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
CREATE TABLE IF NOT EXISTS audit.audit_event_2026m07 PARTITION OF audit.audit_event FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
CREATE TABLE IF NOT EXISTS audit.audit_event_2026m08 PARTITION OF audit.audit_event FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');
CREATE TABLE IF NOT EXISTS audit.audit_event_2026m09 PARTITION OF audit.audit_event FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');
CREATE TABLE IF NOT EXISTS audit.audit_event_default  PARTITION OF audit.audit_event DEFAULT;

-- Índices de leitura (timeline / filtros).
CREATE INDEX IF NOT EXISTS ix_audit_ts     ON audit.audit_event (event_ts DESC);
CREATE INDEX IF NOT EXISTS ix_audit_cat_ts ON audit.audit_event (category, event_ts DESC);
CREATE INDEX IF NOT EXISTS ix_audit_src_ts ON audit.audit_event (source_id, event_ts DESC);
CREATE INDEX IF NOT EXISTS ix_audit_entity ON audit.audit_event (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS ix_audit_corr   ON audit.audit_event (correlation_id);

-- Imutabilidade: proíbe UPDATE/DELETE (correção = evento compensatório).
CREATE OR REPLACE FUNCTION audit.fn_append_only() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'audit_event é append-only: % proibido.', TG_OP;
END; $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_audit_immutable ON audit.audit_event;
CREATE TRIGGER trg_audit_immutable BEFORE UPDATE OR DELETE ON audit.audit_event
  FOR EACH ROW EXECUTE FUNCTION audit.fn_append_only();

-- View de conveniência: timeline recente legível.
CREATE OR REPLACE VIEW audit.v_recent AS
  SELECT event_ts, category, action, severity, actor, source_id, entity_type, entity_id, summary
  FROM audit.audit_event ORDER BY event_ts DESC LIMIT 500;

-- Agregado por categoria (BI rápido).
CREATE OR REPLACE VIEW audit.v_by_category AS
  SELECT category, count(*) AS eventos,
         count(*) FILTER (WHERE severity IN ('alerta','nok','warn')) AS alertas,
         max(event_ts) AS ultimo
  FROM audit.audit_event GROUP BY category ORDER BY eventos DESC;
