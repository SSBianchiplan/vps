import { API_BASE } from "./config";
import type { Mode } from "../types";

export type Severity = "info" | "ok" | "nok" | "alerta" | "warn";
export type Category =
  | "INFERENCE" | "CAMERA" | "DATA" | "ACTION" | "RECORDING" | "VPS" | "MONITOR" | "SYSTEM";

// Evento da trilha de rastreabilidade total (superset; mantém aliases legados).
export interface AuditEvent {
  event_id: string;
  event_ts: string;
  timestamp: string;            // alias de event_ts
  category: Category;
  action: string;
  severity: Severity;
  severidade: Exclude<Severity, "warn">;  // legado (warn→alerta)
  actor: string | null;
  source_id: string | null;
  source_label: string | null;
  entity_type: string | null;
  entity_id: string | null;
  summary: string;
  titulo: string;               // legado = summary
  correlation_id: string | null;
  payload: Record<string, unknown> | null;
  icone: string;
  // legados de inferência
  detection_id: string;
  mode: Mode | null;
  pipeline: string | null;
  latency_ms: number | null;
  confidence: number | null;
}
export type VisionEvent = AuditEvent;  // compat com consumidores existentes

export interface EventCategory {
  key: Category;
  label: string;
  icon: string;
  count: number;
}

export interface EventSource {
  source_id: string;
  tipo?: string | null;
  descricao: string | null;
}

export interface EventsFilter {
  category?: Category | null;
  action?: string | null;
  mode?: Mode | null;
  sourceId?: string | null;
  severity?: Severity | null;
  q?: string | null;
  since?: string | null;
  limit?: number;
}

async function jsonOrThrow<T>(res: Response, label: string): Promise<T> {
  if (!res.ok) throw new Error(`${label} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export async function listEvents(f: EventsFilter = {}): Promise<AuditEvent[]> {
  const p = new URLSearchParams();
  if (f.category) p.set("category", f.category);
  if (f.action) p.set("action", f.action);
  if (f.mode) p.set("mode", f.mode);
  if (f.sourceId) p.set("source_id", f.sourceId);
  if (f.severity) p.set("severity", f.severity);
  if (f.q) p.set("q", f.q);
  if (f.since) p.set("since", f.since);
  p.set("limit", String(f.limit ?? 300));
  const data = await jsonOrThrow<{ events: AuditEvent[] }>(
    await fetch(`${API_BASE}/events?${p}`),
    "events",
  );
  return data.events;
}

export interface EventsSummary {
  total_events: number;
  alerts: number;
  by_day: { day: string; count: number }[];
  by_category: Record<string, number>;
  by_severity: Record<string, number>;
  by_mode: Record<string, number>;
}

export async function eventsSummary(): Promise<EventsSummary> {
  return jsonOrThrow(await fetch(`${API_BASE}/events/summary`), "events summary");
}

export async function listEventCategories(): Promise<EventCategory[]> {
  const data = await jsonOrThrow<{ categories: EventCategory[] }>(
    await fetch(`${API_BASE}/events/categories`),
    "event categories",
  );
  return data.categories;
}

export async function listEventSources(): Promise<EventSource[]> {
  const data = await jsonOrThrow<{ sources: EventSource[] }>(
    await fetch(`${API_BASE}/events/sources`),
    "event sources",
  );
  return data.sources;
}

export interface SyncResult {
  ok: boolean;
  synced?: number;
  scanned?: number;
  pg_total?: number;
  error?: string;
}

export async function syncAuditPg(): Promise<SyncResult> {
  return jsonOrThrow(
    await fetch(`${API_BASE}/events/sync-pg`, { method: "POST" }),
    "sync audit pg",
  );
}
