-- ═══════════════════════════════════════════════════════════════════
--  Gestão de alterações — log de mudanças no PRÓPRIO banco (PostgreSQL)
-- ═══════════════════════════════════════════════════════════════════
--
--  POR QUE NO BANCO, E NÃO NA APLICAÇÃO
--
--  A trilha de auditoria (audit_event) registra o que a APLICAÇÃO decidiu
--  contar. Ela é excelente para intenção — "OP avançada por op_operations com
--  a justificativa X" — e cega para o resto: um UPDATE feito por um script de
--  manutenção, uma correção manual por psql, um caminho de código que alguém
--  esqueceu de instrumentar. Nada disso aparece.
--
--  Este log é do banco. Trigger em cada tabela que importa: toda linha
--  inserida, alterada ou removida vira um registro com o antes, o depois e
--  exatamente quais campos mudaram. Não há como escrever sem aparecer aqui.
--
--  ATOR
--
--  O backend publica quem está agindo em `app.actor` (uma variável de sessão
--  do PostgreSQL) a cada requisição. Sem sessão, fica NULL — e um NULL aqui é
--  informação: quer dizer "veio de fora da aplicação".
--
--  RETENÇÃO
--
--  before/after ficam em JSONB (indexável e consultável). Campos de imagem e
--  base64 são cortados: o log é de mudança, não é backup do frame.
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS change_log (
    change_id      BIGSERIAL PRIMARY KEY,
    changed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    table_name     TEXT        NOT NULL,
    op             CHAR(1)     NOT NULL,          -- I insert · U update · D delete
    pk             TEXT,                          -- chave da linha (texto, serve p/ qualquer tipo)
    actor          TEXT,                          -- app.actor da sessão; NULL = fora da aplicação
    origem         TEXT,                          -- app.origem (rota/módulo), quando informado
    changed_fields TEXT[],                        -- só o que mudou (vazio em I e D)
    before_json    JSONB,
    after_json     JSONB
);

CREATE INDEX IF NOT EXISTS ix_change_log_ts    ON change_log (changed_at DESC);
CREATE INDEX IF NOT EXISTS ix_change_log_tab   ON change_log (table_name, changed_at DESC);
CREATE INDEX IF NOT EXISTS ix_change_log_pk    ON change_log (table_name, pk);
CREATE INDEX IF NOT EXISTS ix_change_log_actor ON change_log (actor, changed_at DESC);

-- Append-only: alterar ou apagar o log de alterações derrota o propósito dele.
CREATE OR REPLACE FUNCTION change_log_imutavel() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'change_log é append-only (tentativa de % negada)', TG_OP;
END; $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_change_log_imutavel ON change_log;
CREATE TRIGGER trg_change_log_imutavel
    BEFORE UPDATE OR DELETE ON change_log
    FOR EACH ROW EXECUTE FUNCTION change_log_imutavel();

-- Campos que nunca entram no log (payload pesado ou dado sensível).
CREATE OR REPLACE FUNCTION change_log_limpa(j JSONB) RETURNS JSONB AS $$
DECLARE k TEXT;
BEGIN
    IF j IS NULL THEN RETURN NULL; END IF;
    FOREACH k IN ARRAY ARRAY['image_b64','frame_b64','template_json','pin_hash','password','image_uri']
    LOOP
        IF j ? k THEN j := jsonb_set(j, ARRAY[k], '"«omitido»"'::jsonb); END IF;
    END LOOP;
    RETURN j;
END; $$ LANGUAGE plpgsql IMMUTABLE;

CREATE OR REPLACE FUNCTION registra_mudanca() RETURNS trigger AS $$
DECLARE
    v_pk     TEXT;
    v_before JSONB;
    v_after  JSONB;
    v_campos TEXT[] := '{}';
    v_col    TEXT;
