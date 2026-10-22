-- ═══════════════════════════════════════════════════════════════════
-- VPS — DDL PostgreSQL (VPS_DB_PostgreSQL_Migracao.md). Idempotente.
-- 8 schemas: vps_core (verdade) · vps_md (SCD2) · vps_proj · vps_aps
--            vps_recon · glx (gold) · vps_stg (migração)
-- ═══════════════════════════════════════════════════════════════════
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE SCHEMA IF NOT EXISTS vps_core;
CREATE SCHEMA IF NOT EXISTS vps_md;
CREATE SCHEMA IF NOT EXISTS vps_proj;
CREATE SCHEMA IF NOT EXISTS vps_aps;
CREATE SCHEMA IF NOT EXISTS vps_recon;
CREATE SCHEMA IF NOT EXISTS glx;
CREATE SCHEMA IF NOT EXISTS vps_stg;

-- ── Event Store (append-only, particionado por mês) ────────────────
CREATE TABLE IF NOT EXISTS vps_core.vps_event (
  event_id       uuid        NOT NULL DEFAULT gen_random_uuid(),
  event_seq      bigint      GENERATED ALWAYS AS IDENTITY,
  tag_id         text        NOT NULL,
  action         text        NOT NULL,
  phase          text,
  owner          text        NOT NULL,
  operator_id    text,
  station_id     text,
  model_name     text,
  model_version  text,
  confidence     numeric(5,4),
  image_uri      text,
  payload        jsonb       NOT NULL DEFAULT '{}'::jsonb,
  vision         jsonb,
  recon_status   text        CHECK (recon_status IN ('MATCHED','PENDING','DIVERGENT')),
  recon_erp_doc  text,
  compensates_id uuid,
  event_ts       timestamptz NOT NULL,
  ingested_ts    timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_vps_event PRIMARY KEY (event_id, event_ts)
) PARTITION BY RANGE (event_ts);

CREATE TABLE IF NOT EXISTS vps_core.vps_event_2026m06 PARTITION OF vps_core.vps_event FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
CREATE TABLE IF NOT EXISTS vps_core.vps_event_2026m07 PARTITION OF vps_core.vps_event FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
CREATE TABLE IF NOT EXISTS vps_core.vps_event_2026m08 PARTITION OF vps_core.vps_event FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');
CREATE TABLE IF NOT EXISTS vps_core.vps_event_default PARTITION OF vps_core.vps_event DEFAULT;

CREATE INDEX IF NOT EXISTS ix_event_tag     ON vps_core.vps_event (tag_id, event_ts);
CREATE INDEX IF NOT EXISTS ix_event_action  ON vps_core.vps_event (action);
CREATE INDEX IF NOT EXISTS ix_event_recon   ON vps_core.vps_event (recon_status) WHERE recon_status IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_event_comp    ON vps_core.vps_event (compensates_id) WHERE compensates_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_event_payload ON vps_core.vps_event USING gin (payload);

CREATE OR REPLACE FUNCTION vps_core.fn_append_only() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'vps_event é append-only: % proibido. Use evento compensatório (VPS_15).', TG_OP;
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS trg_event_immutable ON vps_core.vps_event;
CREATE TRIGGER trg_event_immutable BEFORE UPDATE OR DELETE ON vps_core.vps_event
  FOR EACH ROW EXECUTE FUNCTION vps_core.fn_append_only();

-- ── Linhagem ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vps_core.vps_lineage (
  edge_id       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  parent_tag_id text NOT NULL,
  child_tag_id  text NOT NULL,
  relation      text NOT NULL,
  created_ts    timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_lineage UNIQUE (parent_tag_id, child_tag_id, relation)
);
CREATE INDEX IF NOT EXISTS ix_lineage_parent ON vps_core.vps_lineage (parent_tag_id);
CREATE INDEX IF NOT EXISTS ix_lineage_child  ON vps_core.vps_lineage (child_tag_id);

-- ── Projeção de estado (CQRS) ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS vps_proj.vps_dim_tag (
  tag_pk        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  segment       text NOT NULL,
  entity_type   text NOT NULL,
  natural_key   text NOT NULL,
  instance      text NOT NULL DEFAULT '01',
  tag_id        text GENERATED ALWAYS AS ('VPS:'||segment||':'||entity_type||':'||natural_key||':'||instance) STORED,
  parent_tag_id text,
  template_id   text,
  current_phase text,
  current_state text NOT NULL DEFAULT 'BOUND'
                CHECK (current_state IN ('CAPTURED','RESOLVED','BOUND','IN_PROCESS','EXCEPTION','COMPLETED','ARCHIVED')),
  is_blocked    boolean NOT NULL DEFAULT false,
  recon_status  text,
  created_ts    timestamptz NOT NULL DEFAULT now(),
  updated_ts    timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_dim_tag UNIQUE (tag_id)
);
CREATE INDEX IF NOT EXISTS ix_tag_state  ON vps_proj.vps_dim_tag (current_state);
CREATE INDEX IF NOT EXISTS ix_tag_parent ON vps_proj.vps_dim_tag (parent_tag_id);

