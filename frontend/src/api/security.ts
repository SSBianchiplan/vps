import { API_BASE } from "./config";

export type Status = "aplicado" | "parcial" | "planejado" | "em curso";
export interface Check { l: string; s: Status; ev: string }
export interface CsfFunction { key: string; nist: string; icon: string; score: number; checks: Check[] }
export interface Posture { functions: CsfFunction[]; overall: number; audit_events: number }
export interface Threat { surface: string; threat: string; mitig: string; status: Status }
export interface Framework { code: string; dom: string; uso: string; aplica: string }
export interface RoadmapItem { fase: string; entrega: string; status: Status }
export interface SecEvent { event_ts: string; category: string; action: string; severity: string; actor: string | null; summary: string | null }
export interface Overview { posture: Posture; threats: Threat[]; frameworks: Framework[]; roadmap: RoadmapItem[]; events: SecEvent[] }
export interface Integrity { count: number; head_hash: string; ok: boolean; anomalies: { event_id: string; issue: string }[]; algo: string }

async function j<T>(res: Response, label: string): Promise<T> {
  if (!res.ok) throw new Error(`${label} -> ${res.status}`);
  return res.json() as Promise<T>;
}
export async function secOverview(): Promise<Overview> { return j(await fetch(`${API_BASE}/security/overview`), "sec overview"); }
export async function secIntegrity(): Promise<Integrity> { return j(await fetch(`${API_BASE}/security/integrity`), "sec integrity"); }
