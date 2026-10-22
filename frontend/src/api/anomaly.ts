import { API_BASE } from "./config";

export interface AnomalyScore {
  supported: boolean;
  fitted?: boolean;
  anomaly_score?: number;
  distance?: number;
  tau?: number;
  anomalo?: boolean;
  n_ref?: number;
  message?: string;
}

async function j<T>(res: Response, label: string): Promise<T> {
  if (!res.ok) throw new Error(`${label} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export async function anomalyStatus(profile: string): Promise<{ fitted: boolean; n_ref: number; supported: boolean; tau?: number }> {
  return j(await fetch(`${API_BASE}/anomaly/status?profile=${encodeURIComponent(profile)}`), "anomaly status");
}

export async function anomalyFit(cameraId: string, samples = 8): Promise<{ ok: boolean; n_ref?: number; message?: string }> {
  return j(await fetch(`${API_BASE}/anomaly/fit`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ camera_id: cameraId, samples }),
  }), "anomaly fit");
}

export async function anomalyFitImages(profile: string, imagesB64: string[]): Promise<{ ok: boolean; n_ref?: number; message?: string }> {
  return j(await fetch(`${API_BASE}/anomaly/fit`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ profile, images_b64: imagesB64 }),
  }), "anomaly fit imgs");
}

export async function anomalyScore(profile: string, imageB64: string): Promise<AnomalyScore> {
  return j(await fetch(`${API_BASE}/anomaly/score`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ profile, image_b64: imageB64 }),
  }), "anomaly score");
}