-- ── Master data (SCD2) ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vps_md.vps_dim_operator (
  sk bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  operator_id text NOT NULL, nome text NOT NULL, matricula text, badge_token text,
  role text NOT NULL, stations text[], skills text[], shift text,
  status text NOT NULL DEFAULT 'ATIVO' CHECK (status IN ('ATIVO','INATIVO')),
  owner text NOT NULL DEFAULT 'MasterData',
  valid_from timestamptz NOT NULL DEFAULT now(), valid_to timestamptz, is_current boolean NOT NULL DEFAULT true);
CREATE UNIQUE INDEX IF NOT EXISTS uq_operator_current ON vps_md.vps_dim_operator (operator_id) WHERE is_current;

CREATE TABLE IF NOT EXISTS vps_md.vps_dim_station (
  sk bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  station_id text NOT NULL, nome text, area text, segment text,
  status text NOT NULL DEFAULT 'ATIVO', owner text NOT NULL DEFAULT 'Operations',
  valid_from timestamptz NOT NULL DEFAULT now(), valid_to timestamptz, is_current boolean NOT NULL DEFAULT true);
CREATE UNIQUE INDEX IF NOT EXISTS uq_station_current ON vps_md.vps_dim_station (station_id) WHERE is_current;

CREATE TABLE IF NOT EXISTS vps_md.vps_dim_item (
  sk bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  item_key text NOT NULL, descricao text, familia text, uom text,
  status text NOT NULL DEFAULT 'ATIVO', owner text NOT NULL DEFAULT 'MasterData',
  valid_from timestamptz NOT NULL DEFAULT now(), valid_to timestamptz, is_current boolean NOT NULL DEFAULT true);
CREATE UNIQUE INDEX IF NOT EXISTS uq_item_current ON vps_md.vps_dim_item (item_key) WHERE is_current;

CREATE TABLE IF NOT EXISTS vps_md.vps_dim_client (
  sk bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  client_key text NOT NULL, nome text, segmento_cli text,
  status text NOT NULL DEFAULT 'ATIVO', owner text NOT NULL DEFAULT 'Sales',
  valid_from timestamptz NOT NULL DEFAULT now(), valid_to timestamptz, is_current boolean NOT NULL DEFAULT true);
CREATE UNIQUE INDEX IF NOT EXISTS uq_client_current ON vps_md.vps_dim_client (client_key) WHERE is_current;

CREATE TABLE IF NOT EXISTS vps_md.vps_dim_resource (
  sk bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  resource_key text NOT NULL, nome text, tipo text, capacidade numeric, calendario text,
  status text NOT NULL DEFAULT 'ATIVO', owner text NOT NULL DEFAULT 'Operations',
  valid_from timestamptz NOT NULL DEFAULT now(), valid_to timestamptz, is_current boolean NOT NULL DEFAULT true);
CREATE UNIQUE INDEX IF NOT EXISTS uq_resource_current ON vps_md.vps_dim_resource (resource_key) WHERE is_current;

CREATE TABLE IF NOT EXISTS vps_md.vps_dim_shift (
  sk bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  shift_key text NOT NULL, nome text, inicio time, fim time, dias text[],
  status text NOT NULL DEFAULT 'ATIVO', owner text NOT NULL DEFAULT 'Operations',
  valid_from timestamptz NOT NULL DEFAULT now(), valid_to timestamptz, is_current boolean NOT NULL DEFAULT true);
CREATE UNIQUE INDEX IF NOT EXISTS uq_shift_current ON vps_md.vps_dim_shift (shift_key) WHERE is_current;

CREATE TABLE IF NOT EXISTS vps_md.vps_dim_model (
  sk bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  model_name text NOT NULL, model_version text NOT NULL, modo text, min_confidence numeric(5,4),
  status text NOT NULL DEFAULT 'ATIVO', owner text NOT NULL DEFAULT 'IT',
  valid_from timestamptz NOT NULL DEFAULT now(), valid_to timestamptz, is_current boolean NOT NULL DEFAULT true);
CREATE UNIQUE INDEX IF NOT EXISTS uq_model_current ON vps_md.vps_dim_model (model_name, model_version) WHERE is_current;

