import { API_BASE } from "./config";

export interface OtAsset {
  asset_id: string; name: string; kind: string; mode: string;
  protocol: string | null; endpoint: string | null; tag_id: string | null;
}
export interface OtEvent {
  asset_id: string; action: string; tag: string | null; value: string;
  code: number | null; quality: string | null; source: string; source_ts: string;
}
export interface OtKpis {
  CLD_OEE: number;
  CLD_Machine_Availability: number;
  CLD_Production_Count: number;
  CLD_Cycle_Time_Observed: number | null;
  CLD_IO_Fault_Rate: number;
  CLD_Downtime_By_Reason: Record<string, number>;
  CLD_Count_Reconciliation: string;
  samples: number;
}
export interface OtStatus extends OtKpis {
  opcua_available: boolean; read_only: boolean; purdue_zone: string; assets: number;
}

async function j<T>(res: Response, label: string): Promise<T> {
  if (!res.ok) throw new Error(`${label} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export async function otStatus(): Promise<OtStatus> { return j(await fetch(`${API_BASE}/automation/status`), "ot status"); }
export async function otAssets(): Promise<{ assets: OtAsset[]; demo: Partial<OtAsset>[] }> {
  return j(await fetch(`${API_BASE}/automation/assets`), "ot assets");
}
export async function otEvents(asset_id?: string): Promise<OtEvent[]> {
  const q = asset_id ? `?asset_id=${encodeURIComponent(asset_id)}` : "";
  const d = await j<{ events: OtEvent[] }>(await fetch(`${API_BASE}/automation/events${q}`), "ot events");
  return d.events;
}
export async function otSimulate(asset_id?: string): Promise<{ ok: boolean; count: number }> {
  const q = asset_id ? `?asset_id=${encodeURIComponent(asset_id)}` : "";
  return j(await fetch(`${API_BASE}/automation/simulate${q}`, { method: "POST" }), "ot simulate");
}
export interface OtAlarm { asset_id: string; action: string; value: string; code: number | null; source_ts: string; active: boolean }
export async function otAlarms(): Promise<OtAlarm[]> {
  const d = await j<{ alarms: OtAlarm[] }>(await fetch(`${API_BASE}/automation/alarms`), "ot alarms");
  return d.alarms;
}
export async function otAck(asset_id: string): Promise<{ ok: boolean }> {
  return j(await fetch(`${API_BASE}/automation/ack`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ asset_id }),
  }), "ot ack");
}
export async function otAckAll(): Promise<{ ok: boolean; count: number }> {
  return j(await fetch(`${API_BASE}/automation/ack_all`, { method: "POST" }), "ot ack_all");
}
export interface VisionResult { ok: boolean; asset_id: string; result: "PASS" | "FAIL"; confidence: number; defect: string | null }
export async function otVisionInspect(asset_id?: string): Promise<VisionResult> {
  const q = asset_id ? `?asset_id=${encodeURIComponent(asset_id)}` : "";
  return j(await fetch(`${API_BASE}/automation/vision_inspect${q}`, { method: "POST" }), "vision inspect");
}
export interface AlarmQr { asset_id: string; alarm: OtAlarm | null; work_order: string; payload: string; active: boolean; generated_at: string; svg: string }
export async function otAlarmQr(asset_id?: string): Promise<AlarmQr> {
  const q = asset_id ? `?asset_id=${encodeURIComponent(asset_id)}` : "";
  return j(await fetch(`${API_BASE}/automation/alarm_qr${q}`), "alarm qr");
}

export type WType =
  | "label" | "tag" | "gauge" | "tank" | "valve" | "pump" | "fan" | "motor" | "machine" | "lamp" | "switch" | "button"
  | "pipe" | "arrow" | "process" | "decision" | "terminator" | "vision";
export type LinkKind = "process" | "signal" | "electric" | "vision";
export type ActionKind = "simulate" | "ack" | "ackAll" | "modal" | "navigate" | "vision" | "qr" | "report";
export interface Widget {
  id: string; type: WType; x: number; y: number; w: number; h: number;
  label?: string; text?: string; unit?: string; color?: string; max?: number;
  asset?: string; action?: string; rot?: number; z?: number;
  action_kind?: ActionKind; action_target?: string;
}
export interface Link {
  id: string; from: string; to: string; kind: LinkKind; animated?: boolean; label?: string; color?: string;
  // campos do processo (supervisório avançado) — obrigatórios por kind (ver schema sup_link_fields)
  tag?: string; direction?: "uni" | "bi"; priority?: "baixa" | "normal" | "alta" | "critica";
  medium?: string; signal_type?: string; diameter?: string; engineering_unit?: string;
  interlock?: boolean; description?: string;
}
export interface Synoptic { name: string; widgets: Widget[]; links: Link[] }

export async function otSynoptic(name = "default"): Promise<Synoptic> {
  return j(await fetch(`${API_BASE}/automation/synoptic?name=${encodeURIComponent(name)}`), "synoptic");
}
export async function otSaveSynoptic(name: string, widgets: Widget[], links: Link[]): Promise<{ ok: boolean }> {
  return j(await fetch(`${API_BASE}/automation/synoptic`, {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, widgets, links }),
  }), "save synoptic");
}
