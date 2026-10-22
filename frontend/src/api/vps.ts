import { API_BASE } from "./config";

// ── Tipos (espelham o backend VPS) ───────────────────────────────────
export interface BoardCard {
  tag_id: string;
  entity_type: string;
  natural_key: string;
  segment: string;
  state: string;
  phase: string;
  aging_h: number;
  sla_h: number | null;
  sla_status: "ok" | "warn" | "late";
  eta_breach_h: number | null;
  risk: "ok" | "warn" | "high" | "late" | "blocked" | "done";
  pendings: number;
  occurrences: number;
}

export interface BoardAlert {
  tag_id: string;
  natural_key: string;
  phase: string;
  reason: string;
  risk?: string;
  eta_breach_h?: number | null;
  pendings: number;
  occurrences: number;
}

export interface Board {
  columns: string[];
  cards: BoardCard[];
  wip: Record<string, number>;
  bottleneck: string | null;
  alerts: BoardAlert[];
  total: number;
}

export interface VpsEvent {
  event_id: string;
  tag_id: string;
  parent_tag_id: string | null;
  action: string;
  phase: string | null;
  domain: string | null;
  event_ts: string;
  source_type: string | null;
  station_id?: string | null;
  operator_id?: string | null;
  vision_mode: string | null;
  model_version: string | null;
  confidence: number | null;
  payload: Record<string, unknown>;
  owner: string | null;
  recon_status: string | null;
  image_uri: string | null;
}

export interface Pending { pending_id: string; tag_id: string; phase: string | null; reason: string; blocking: number; opened_ts: string; cleared_ts: string | null }
export interface Occurrence { occ_id: string; tag_id: string; phase: string | null; kind: string; severity: string; note: string; raised_ts: string; resolved_ts: string | null }
export interface LineageEdge { parent_tag_id: string; child_tag_id: string; relation: string }

export interface Thread {
  tag: Record<string, string | null>;
  timeline: VpsEvent[];
  lineage: { parents: LineageEdge[]; children: LineageEdge[] };
  pendencies: Pending[];
  occurrences: Occurrence[];
  kpis: { lead_time_h: number; phase_times_h: Record<string, number>; bottleneck: string | null; events: number };
}

export type Kpis = Record<string, number | string | null>;

export interface TemplateInfo { template_id: string; segment: string; label: string | null; phases: string[] }