CREATE TABLE IF NOT EXISTS vps_md.vps_dim_segment (
  sk bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  segment text NOT NULL, descricao text,
  status text NOT NULL DEFAULT 'ATIVO', owner text NOT NULL DEFAULT 'Engineering',
  valid_from timestamptz NOT NULL DEFAULT now(), valid_to timestamptz, is_current boolean NOT NULL DEFAULT true);
CREATE UNIQUE INDEX IF NOT EXISTS uq_segment_current ON vps_md.vps_dim_segment (segment) WHERE is_current;

CREATE TABLE IF NOT EXISTS vps_md.vps_dim_template (
  sk bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  template_id text NOT NULL, segment text NOT NULL, version text NOT NULL, definition jsonb NOT NULL,
  status text NOT NULL DEFAULT 'ATIVO', owner text NOT NULL DEFAULT 'Engineering',
  valid_from timestamptz NOT NULL DEFAULT now(), valid_to timestamptz, is_current boolean NOT NULL DEFAULT true);
CREATE UNIQUE INDEX IF NOT EXISTS uq_template_current ON vps_md.vps_dim_template (template_id) WHERE is_current;

-- ── Projeções de processo ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vps_proj.vps_pending (
  pending_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tag_id text NOT NULL, cause_event_id uuid, item_key text,
  is_blocking boolean NOT NULL DEFAULT true, hourly_cost numeric(12,2),
  opened_ts timestamptz NOT NULL DEFAULT now(), cleared_ts timestamptz,
  aging_hours numeric);   -- derivado no read/view (now() não é imutável p/ STORED)
CREATE INDEX IF NOT EXISTS ix_pending_open ON vps_proj.vps_pending (tag_id) WHERE cleared_ts IS NULL;

CREATE TABLE IF NOT EXISTS vps_proj.vps_occurrence (
  occurrence_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tag_id text NOT NULL, occ_type text NOT NULL, severity text, phase text,
  evidence_uri text, model_version text,
  raised_ts timestamptz NOT NULL DEFAULT now(), resolved_ts timestamptz, resolution text);
CREATE INDEX IF NOT EXISTS ix_occ_open ON vps_proj.vps_occurrence (tag_id) WHERE resolved_ts IS NULL;

