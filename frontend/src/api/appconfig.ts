import { API_BASE } from "./config";

export type Tier = "basico" | "avancado";
export interface UiComponent { id: string; name: string; en: string; tier: Tier; group: string; wave: number; enabled: boolean }
export interface SupLinkField { name: string; label: string; type: "text" | "select" | "bool"; options?: string[]; required: string[]; placeholder?: string; default?: string }
export interface UiRollout { current_wave: number; waves: number; vps_aligned: boolean; note?: string }
export interface ConfigAll {
  keys: string[]; ui_components: UiComponent[]; sup_link_fields: SupLinkField[]; ui_rollout: UiRollout; appearance: unknown;
}

async function j<T>(res: Response, label: string): Promise<T> {
  if (!res.ok) throw new Error(`${label} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export async function getConfigAll(): Promise<ConfigAll> { return j(await fetch(`${API_BASE}/config`), "config"); }
export async function getConfig<T = unknown>(key: string): Promise<T> {
  const d = await j<{ key: string; value: T }>(await fetch(`${API_BASE}/config/${encodeURIComponent(key)}`), "config get");
  return d.value;
}
export async function putConfig(key: string, value: unknown): Promise<{ ok: boolean }> {
  return j(await fetch(`${API_BASE}/config/${encodeURIComponent(key)}`, {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ value }),
  }), "config put");
}
export async function setWave(current_wave: number): Promise<UiRollout> {
  return j(await fetch(`${API_BASE}/config/wave`, {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ current_wave }),
  }), "config wave");
}

// Validação local (espelha o schema do backend) — campos obrigatórios por kind do link.
export function missingFields(link: Record<string, unknown>, fields: SupLinkField[]): string[] {
  const kind = String(link.kind || "process");
  return fields.filter((f) => f.required.includes(kind)).map((f) => f.name)
    .filter((n) => { const v = link[n]; return v == null || (typeof v === "string" && !v.trim()); });
}
