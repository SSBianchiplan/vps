import { API_BASE } from "./config";

export interface FaceOperator {
  operator_id: string;
  name: string;
  algo: string;
  consent_ts: string;
  created_at: string;
}

export interface IdentifyResult {
  ok: boolean;
  live?: boolean;
  matched?: boolean;
  operator_id?: string;
  name?: string;
  score?: number;
  threshold?: number;
  bbox?: number[];      // [x,y,w,h] normalizado
  faces?: number;
  message?: string;
}

export interface FaceKpis {
  enrolled: number;
  CLD_Auth_Success_Rate: number | null;
  CLD_Liveness_Block_Rate: number;
  granted: number;
  denied: number;
  liveness_failed: number;
  threshold: number;
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

export async function faceStatus(): Promise<FaceKpis> {
  return j(await fetch(`${API_BASE}/face/status`), "face status");
}

export async function faceGallery(): Promise<FaceOperator[]> {
  const d = await j<{ operators: FaceOperator[] }>(await fetch(`${API_BASE}/face/gallery`), "face gallery");
  return d.operators;
}
export function faceEnroll(operator_id: string, name: string, image_b64: string, consent: boolean) {
  return post<{ ok: boolean; message?: string; name?: string; dim?: number; sharpness?: number }>(
    "/face/enroll", { operator_id, name, image_b64, consent });
}
export function faceIdentify(image_b64: string) {
  return post<IdentifyResult>("/face/identify", { image_b64 });
}
export function faceVerify(operator_id: string, image_b64: string) {
  return post<IdentifyResult & { verified?: boolean }>("/face/verify", { operator_id, image_b64 });
}
export async function faceRevoke(operator_id: string): Promise<{ ok: boolean }> {
  return j(await fetch(`${API_BASE}/face/template/${encodeURIComponent(operator_id)}`, { method: "DELETE" }), "face revoke");
}
