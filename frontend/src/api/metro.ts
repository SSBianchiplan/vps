import { API_BASE } from "./config";

export type Pt = [number, number];

export interface Calibration {
  ref: string;
  scale_mm_per_px: number;
  valid_until: string | null;
  valid?: boolean;
}

export interface MeasureResult {
  ok: boolean;
  feature?: string;
  kind?: string;
  measured?: number;
  unit?: string;
  nominal?: number;
  tol?: [number, number];
  deviation?: number;
  verdict?: "CONFORME" | "NAO_CONFORME";
  uncertainty?: number;
  px?: number | null;
  calibration_ref?: string | null;
  calibration_valid?: boolean;
  message?: string;
}

export interface MetroKpis {
  measurements: number;
  CLD_Measurement_Pass_Rate: number | null;
  CLD_Cpk: Record<string, number>;
  CLD_Measurement_Uncertainty: number | null;
  CLD_Calibration_Validity: boolean;
  calibration: Calibration | null;
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

export async function metroStatus(): Promise<MetroKpis> {
  return j(await fetch(`${API_BASE}/metro/status`), "metro status");
}
export function metroCalibrate(ref: string, p1: Pt, p2: Pt, known_mm: number, frame_w: number, frame_h: number, valid_until?: string | null) {
  return post<{ ok: boolean; ref?: string; scale_mm_per_px?: number; message?: string }>(
    "/metro/calibrate", { ref, p1, p2, known_mm, frame_w, frame_h, valid_until: valid_until ?? null });
}
export function metroMeasure(body: {
  kind: string; points: Pt[]; frame_w: number; frame_h: number;
  feature: string; nominal: number; tol_lo: number; tol_hi: number; op_tag?: string | null;
}): Promise<MeasureResult> {
  return post("/metro/measure", body);
}
