-- ─────────────────────────────────────────────────────────────
-- VisionDesk — modelo de dados em STAR SCHEMA (SQLite no MVP).
-- Dimensões de configuração + fatos de inferência (Seção 6 da spec).
-- ─────────────────────────────────────────────────────────────

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ── DIMENSÕES ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dim_source (
    source_id    TEXT PRIMARY KEY,
    tipo         TEXT NOT NULL,            -- macbook | iphone_continuity | iphone_webrtc
    resolucao    TEXT,
    fps_nominal  INTEGER,
    descricao    TEXT,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_task (
    task_id          TEXT PRIMARY KEY,
    modo             TEXT NOT NULL,        -- LER | CONTAR | DESCREVER | ANALISAR
    prompt           TEXT,
    parametros_json  TEXT,                 -- classes-alvo, regex, critérios, thresholds
    roi_json         TEXT,                 -- coordenadas da ROI
    created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_model (
    model_id  TEXT PRIMARY KEY,
    nome      TEXT NOT NULL,               -- ex. yolo11n, claude-opus-4-8, paddleocr
    tipo      TEXT NOT NULL,               -- edge | vlm
    versao    TEXT
);

-- ── FATOS ────────────────────────────────────────────────────
-- grão = 1 inferência
CREATE TABLE IF NOT EXISTS fact_detection (
    detection_id  TEXT PRIMARY KEY,
    source_id     TEXT,
    task_id       TEXT,
    model_id      TEXT,
    timestamp     TEXT NOT NULL,
    frame_ref     TEXT,                    -- caminho/hash do frame (se persistido)
    latency_ms    INTEGER,
    confidence    REAL,
    pipeline      TEXT,
    result_json   TEXT,                    -- payload completo do resultado
    FOREIGN KEY (source_id) REFERENCES dim_source(source_id),
    FOREIGN KEY (task_id)   REFERENCES dim_task(task_id),
    FOREIGN KEY (model_id)  REFERENCES dim_model(model_id)
);
CREATE INDEX IF NOT EXISTS ix_fact_detection_ts     ON fact_detection(timestamp);
CREATE INDEX IF NOT EXISTS ix_fact_detection_task   ON fact_detection(task_id);
CREATE INDEX IF NOT EXISTS ix_fact_detection_source ON fact_detection(source_id);
CREATE INDEX IF NOT EXISTS ix_fact_detection_src_ts ON fact_detection(source_id, timestamp);

-- grão = janela temporal (agregação de contagem)
CREATE TABLE IF NOT EXISTS fact_count (
    count_id          TEXT PRIMARY KEY,
    task_id           TEXT,
    janela_inicio     TEXT NOT NULL,
    janela_fim        TEXT NOT NULL,
    classe            TEXT,
    quantidade        INTEGER,
    cruzamentos_linha INTEGER,
    FOREIGN KEY (task_id) REFERENCES dim_task(task_id)
);

-- grão = token/campo reconhecido (modo LER)
CREATE TABLE IF NOT EXISTS fact_ocr (
    ocr_id        TEXT PRIMARY KEY,
    detection_id  TEXT,
    texto         TEXT,
    campo_logico  TEXT,
    confidence    REAL,
    bbox_json     TEXT,
    FOREIGN KEY (detection_id) REFERENCES fact_detection(detection_id)
);
CREATE INDEX IF NOT EXISTS ix_fact_ocr_detection ON fact_ocr(detection_id);

-- ── AGIR (M5 — Vision-Language-Action) — v2.0 ────────────────────────
-- Regras no-code configuradas pelo operador (condição → ações).
-- task_id sem FK: aceita task_id real OU '*' (regra global p/ qualquer tarefa).
CREATE TABLE IF NOT EXISTS dim_action_rule (
    rule_id        TEXT PRIMARY KEY,
    task_id        TEXT,
    label          TEXT,
    condition_json TEXT NOT NULL,   -- {"field","op","value","min_confidence"}
    actions_json   TEXT NOT NULL,   -- [{"type","target","message","payload_template"}]
    active         INTEGER DEFAULT 1,
    created_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_rule_task ON dim_action_rule(task_id);

-- Ações disparadas (auditoria + retry).
CREATE TABLE IF NOT EXISTS fact_action (
    action_id     TEXT PRIMARY KEY,
    rule_id       TEXT,
    detection_id  TEXT,
    task_id       TEXT,
    timestamp     TEXT NOT NULL,
    action_type   TEXT NOT NULL,
    target        TEXT,
    payload_json  TEXT,
    status        TEXT DEFAULT 'pending',  -- pending|success|error|skipped
    http_status   INTEGER,
    error_message TEXT,
    retry_count   INTEGER DEFAULT 0,
    executed_at   TEXT
);
CREATE INDEX IF NOT EXISTS ix_action_ts     ON fact_action(timestamp);
CREATE INDEX IF NOT EXISTS ix_action_status ON fact_action(status);

-- ── GRAVAÇÕES (auto por detecção + manuais) — antes em index.json ────
CREATE TABLE IF NOT EXISTS fact_recording (
    rec_id      TEXT PRIMARY KEY,
    source_id   TEXT,
    timestamp   TEXT NOT NULL,
    mode        TEXT,
    trigger     TEXT,                    -- auto | manual
    classes_json TEXT,                   -- {"person":2,"dog":1}
    image_uri   TEXT                     -- file://… | s3://…
);
CREATE INDEX IF NOT EXISTS ix_rec_src_ts ON fact_recording(source_id, timestamp);

-- ── SÉRIE TEMPORAL DE REDE/BUFFER (monitoramento) — TimescaleDB-ready ─
-- grão = 1 amostra de enlace por câmera (latência/jitter/perda/buffer/throughput).
CREATE TABLE IF NOT EXISTS metric_timeseries (
    time            TIMESTAMPTZ NOT NULL,
    source_id       TEXT NOT NULL,
    latency_ms      REAL,
    jitter_ms       REAL,
    packet_loss     REAL,
    buffer_pct      REAL,
    fps             REAL,
    throughput_kbps REAL
);
CREATE INDEX IF NOT EXISTS ix_metric_src_time ON metric_timeseries(source_id, time DESC);

-- ── TRILHA DE AUDITORIA / RASTREABILIDADE TOTAL (append-only) ─────────
-- Uma linha por AÇÃO do sistema: cada leitura/contagem/detecção/descrição/
-- análise, alteração de dados (CRUD), evento de câmera, ação (AGIR), captura
-- VPS, alerta de monitor. Envelope comum → timeline única e auditável.
CREATE TABLE IF NOT EXISTS audit_event (
    event_id       TEXT PRIMARY KEY,
    event_ts       TEXT NOT NULL,                 -- ISO-8601
    category       TEXT NOT NULL,                 -- INFERENCE|CAMERA|DATA|ACTION|RECORDING|VPS|MONITOR|SYSTEM
    action         TEXT NOT NULL,                 -- READ|COUNT|DETECT|DESCRIBE|ANALYZE|CREATE|UPDATE|DELETE|...
    severity       TEXT NOT NULL DEFAULT 'info',  -- info|ok|nok|alerta|warn
    actor          TEXT,                          -- operador/usuário/worker/sistema
    source_id      TEXT,                          -- câmera/fonte (vínculo c/ câmeras)
    entity_type    TEXT,                          -- camera|rule|recording|tag|inference|...
    entity_id      TEXT,
    summary        TEXT,                          -- 1 linha humana
    correlation_id TEXT,                          -- liga eventos do mesmo fio (detection_id/tag_id)
    payload_json   TEXT
);
CREATE INDEX IF NOT EXISTS ix_audit_ts       ON audit_event(event_ts DESC);
CREATE INDEX IF NOT EXISTS ix_audit_cat_ts   ON audit_event(category, event_ts DESC);
CREATE INDEX IF NOT EXISTS ix_audit_src_ts   ON audit_event(source_id, event_ts DESC);
CREATE INDEX IF NOT EXISTS ix_audit_entity   ON audit_event(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS ix_audit_corr     ON audit_event(correlation_id);

-- ── TRACKING · sumário durável (silver/lakehouse) ───────────────────
-- Eventos semânticos vão na trilha; AQUI fica o sumário por track/dwell
-- (cycle time observado) p/ baseline/tendência — downsampled, não por frame.
CREATE TABLE IF NOT EXISTS vps_track_summary (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id    TEXT,
    track_id     INTEGER,
    object_class TEXT,
    tag_id       TEXT,                       -- Fio Dourado do movimento (se vinculado)
    dwell_s      REAL,                       -- permanência na zona = cycle time observado
    event_ts     TEXT NOT NULL,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_track_summary_src ON vps_track_summary(source_id, event_ts DESC);

-- ── TERMOGRAFIA / MANUTENÇÃO PREDITIVA ───────────────────────────────
-- Ativo (ASSET) com baseline térmica + limites; série de leituras p/ tendência.
CREATE TABLE IF NOT EXISTS thermal_asset (
    asset_id      TEXT PRIMARY KEY,
    name          TEXT,
    emissivity    REAL NOT NULL DEFAULT 0.95,
    t_min         REAL NOT NULL DEFAULT 20,    -- faixa p/ pseudo-radiometria (luminância→°C)
    t_max         REAL NOT NULL DEFAULT 120,
    t_abs_limit   REAL NOT NULL DEFAULT 75,    -- limiar absoluto (°C)
    delta_t_limit REAL NOT NULL DEFAULT 15,    -- ΔT vs baseline p/ alarme
    baseline_tmax REAL,                        -- assinatura térmica saudável (datada)
    baseline_ts   TEXT,
    tag_id        TEXT,                        -- VPS:PLANT:ASSET:...
    created_at    TEXT NOT NULL
);

-- Série radiométrica por ativo (analítico → baseline e tendência).
CREATE TABLE IF NOT EXISTS thermal_reading (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id    TEXT NOT NULL,
    t_max       REAL, t_avg REAL, delta_t REAL,
    severity    TEXT,                          -- NORMAL | OBSERVAR | AGIR | CRITICO
    hotspot_x   REAL, hotspot_y REAL,          -- normalizado [0,1]
    emissivity  REAL,
    event_ts    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_thermal_reading_asset ON thermal_reading(asset_id, event_ts DESC);

-- ── METROLOGIA / INSPEÇÃO DIMENSIONAL ────────────────────────────────
-- Calibração rastreável (escala px→mm) + medições com tolerância/veredito.
CREATE TABLE IF NOT EXISTS metro_calibration (
    ref             TEXT PRIMARY KEY,
    scale_mm_per_px REAL NOT NULL,
    valid_until     TEXT,
    is_current      INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS metro_measurement (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    op_tag          TEXT,
    feature         TEXT,
    kind            TEXT,                       -- linear | diameter | angle
    measured        REAL, nominal REAL, tol_lo REAL, tol_hi REAL,
    uncertainty     REAL, verdict TEXT,         -- CONFORME | NAO_CONFORME
    calibration_ref TEXT,
    event_ts        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_metro_feat ON metro_measurement(feature, event_ts DESC);

-- ── AUTOMAÇÃO INDUSTRIAL (conector OT: PLC/IHM → eventos) ────────────
-- Read-only/observador. Ativo = máquina (Tag-ID). Leitura por protocolo (OPC UA…)
-- ou por visão (IHM legada). Série de leituras → eventos semânticos + OEE.
CREATE TABLE IF NOT EXISTS ot_asset (
    asset_id   TEXT PRIMARY KEY,
    name       TEXT,
    kind       TEXT,                            -- drive | remote_io | transmitter | machine | legacy_hmi
    mode       TEXT NOT NULL DEFAULT 'protocol',-- protocol | vision | hybrid
    protocol   TEXT,                            -- opcua | modbus | s7 | ethernetip | mqtt | profinet | screen
    endpoint   TEXT,
    tag_id     TEXT,                            -- VPS:PLANT:ASSET:...
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ot_reading (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id  TEXT NOT NULL,
    action    TEXT NOT NULL,                    -- MACHINE_STATE | COUNTER_READ | ALARM_RAISED | PROCESS_VALUE_READ | CYCLE_COMPLETED | IO_STATE | IO_FAULT | TELEMETRY_READ
    tag       TEXT,
    value     TEXT,
    code      INTEGER,
    quality   TEXT,                             -- Good | Bad | Uncertain (OPC UA)
    source    TEXT,                             -- PLC | SCREEN
    source_ts TEXT,                             -- timestamp da FONTE (PLC/OPC UA)
    event_ts  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_ot_reading ON ot_reading(asset_id, event_ts DESC);
CREATE INDEX IF NOT EXISTS ix_ot_action ON ot_reading(action, event_ts DESC);

-- Sinóptico (tela supervisória low-code): layout de widgets editável/parametrizável.
CREATE TABLE IF NOT EXISTS ot_synoptic (
    name       TEXT PRIMARY KEY,
    json       TEXT NOT NULL,                  -- {name, widgets:[...]}
    updated_at TEXT NOT NULL
);

-- ── CONTROLE DE ACESSO (RBAC) + LOGIN ────────────────────────────────
-- Papel de ACESSO ao sistema por usuário (operador): admin | operador | view.
-- Login por FaceID (reusa vps_face_template) ou PIN (fallback). Sessão por token.
CREATE TABLE IF NOT EXISTS vps_access (
    operator_id TEXT PRIMARY KEY,
    name        TEXT,
    role        TEXT NOT NULL DEFAULT 'view',   -- admin | operador | view
    pin_hash    TEXT,                            -- fallback não-biométrico (sha256)
    active      INTEGER NOT NULL DEFAULT 1,
    perfil      TEXT,                            -- perfil operacional (Operations|Supply|Quality|Projects)
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS auth_session (
    token       TEXT PRIMARY KEY,
    operator_id TEXT NOT NULL,
    name        TEXT,
    role        TEXT NOT NULL,
    method      TEXT,                            -- face | pin | bootstrap
    created_at  TEXT NOT NULL
);

-- ── iaMAC · IA + Motor de Aprendizado (flywheel) ─────────────────────
-- Interações do copiloto (com citações/feedback) + histórico de avaliação (eval).
CREATE TABLE IF NOT EXISTS ia_interaction (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    question       TEXT NOT NULL,
    answer         TEXT,
    citations_json TEXT,
    vote           INTEGER,                 -- +1 / -1 (feedback do flywheel)
    ts             TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ia_eval (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    version   TEXT,
    score     REAL,                          -- % acerto no golden set
    grounding REAL,                          -- % respostas lastreadas
    ts        TEXT NOT NULL
);

-- ── BIOMETRIA FACIAL (template, NÃO foto · LGPD) ─────────────────────
-- Identificação consentida de operador. Guarda o TEMPLATE (vetor), nunca a
-- imagem. Consentimento registrado e revogável (VisionDesk_Reconhecimento_Facial).
CREATE TABLE IF NOT EXISTS vps_face_template (
    operator_id   TEXT PRIMARY KEY,
    name          TEXT,
    template_json TEXT NOT NULL,             -- vetor (JSON) — descritor, não foto
    algo          TEXT NOT NULL,
    dim           INTEGER NOT NULL,
    consent_ts    TEXT NOT NULL,             -- prova de consentimento (LGPD art. 11)
    consent_ref   TEXT,
    is_current    INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL
);

-- ═════════════════════════════════════════════════════════════════════
-- VPS — Visual Planning System (event-sourced; Event Store = fonte da verdade).
-- Tag-ID (Fio Dourado) atravessa todos os bounded contexts. Ver SPEC_VPS.md.
-- ═════════════════════════════════════════════════════════════════════

-- EVENT STORE (imutável, append-only) — grão = 1 evento VPS
CREATE TABLE IF NOT EXISTS vps_event (
    event_id      TEXT PRIMARY KEY,
    tag_id        TEXT NOT NULL,
    parent_tag_id TEXT,
    action        TEXT NOT NULL,            -- VERBO_SUBSTANTIVO (PICK_ITEM_CONFIRMED)
    phase         TEXT,                      -- fase do template no momento
    domain        TEXT,                      -- OP | PICK | STOCK | ...
    event_ts      TEXT NOT NULL,             -- ISO-8601 (carimbo físico)
    source_type   TEXT,                      -- OSMO_UVC | DRONE_RTMP | FIXED | MANUAL | cam:<id>
    station_id    TEXT,
    operator_id   TEXT,
    vision_mode   TEXT,                      -- LER | CONTAR | DESCREVER | ANALISAR
    model_version TEXT,                      -- rastreabilidade do modelo de visão
    confidence    REAL,
    payload_json  TEXT,                      -- {sku, qty, location, ...}
    owner         TEXT,                      -- Operations | Supply | Finance | ...
    recon_status  TEXT,                      -- PENDING | MATCHED | DIVERGENT
    image_uri     TEXT,
    ingested_ts   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_vps_event_tag ON vps_event(tag_id, event_ts);
CREATE INDEX IF NOT EXISTS ix_vps_event_ts ON vps_event(event_ts DESC);

-- DIMENSÃO TAG-ID (estado atual + ponteiro de linhagem) — projeção do event store
CREATE TABLE IF NOT EXISTS vps_tag (
    tag_id         TEXT PRIMARY KEY,
    segment        TEXT,
    entity_type    TEXT,                     -- OP | PICK | ITEM | SO | PROJ | SHIP ...
    natural_key    TEXT,
    instance       TEXT,
    state          TEXT NOT NULL,            -- CAPTURED→RESOLVED→BOUND→IN_PROCESS⇄EXCEPTION→COMPLETED→ARCHIVED
    template_id    TEXT,
    current_phase  TEXT,
    parent_tag_id  TEXT,
    opened_ts      TEXT,
    closed_ts      TEXT,
    last_event_ts  TEXT
);
CREATE INDEX IF NOT EXISTS ix_vps_tag_state ON vps_tag(state);
CREATE INDEX IF NOT EXISTS ix_vps_tag_phase ON vps_tag(current_phase);

-- LINHAGEM (grafo do Fio Dourado)
CREATE TABLE IF NOT EXISTS vps_lineage (
    parent_tag_id  TEXT NOT NULL,
    child_tag_id   TEXT NOT NULL,
    relation       TEXT,                     -- SO→PROJ | PROJ→OP | OP→PICK ...
    PRIMARY KEY (parent_tag_id, child_tag_id)
);

-- PENDÊNCIAS (o que falta p/ avançar — pode bloquear a fase)
CREATE TABLE IF NOT EXISTS vps_pending (
    pending_id   TEXT PRIMARY KEY,
    tag_id       TEXT NOT NULL,
    phase        TEXT,
    reason       TEXT,
    blocking     INTEGER DEFAULT 1,
    opened_ts    TEXT NOT NULL,
    cleared_ts   TEXT
);
CREATE INDEX IF NOT EXISTS ix_vps_pending_tag ON vps_pending(tag_id, cleared_ts);

-- OCORRÊNCIAS (desvios / transições inválidas / anomalias)
CREATE TABLE IF NOT EXISTS vps_occurrence (
    occ_id       TEXT PRIMARY KEY,
    tag_id       TEXT NOT NULL,
    phase        TEXT,
    kind         TEXT,                       -- INVALID_TRANSITION | ANOMALY | DAMAGE | SHORT ...
    severity     TEXT,                       -- info | alerta | nok
    note         TEXT,
    evidence_uri TEXT,
    raised_ts    TEXT NOT NULL,
    resolved_ts  TEXT
);
CREATE INDEX IF NOT EXISTS ix_vps_occ_tag ON vps_occurrence(tag_id, resolved_ts);

-- DOCUMENTOS ERP/MES (conector) — reconciliação contra o físico (visão). Persistido.
CREATE TABLE IF NOT EXISTS vps_erp_doc (
    natural_key  TEXT PRIMARY KEY,         -- chave de negócio que casa com o Tag-ID (OP/lote/pedido)
    doc          TEXT,                      -- nº do documento no ERP/MES
    qty          REAL,                      -- quantidade do documento (p/ checar divergência vs visão)
    value        REAL,
    status       TEXT,
    source       TEXT,                      -- csv | api | manual | seed
    ingested_ts  TEXT
);

-- OPERADORES (master data / SCD2-lite) — gente que opera; operator_id vai no evento.
CREATE TABLE IF NOT EXISTS vps_operator (
    operator_id  TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    matricula    TEXT,
    badge        TEXT,                      -- crachá QR/NFC/PIN p/ identificar-se na captura
    role         TEXT,                      -- mapeia ao RBAC (Operador/Supervisor/...)
    stations     TEXT,                      -- estações habilitadas (csv)
    skills       TEXT,                      -- habilidades (csv) → restrições do APS
    shift        TEXT,
    status       TEXT DEFAULT 'ativo',      -- ativo|inativo (inativar, nunca apagar)
    created_at   TEXT
);

-- RECURSOS / MÁQUINAS (APS) — capacidade finita p/ o scheduling.
CREATE TABLE IF NOT EXISTS vps_resource (
    resource_key TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    capacity     INTEGER DEFAULT 1,         -- ordens simultâneas (capacidade finita)
    skills       TEXT,                      -- habilidades exigidas/fornecidas (csv)
    calendar     TEXT,                      -- turno/calendário (ref. textual)
    status       TEXT DEFAULT 'ativo',
    created_at   TEXT
);

-- CRONOGRAMA APS (GLX_FACT_VPS_SCHEDULE) — grão = operação agendada por recurso.
CREATE TABLE IF NOT EXISTS vps_schedule (
    schedule_id   TEXT PRIMARY KEY,
    scenario_id   TEXT,
    tag_id        TEXT,                      -- OP/instância (linhagem)
    operation     TEXT,                      -- fase do template
    resource_key  TEXT,
    seq           INTEGER,                   -- ordem no recurso
    planned_start TEXT,
    planned_end   TEXT,
    setup_min     INTEGER DEFAULT 0,
    run_min       INTEGER DEFAULT 0,
    priority      INTEGER DEFAULT 0,
    rule_used     TEXT,
    actual_start  TEXT,                      -- realimentação da visão (Fio Dourado)
    actual_end    TEXT,
    variance_min  INTEGER,
    published     INTEGER DEFAULT 0,
    created_at    TEXT
);
CREATE INDEX IF NOT EXISTS ix_vps_sched_scn ON vps_schedule(scenario_id, resource_key, seq);

-- ── PLANEJAMENTO (Projetos/Cards) — VPS_Projetos_Planejamento_Cards.md ─
-- O Projeto REGE: habilita planejar cards; card liberado vira Tag-ID (gênese).
CREATE TABLE IF NOT EXISTS vps_project (
    project_id    TEXT PRIMARY KEY,
    code          TEXT NOT NULL UNIQUE,        -- PRJ-2026-118
    name          TEXT NOT NULL,
    segment       TEXT NOT NULL,
    template_id   TEXT,
    client_key    TEXT,
    resource_pool TEXT,                          -- recursos do projeto (csv)
    state         TEXT NOT NULL DEFAULT 'DRAFT', -- DRAFT|PLANNING|BASELINED|IN_EXECUTION|CLOSING|CLOSED
    planned_start TEXT,
    planned_end   TEXT,
    baseline_version INTEGER DEFAULT 0,
    owner         TEXT DEFAULT 'Projects',
    tag_id        TEXT,                          -- VPS:{seg}:PROJ:{code}:01 (linhagem)
    created_at    TEXT
);

CREATE TABLE IF NOT EXISTS vps_wbs (
    wbs_id        TEXT PRIMARY KEY,
    project_id    TEXT NOT NULL,
    parent_wbs_id TEXT,
    code          TEXT NOT NULL,
    name          TEXT NOT NULL,
    lvl           INTEGER DEFAULT 1
);
CREATE INDEX IF NOT EXISTS ix_wbs_project ON vps_wbs(project_id);

CREATE TABLE IF NOT EXISTS vps_card (
    card_id        TEXT PRIMARY KEY,
    project_id     TEXT NOT NULL,
    wbs_id         TEXT,
    code           TEXT NOT NULL,
    title          TEXT NOT NULL,
    card_type      TEXT NOT NULL DEFAULT 'TASK',  -- DELIVERABLE|TASK|MILESTONE
    planned_start  TEXT,
    planned_end    TEXT,
    planned_effort REAL DEFAULT 8,                -- horas
    resource_key   TEXT,
    assigned_operator TEXT,
    priority       INTEGER DEFAULT 100,
    state          TEXT NOT NULL DEFAULT 'PLANNED', -- PLANNED|SCHEDULED|RELEASED|IN_EXECUTION|BLOCKED|DONE
    tag_id         TEXT,                          -- null até liberar (vínculo execução)
    pct_complete   REAL DEFAULT 0,                -- avanço FÍSICO observado (visão)
    actual_start   TEXT,
    actual_end     TEXT,
    created_at     TEXT
);
CREATE INDEX IF NOT EXISTS ix_card_project ON vps_card(project_id, state);
CREATE INDEX IF NOT EXISTS ix_card_tag ON vps_card(tag_id);

CREATE TABLE IF NOT EXISTS vps_card_dep (
    dep_id        TEXT PRIMARY KEY,
    project_id    TEXT NOT NULL,
    pred_card_id  TEXT NOT NULL,
    succ_card_id  TEXT NOT NULL,
    dep_type      TEXT NOT NULL DEFAULT 'FS',     -- FS|SS|FF|SF
    lag_min       INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_dep_project ON vps_card_dep(project_id);

CREATE TABLE IF NOT EXISTS vps_baseline (
    baseline_id  TEXT PRIMARY KEY,
    project_id   TEXT NOT NULL,
    version      INTEGER NOT NULL,
    created_at   TEXT,
    created_by   TEXT
);
CREATE TABLE IF NOT EXISTS vps_baseline_card (
    baseline_id   TEXT NOT NULL,
    card_id       TEXT NOT NULL,
    planned_start TEXT,
    planned_end   TEXT,
    planned_effort REAL,
    PRIMARY KEY (baseline_id, card_id)
);

-- Configurações de sistema persistidas (chave→JSON): catálogo UI/UX, schema de
-- campos de links do supervisório, aparência sincronizada, ondas de implantação.
-- ── Linha do tempo por ETAPA: baseline, plano vigente e realizado ───
-- Uma linha por (instância, fase). baseline_* é escrito na gênese e nunca
-- reescrito; planned_* é reprojetado quando uma etapa atrasa; actual_* é
-- gravado no instante em que o card avançou. Ver vps/phases.py.
CREATE TABLE IF NOT EXISTS vps_phase_log (
    phase_log_id   TEXT PRIMARY KEY,
    tag_id         TEXT NOT NULL,
    phase          TEXT NOT NULL,
    seq            INTEGER NOT NULL,
    baseline_start TEXT,
    baseline_end   TEXT,
    planned_start  TEXT,
    planned_end    TEXT,
    actual_start   TEXT,
    actual_end     TEXT,
    duration_h     REAL,
    sla_h          REAL,
    variance_h     REAL,
    state          TEXT NOT NULL DEFAULT 'PENDING',   -- PENDING|ACTIVE|DONE|SKIPPED
    entered_event  TEXT,
    exited_event   TEXT,
    updated_at     TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_phase_log_tag_phase ON vps_phase_log(tag_id, phase);
CREATE INDEX IF NOT EXISTS ix_phase_log_state ON vps_phase_log(state, planned_end);

-- ── PCP — Planejamento e Controle da Produção ───────────────────────
-- A fase PCP transforma DEMANDA em MATERIAL: pega a estrutura do produto
-- (vps_bom) e explode em demandas de separação (vps_pick_demand), que é o que
-- o PICKING vai buscar. Sem esta etapa o picking nascia do nada — alguém
-- decidia de cabeça o que separar, e a diferença entre o planejado e o
-- separado não tinha onde ser medida.
CREATE TABLE IF NOT EXISTS vps_bom (
    bom_id       TEXT PRIMARY KEY,
    product_key  TEXT NOT NULL,                 -- família/produto: PANEL, FOOD, PHARMA…
    template_id  TEXT,                          -- template do processo a que se aplica
    item_key     TEXT NOT NULL,                 -- RES-22K
    descricao    TEXT,
    qty          REAL NOT NULL DEFAULT 1,       -- por unidade do produto
    unit         TEXT DEFAULT 'un',
    posicao      INTEGER DEFAULT 0,             -- ordem na estrutura
    lead_time_h  REAL DEFAULT 0,                -- ressuprimento (entra no CTP)
    critico      INTEGER DEFAULT 0,             -- falta trava a produção
    created_at   TEXT
);
CREATE INDEX IF NOT EXISTS ix_bom_produto ON vps_bom(product_key, posicao);
CREATE INDEX IF NOT EXISTS ix_bom_item ON vps_bom(item_key);

CREATE TABLE IF NOT EXISTS vps_pick_demand (
    demand_id    TEXT PRIMARY KEY,
    tag_id       TEXT NOT NULL,                 -- OP que demandou (Fio Dourado)
    pick_tag_id  TEXT,                          -- Tag-ID da separação (filho da OP)
    bom_id       TEXT,                          -- item da estrutura que gerou
    item_key     TEXT NOT NULL,
    descricao    TEXT,
    qty_planned  REAL NOT NULL,
    qty_picked   REAL DEFAULT 0,
    unit         TEXT DEFAULT 'un',
    state        TEXT NOT NULL DEFAULT 'PLANNED',  -- PLANNED|PICKING|DONE|SHORT
    critico      INTEGER DEFAULT 0,
    created_at   TEXT,
    closed_at    TEXT
);
CREATE INDEX IF NOT EXISTS ix_demand_tag ON vps_pick_demand(tag_id, state);
CREATE INDEX IF NOT EXISTS ix_demand_item ON vps_pick_demand(item_key);

CREATE TABLE IF NOT EXISTS app_config (
    key        TEXT PRIMARY KEY,
    json       TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