-- ── Reconciliação ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vps_recon.vps_reconciliation (
  recon_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tag_id text NOT NULL, physical_ref uuid, erp_doc text,
  status text NOT NULL CHECK (status IN ('MATCHED','PENDING','DIVERGENT')),
  divergence jsonb, evaluated_ts timestamptz NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS ix_recon_tag ON vps_recon.vps_reconciliation (tag_id, status);

-- ── APS ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vps_aps.glx_fact_vps_schedule (
  schedule_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  scenario_id text, tag_id text NOT NULL, operation text, resource_key text,
  planned_start timestamptz, planned_end timestamptz, setup_min int, run_min int, priority int, rule_used text,
  actual_start timestamptz, actual_end timestamptz,
  variance_min int GENERATED ALWAYS AS (CASE WHEN actual_end IS NOT NULL AND planned_end IS NOT NULL
                 THEN (EXTRACT(EPOCH FROM (actual_end - planned_end))/60)::int END) STORED);
CREATE INDEX IF NOT EXISTS ix_sched_tag ON vps_aps.glx_fact_vps_schedule (tag_id);
CREATE INDEX IF NOT EXISTS ix_sched_res ON vps_aps.glx_fact_vps_schedule (resource_key, planned_start);

-- ── Gold (glx) ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS glx.glx_dim_date (
  date_key int PRIMARY KEY, dt date NOT NULL, ano int, mes int, dia int, semana int, trimestre int);
CREATE TABLE IF NOT EXISTS glx.glx_dim_phase (
  phase_key bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, phase text UNIQUE, ordem int);
CREATE TABLE IF NOT EXISTS glx.glx_fact_vps_event (
  event_id uuid, tag_id text, segment text, entity_type text, action text, phase text,
  owner text, operator_id text, station_id text, model_version text, confidence numeric,
  recon_status text, event_ts timestamptz, date_key int);
CREATE INDEX IF NOT EXISTS ix_gfe_tag ON glx.glx_fact_vps_event (tag_id);
CREATE TABLE IF NOT EXISTS glx.glx_fact_vps_phase (
  phase_fact_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tag_id text, phase text, planned_min int, duration_min int, delay_min int,
  started_ts timestamptz, ended_ts timestamptz);
CREATE TABLE IF NOT EXISTS glx.glx_fact_vps_pending (
  pending_id bigint, tag_id text, is_blocking boolean, aging_hours numeric, hourly_cost numeric);

-- ── Staging / migração ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vps_stg.migration_batch (
  batch_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  source text, description text, started_ts timestamptz DEFAULT now(), finished_ts timestamptz, status text DEFAULT 'RUNNING');
CREATE TABLE IF NOT EXISTS vps_stg.depara_tagid (
  legacy_key text NOT NULL, source text NOT NULL, tag_id text NOT NULL, batch_id bigint,
  PRIMARY KEY (legacy_key, source));
CREATE TABLE IF NOT EXISTS vps_stg.stg_legacy_order (
  legacy_key text, segment text, entity_type text, natural_key text,
  client_key text, item_key text, qty numeric, status_legacy text,
  open_flag boolean, due_date date, batch_id bigint);

-- ── PLANEJAMENTO (vps_plan) — VPS_Projetos_Planejamento_Cards.md §8 ───
CREATE SCHEMA IF NOT EXISTS vps_plan;

CREATE TABLE IF NOT EXISTS vps_plan.project_calendar (
  calendar_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name text, work_days int[], shift_start time, shift_end time, holidays date[]);

CREATE TABLE IF NOT EXISTS vps_plan.project (
  project_id    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  code text NOT NULL UNIQUE, name text NOT NULL, segment text NOT NULL,
  template_id text, client_key text, calendar_id bigint, resource_pool text[],
  state text NOT NULL DEFAULT 'DRAFT'
    CHECK (state IN ('DRAFT','PLANNING','BASELINED','IN_EXECUTION','CLOSING','CLOSED')),
  planned_start date, planned_end date, baseline_id bigint,
  owner text NOT NULL DEFAULT 'Projects', tag_id text, created_ts timestamptz NOT NULL DEFAULT now());

CREATE TABLE IF NOT EXISTS vps_plan.wbs (
  wbs_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  project_id bigint NOT NULL REFERENCES vps_plan.project(project_id),
  parent_wbs_id bigint REFERENCES vps_plan.wbs(wbs_id),
  code text NOT NULL, name text NOT NULL, lvl int NOT NULL DEFAULT 1);

CREATE TABLE IF NOT EXISTS vps_plan.card (
  card_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  project_id bigint NOT NULL REFERENCES vps_plan.project(project_id),
  wbs_id bigint REFERENCES vps_plan.wbs(wbs_id),
  code text NOT NULL, title text NOT NULL,
  card_type text NOT NULL DEFAULT 'TASK' CHECK (card_type IN ('DELIVERABLE','TASK','MILESTONE')),
  planned_start timestamptz, planned_end timestamptz, planned_effort numeric,
  resource_key text, assigned_operator text, priority int DEFAULT 100,
  state text NOT NULL DEFAULT 'PLANNED'
    CHECK (state IN ('PLANNED','SCHEDULED','RELEASED','IN_EXECUTION','BLOCKED','DONE')),
  tag_id text, pct_complete numeric(5,2) DEFAULT 0,
  actual_start timestamptz, actual_end timestamptz, created_ts timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_card UNIQUE (project_id, code));
CREATE INDEX IF NOT EXISTS ix_card_project ON vps_plan.card (project_id, state);
CREATE INDEX IF NOT EXISTS ix_card_tag ON vps_plan.card (tag_id);

CREATE TABLE IF NOT EXISTS vps_plan.card_dependency (
  dep_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  pred_card_id bigint NOT NULL REFERENCES vps_plan.card(card_id),
  succ_card_id bigint NOT NULL REFERENCES vps_plan.card(card_id),
  dep_type text NOT NULL DEFAULT 'FS' CHECK (dep_type IN ('FS','SS','FF','SF')),
  lag_min int DEFAULT 0,
  CONSTRAINT uq_dep UNIQUE (pred_card_id, succ_card_id),
  CONSTRAINT ck_dep_noself CHECK (pred_card_id <> succ_card_id));

CREATE TABLE IF NOT EXISTS vps_plan.baseline (
  baseline_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  project_id bigint NOT NULL REFERENCES vps_plan.project(project_id),
  version int NOT NULL, snapshot_id bigint,
  created_ts timestamptz NOT NULL DEFAULT now(), created_by text,
  CONSTRAINT uq_baseline UNIQUE (project_id, version));
CREATE TABLE IF NOT EXISTS vps_plan.baseline_card (
  baseline_id bigint NOT NULL REFERENCES vps_plan.baseline(baseline_id),
  card_id bigint NOT NULL,
  planned_start timestamptz, planned_end timestamptz, planned_effort numeric,
  PRIMARY KEY (baseline_id, card_id));
