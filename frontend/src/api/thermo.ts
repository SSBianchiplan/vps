import { API_BASE } from "./config";

export type Severity = "NORMAL" | "OBSERVAR" | "AGIR" | "CRITICO";

export interface ThermalAsset {
  asset_id: string;
  name: string;
  emissivity: number;
  t_min: number;
  t_max: number;
  t_abs_limit: number;
  delta_t_limit: number;
  baseline_tmax: number | null;
  baseline_ts: string | null;
  tag_id: string | null;
}

export interface ThermalResult {
  ok: boolean;
  asset_id: string;
  name: string;
  t_max: number;
  t_avg: number;
  delta_t: number;
  severity: Severity;
  baseline: number | null;
  trend_c_per_week: number;
  lead_days: number | null;
  hotspot: [number, number];
  emissivity: number;
  t_abs_limit: number;
  delta_t_limit: number;
  thermal_b64: string | null;
  algo: string;
}

export interface ThermalReading {
  t_max: number; delta_t: number; severity: Severity; event_ts: string;
}

export interface ThermoKpis {
  assets: number;
  CLD_Assets_At_Risk: number;
  CLD_Hotspots_By_Severity: Record<string, number>;
  CLD_Predictive_Lead_Time: number | null;
  algo: string;
  available?: boolean;
}

async function j<T>(res: Response, label: string): Promise<T> {
  if (!res.ok) throw new Error(`${label} -> ${res.status}`);
  return res.json() as Promise<T>;
}
function post<T>(path: string, body: unknown): Promise<T> {
  return fetch(`${API_BASE}${path}`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  }).then((r) => j<T>(r, path));
}

export async function thermoStatus(): Promise<ThermoKpis> {
  return j(await fetch(`${API_BASE}/thermo/status`), "thermo status");
}
export async function thermoAssets(): Promise<ThermalAsset[]> {
  const d = await j<{ assets: ThermalAsset[] }>(await fetch(`${API_BASE}/thermo/assets`), "thermo assets");
  return d.assets;
}
export function thermoUpsertAsset(body: Partial<ThermalAsset> & { asset_id: string }): Promise<ThermalAsset> {
  return post("/thermo/asset", body);
}
export function thermoAnalyze(asset_id: string, image_b64: string): Promise<ThermalResult> {
  return post("/thermo/analyze", { asset_id, image_b64 });
}
export function thermoBaseline(asset_id: string, image_b64: string): Promise<{ ok: boolean; baseline_tmax: number }> {
  return post("/thermo/baseline", { asset_id, image_b64 });
}
export async function thermoTrend(asset_id: string): Promise<ThermalReading[]> {
  const d = await j<{ readings: ThermalReading[] }>(await fetch(`${API_BASE}/thermo/trend/${encodeURIComponent(asset_id)}`), "thermo trend");
  return d.readings;
}