export interface ReconItem { tag_id: string; natural_key: string; entity_type: string; erp_doc: string | null; status: string }
export interface Recon { rate: number; matched: number; divergent: number; unmatched: number; docs: Record<string, unknown>[]; items: ReconItem[] }

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`);
  if (!r.ok) throw new Error(`GET ${path} -> ${r.status}`);
  return r.json() as Promise<T>;
}

export const getBoard = (entity?: string, segment?: string) => {
  const q = new URLSearchParams();
  if (entity) q.set("entity", entity);
  if (segment) q.set("segment", segment);
  const s = q.toString();
  return get<Board>(`/vps/board${s ? `?${s}` : ""}`);
};
export const getKpis = () => get<Kpis>(`/vps/kpis`);
export const getRecon = () => get<Recon>(`/vps/recon`);
export async function seedRecon(): Promise<Recon> {
  return (await fetch(`${API_BASE}/vps/recon/seed`, { method: "POST" })).json();
}

// Conector ERP/MES: ingestão de documentos (CSV) + persistência.
export interface ErpDoc { natural_key: string; doc: string | null; qty: number | null; value: number | null; status: string | null; source: string | null }
export const getReconDocs = () => get<{ docs: ErpDoc[] }>(`/vps/recon/docs`);
export async function importReconCsv(csv: string): Promise<Recon & { ingested: number }> {
  return (await fetch(`${API_BASE}/vps/recon/import`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ csv }),
  })).json();
}
export async function clearReconDocs(): Promise<Recon> {
  return (await fetch(`${API_BASE}/vps/recon/docs`, { method: "DELETE" })).json();
}
export const getThread = (tagId: string) => get<Thread>(`/vps/thread/${encodeURIComponent(tagId)}`);
export const getTemplates = () => get<{ templates: TemplateInfo[] }>(`/vps/templates`);
export const getRecentEvents = (limit = 80) => get<{ events: VpsEvent[] }>(`/vps/events?limit=${limit}`);

export async function seedVps(reset = true): Promise<{ seeded_events: number; tags: number }> {
  return (await fetch(`${API_BASE}/vps/seed?reset=${reset}`, { method: "POST" })).json();
}

// ── Inteligência preditiva + governança ──────────────────────────────
export interface Risks { risks: BoardCard[]; predicted_bottleneck: string | null; count: number }
export const getRisks = () => get<Risks>(`/vps/risks`);

// RBAC: papel atual (persistido) enviado em X-VPS-Role nas ações de governança.
export function getVpsRole(): string { try { return localStorage.getItem("vps-role") || "Admin"; } catch { return "Admin"; } }
export function setVpsRole(r: string): void { try { localStorage.setItem("vps-role", r); } catch { /* ignore */ } }

const post = async (path: string, body?: unknown) =>
  (await fetch(`${API_BASE}${path}`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined,
  })).json();

// Ações de governança: enviam papel e lançam erro legível em 403 (RBAC).
async function postGov(path: string, body?: unknown) {
  const r = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-VPS-Role": getVpsRole() },
    body: body ? JSON.stringify(body) : undefined,
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j?.detail?.message || `HTTP ${r.status}`);
  return j;
}

export const clearPending = (id: string) => postGov(`/vps/pending/${id}/clear`);
export const resolveOccurrence = (id: string) => postGov(`/vps/occurrence/${id}/resolve`);
export const advanceThread = (tagId: string) => postGov(`/vps/thread/${encodeURIComponent(tagId)}/advance`);
export const correctThread = (tagId: string, note: string) => postGov(`/vps/thread/${encodeURIComponent(tagId)}/correct`, { note });

export interface RolesInfo { roles: string[]; default: string; entity_owner: Record<string, string> }
export const getRoles = () => get<RolesInfo>(`/vps/roles`);

// ── Operadores (master data + identificação) ─────────────────────────
export interface Operator {
  operator_id: string; name: string; matricula: string | null; badge: string | null;
  role: string | null; stations: string | null; skills: string | null; shift: string | null; status: string;
}
export const getOperators = (status?: string) =>
  get<{ operators: Operator[]; sessions: Record<string, string> }>(`/vps/operators${status ? `?status=${status}` : ""}`);
export const upsertOperator = (d: Partial<Operator>) => post(`/vps/operators`, d) as Promise<Operator>;
export const setOperatorStatus = (id: string, status: string) => post(`/vps/operators/${id}/status`, { status });
export const identifyOperator = (station: string, who: { operator_id?: string; badge?: string }) =>
  post(`/vps/operators/identify`, { station, ...who }) as Promise<{ station: string; operator_id: string | null }>;
export const seedOperators = () => post(`/vps/operators/seed`);

// ── APS — Planejamento Avançado ──────────────────────────────────────
export interface Resource { resource_key: string; name: string; capacity: number; skills: string | null; calendar: string | null; status: string }
export interface ScheduleRow {
  schedule_id: string; scenario_id: string; tag_id: string; operation: string; resource_key: string; seq: number;
  planned_start: string; planned_end: string; setup_min: number; run_min: number; priority: number;
  rule_used: string | null; actual_start: string | null; actual_end: string | null; variance_min: number | null; published: number;
}
export const getApsResources = () => get<{ resources: Resource[] }>(`/vps/aps/resources`);
export const upsertResource = (d: Partial<Resource>) => post(`/vps/aps/resources`, d) as Promise<Resource>;
export const getApsRules = () => get<{ rules: { key: string; label: string }[] }>(`/vps/aps/rules`);
export const getSchedule = (scenario = "base") => get<{ scenario: string; scenarios: string[]; rows: ScheduleRow[] }>(`/vps/aps/schedule?scenario=${scenario}`);
export const generateSchedule = (scenario: string, rule: string) => post(`/vps/aps/schedule?scenario=${scenario}&rule=${rule}`) as Promise<{ operations: number }>;
export const publishSchedule = (scenario = "base") => post(`/vps/aps/publish?scenario=${scenario}`);
export const getApsKpis = (scenario = "base") => get<Record<string, number | string | boolean | null>>(`/vps/aps/kpis?scenario=${scenario}`);
export interface ResLoad { resource_key: string; busy_min: number; ops: number; cap: number; util: number; bottleneck: boolean }
export const getApsLoad = (scenario = "base") => get<{ load: ResLoad[] }>(`/vps/aps/load?scenario=${scenario}`);
export interface CompareRow { rule: string; label: string; scenario: string; kpis: Record<string, number | string | boolean | null> }
export const compareAps = (rules = "prioridade,menor_prazo,fifo") => get<{ comparison: CompareRow[] }>(`/vps/aps/compare?rules=${rules}`);
export const ctpAps = (qty: number, due?: string) => post(`/vps/aps/ctp`, { qty, due }) as Promise<{ ctp_end: string; lead_h: number; on_time: boolean | null; qty: number; due: string | null }>;
export const expediteOp = (tagId: string) => post(`/vps/aps/expedite?tag_id=${encodeURIComponent(tagId)}`) as Promise<{ expedited: string[] }>;

// ── Multi-segmento + etiquetas ────────────────────────────────────────
export interface SegmentInfo { segment: string; template_id: string; label: string }
export const getSegments = () => get<{ segments: SegmentInfo[]; current: string }>(`/vps/segments`);
export const setGenesisSegment = (segment: string) => post(`/vps/bridge/segment`, { segment });
export const buildTagId = (segment: string, key: string, entity = "OP", instance = "01") =>
  get<{ tag_id: string }>(`/vps/tagid?segment=${segment}&entity=${entity}&key=${encodeURIComponent(key)}&instance=${instance}`);

// ── Gerador de Tags (etiquetas QR — VPS_Gerador_de_Tags.md) ──────────
export interface LabelData {
  type: string; segment: string; entity_type: string; natural_key: string; instance: string;
  parent?: string | null; cliente?: string | null; lote?: string | null; qtd?: string | null;
  estado?: string | null; phase?: string | null; sla?: string | null; template_id?: string | null;
  owner?: string | null; station?: string | null; emissor?: string | null;
  encode: string; size: string; print_batch?: string | null;
}
export interface GeneratedLabel extends LabelData { tag_id: string; qr_payload: string; qr_svg: string | null; print_batch: string }
export const tagGenerate = (d: LabelData) =>
  post(`/vps/tag/generate`, d) as Promise<GeneratedLabel>;
export const getLabelPrefill = (tagId: string) =>
  get<Partial<LabelData>>(`/vps/label/prefill/${encodeURIComponent(tagId)}`);
// URL do QR (SVG) p/ exibir a leitura no formato das etiquetas do sistema.
export const qrUrl = (data: string, ec = "Q") => `${API_BASE}/vps/qr?data=${encodeURIComponent(data)}&ec=${ec}`;

// ── Scanner de token (📷 APONTAR/ESCANEAR) ───────────────────────────
export interface StationAction { action: string; label: string; kind: string }
export interface ScanResult {
  ok: boolean; token?: string; tag_id?: string; action?: string; genesis?: boolean;
  state?: string; phase?: string; operator_id?: string | null; message?: string; frame?: boolean;
  resolved?: boolean; actions?: StationAction[]; info?: Record<string, string | null>;
}
export const scanToken = (body: { station: string; operator_id?: string | null; image_b64?: string; camera_id?: string; mtx_path?: string }) =>
  post(`/vps/scan`, body) as Promise<ScanResult>;
export const stationAction = (body: { tag_id: string; action: string; station: string; operator_id?: string | null; payload?: Record<string, unknown> }) =>
  post(`/vps/station/action`, body) as Promise<{ ok: boolean; action?: string; state?: string; phase?: string; operator_id?: string | null }>;

// ── Teste ponta a ponta ──────────────────────────────────────────────
export interface E2eStep {
  seq: number; cat: string; txt: string; ok: boolean; detail?: string;
  id?: string; node?: string; pill?: [string, string]; op?: string;
}
export interface E2eResult {
  steps: E2eStep[]; op_tag: string; passed: boolean;
  acceptance: Record<string, boolean>; kpis: Record<string, string>; expected_links: string[];
}
export const runE2e = () => post(`/vps/e2e/run`) as Promise<E2eResult>;
// Aplica o projeto PostgreSQL 'teste_sistema' ao cockpit (10 OPs visíveis)
export const importTeste = () => post(`/vps/import/teste`) as Promise<{ ok: boolean; tags: number; events: number; lineage: number; pendings: number; occurrences: number; schedule: number; erp_docs: number }>;

// ── Planejamento (Projetos/Cards) ────────────────────────────────────
export interface Project { project_id: string; code: string; name: string; segment: string; state: string; resource_pool: string | null; baseline_version: number; planned_start: string | null; tag_id: string | null; cards?: number }
export interface Card { card_id: string; project_id: string; code: string; title: string; card_type: string; state: string; resource_key: string | null; assigned_operator: string | null; priority: number; planned_effort?: number; planned_start: string | null; planned_end: string | null; pct_complete: number; tag_id: string | null; wbs_id: string | null }
export interface CardDep { dep_id: string; pred_card_id: string; succ_card_id: string; dep_type: string; lag_min: number }
export interface ProjectDetail extends Omit<Project, "cards"> { wbs: { wbs_id: string; code: string; name: string }[]; cards: Card[]; deps: CardDep[] }
export interface PvaRow { card_id: string; code: string; title: string; state: string; resource_key: string | null; operator: string | null; planned_start: string | null; planned_end: string | null; baseline_end: string | null; actual_start: string | null; actual_end: string | null; pct: number; tag_id: string | null }
export interface PlanVsActual { cards: PvaRow[]; kpis: Record<string, number | null> }
export interface CpmCard { card_id: string; code: string; title: string; es: number; ef: number; slack: number; critical: boolean }

export const getProjects = () => get<{ projects: Project[] }>(`/vps/projects`);
export const createProject = (d: Partial<Project>) => post(`/vps/projects`, d) as Promise<Project>;
export const getProject = (id: string) => get<ProjectDetail>(`/vps/project/${id}`);
export const addCard = (id: string, d: Partial<Card> & { code: string }) => post(`/vps/project/${id}/card`, d) as Promise<Card>;
export const addDep = (id: string, pred: string, succ: string, dep_type = "FS", lag_min = 0) => post(`/vps/project/${id}/dependency`, { pred_card_id: pred, succ_card_id: succ, dep_type, lag_min });
export const scheduleProject = (id: string) => post(`/vps/project/${id}/schedule`) as Promise<{ ok: boolean; scheduled: number; critical: string[] }>;
export const baselineProject = (id: string) => post(`/vps/project/${id}/baseline`) as Promise<{ ok: boolean; version: number }>;
export const getCriticalPath = (id: string) => get<{ cards: CpmCard[]; makespan_h: number }>(`/vps/project/${id}/critical-path`);
export const getPlanVsActual = (id: string) => get<PlanVsActual>(`/vps/project/${id}/plan-vs-actual`);
export const releaseCard = (cardId: string) => post(`/vps/card/${cardId}/release`) as Promise<Card>;
export const assignCard = (cardId: string, operator?: string, resource?: string) => post(`/vps/card/${cardId}/assign`, { operator, resource }) as Promise<Card>;
export const seedPlanning = () => post(`/vps/planning/seed`) as Promise<{ ok: boolean; project_id: string; code: string }>;

// ── Modais & Vínculos de dados ───────────────────────────────────────
export interface BoundField { modal: string; label: string; value: string | null; origin: string; editable: boolean }
export interface ModalGroup { id: string; title: string; fields: BoundField[] }
export interface ModalBindings { tag_id: string; modais: ModalGroup[]; origins: Record<string, string> }
export const getModal = (tagId: string) => get<ModalBindings>(`/vps/modal/${encodeURIComponent(tagId)}`);

// ── LGPD ──────────────────────────────────────────────────────────────
export interface Lgpd { blur: boolean; blur_available: boolean; retention_days: number; files: Record<string, number> }
export const getLgpd = () => get<Lgpd>(`/vps/lgpd`);
export const setLgpd = (blur: boolean) => post(`/vps/lgpd`, { blur });
export const sweepLgpd = () => post(`/vps/lgpd/sweep`) as Promise<{ removed: number; freed_mb: number; retention_days: number }>;

// ── Plataforma de Dados / BI (Gold GLX_) + Auditoria ─────────────────
export interface GoldModel { key: string; name: string }
export const getGoldModels = () => get<{ models: GoldModel[] }>(`/vps/gold`);

async function downloadBlob(path: string, filename: string) {
  const r = await fetch(`${API_BASE}${path}`);
  const blob = await r.blob();
  const u = URL.createObjectURL(blob);
  const a = document.createElement("a"); a.href = u; a.download = filename;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(u), 8000);
}
export const downloadGold = (model: string, name: string, fmt: "csv" | "json") =>
  downloadBlob(`/vps/gold/${model}?fmt=${fmt}`, `${name}.${fmt}`);
export const exportThread = (tagId: string, key: string) =>
  downloadBlob(`/vps/export/thread/${encodeURIComponent(tagId)}`, `VPS_AUDIT_${key}.json`);

// ── Live (WebSocket) ──────────────────────────────────────────────────
export function connectVpsLive(onEvents: (events: VpsEvent[]) => void): WebSocket {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws/vps`);
  ws.onmessage = (e) => {
    try { const m = JSON.parse(e.data); if (m.type === "events") onEvents(m.events); } catch { /* ignore */ }
  };
  return ws;
}

// ── Ponte Visão→VPS ──────────────────────────────────────────────────
export interface BridgeStatus { auto_capture: boolean; bindings: Record<string, string> }
export const getBridge = () => get<BridgeStatus>(`/vps/bridge`);
export async function setAutoCapture(on: boolean): Promise<BridgeStatus> {
  return (await fetch(`${API_BASE}/vps/bridge/auto`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ on }),
  })).json();
}
export async function bindSource(source_id: string, tag_id: string | null): Promise<{ bindings: Record<string, string> }> {
  return (await fetch(`${API_BASE}/vps/bridge/bind`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ source_id, tag_id }),
  })).json();
}

export interface CaptureIn {
  tag_id: string; action: string; parent_tag_id?: string; vision_mode?: string;
  confidence?: number; payload?: Record<string, unknown>; source_type?: string; station_id?: string;
}
export async function capture(body: CaptureIn): Promise<Record<string, unknown>> {
  return (await fetch(`${API_BASE}/vps/capture`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  })).json();
}