BEGIN
    -- A chave da linha vem do primeiro argumento do trigger (nome da coluna PK).
    IF TG_OP <> 'INSERT' THEN v_before := change_log_limpa(to_jsonb(OLD)); END IF;
    IF TG_OP <> 'DELETE' THEN v_after  := change_log_limpa(to_jsonb(NEW)); END IF;

    IF TG_NARGS > 0 THEN
        IF TG_OP = 'DELETE' THEN v_pk := v_before ->> TG_ARGV[0];
        ELSE                     v_pk := v_after  ->> TG_ARGV[0]; END IF;
    END IF;

    IF TG_OP = 'UPDATE' THEN
        FOR v_col IN SELECT jsonb_object_keys(v_after) LOOP
            IF (v_after -> v_col) IS DISTINCT FROM (v_before -> v_col) THEN
                v_campos := array_append(v_campos, v_col);
            END IF;
        END LOOP;
        -- UPDATE que não mudou nada não é mudança: não polui o log.
        IF array_length(v_campos, 1) IS NULL THEN RETURN NULL; END IF;
    END IF;

    INSERT INTO change_log(table_name, op, pk, actor, origem, changed_fields, before_json, after_json)
    VALUES (TG_TABLE_NAME, left(TG_OP, 1), v_pk,
            NULLIF(current_setting('app.actor',  true), ''),
            NULLIF(current_setting('app.origem', true), ''),
            v_campos, v_before, v_after);
    RETURN NULL;   -- AFTER trigger: o valor de retorno é ignorado
END; $$ LANGUAGE plpgsql;

-- Liga o log a uma tabela. Idempotente: pode rodar a cada boot.
CREATE OR REPLACE FUNCTION change_log_ligar(p_tabela TEXT, p_pk TEXT) RETURNS void AS $$
BEGIN
    IF to_regclass(p_tabela) IS NULL THEN RETURN; END IF;
    EXECUTE format('DROP TRIGGER IF EXISTS trg_change_log ON %I', p_tabela);
    EXECUTE format(
        'CREATE TRIGGER trg_change_log AFTER INSERT OR UPDATE OR DELETE ON %I
         FOR EACH ROW EXECUTE FUNCTION registra_mudanca(%L)', p_tabela, p_pk);
END; $$ LANGUAGE plpgsql;

-- ── Tabelas sob gestão de alterações ────────────────────────────────
-- Fio Dourado, planejamento, APS, master data, acesso e configuração.
-- Ficam de fora: audit_event e vps_event (já são append-only por natureza —
-- logar um log é ruído), e as tabelas de série temporal/inferência, que são
-- alto volume e só recebem INSERT.
SELECT change_log_ligar('vps_tag',         'tag_id');
SELECT change_log_ligar('vps_lineage',     'child_tag_id');   -- PK composta: guarda o filho
SELECT change_log_ligar('vps_pending',     'pending_id');
SELECT change_log_ligar('vps_occurrence',  'occ_id');
SELECT change_log_ligar('vps_project',     'project_id');
SELECT change_log_ligar('vps_wbs',         'wbs_id');
SELECT change_log_ligar('vps_card',        'card_id');
SELECT change_log_ligar('vps_card_dep',    'dep_id');
SELECT change_log_ligar('vps_baseline',    'baseline_id');
SELECT change_log_ligar('vps_schedule',    'schedule_id');
SELECT change_log_ligar('vps_bom',         'bom_id');
SELECT change_log_ligar('vps_phase_log',   'phase_log_id');
SELECT change_log_ligar('vps_pick_demand', 'demand_id');
SELECT change_log_ligar('vps_resource',    'resource_key');
SELECT change_log_ligar('vps_operator',    'operator_id');
SELECT change_log_ligar('vps_access',      'operator_id');
SELECT change_log_ligar('vps_face_template','operator_id');
SELECT change_log_ligar('vps_erp_doc',     'natural_key');
SELECT change_log_ligar('dim_source',      'source_id');
SELECT change_log_ligar('dim_task',        'task_id');
SELECT change_log_ligar('dim_model',       'model_id');
SELECT change_log_ligar('dim_action_rule', 'rule_id');
SELECT change_log_ligar('app_config',      'key');
SELECT change_log_ligar('thermal_asset',   'asset_id');
SELECT change_log_ligar('metro_calibration','ref');
SELECT change_log_ligar('ot_asset',        'asset_id');
