import { API_BASE } from "./config";

export interface DiscoveredCamera {
  ip: string;
  ports: number[];
  onvif: { name: string | null; hardware: string | null; xaddrs: string[] } | null;
  rtsp_candidates: string[];
  likely_camera: boolean;
}

export interface ScanResult {
  local_ip: string | null;
  subnet: string | null;
  scanned_ports: number[];
  cameras: DiscoveredCamera[];
  opencv: boolean;
}

export interface SavedCamera {
  id: string;
  name: string;
  ip: string;
  port: number;
  path: string;
  username: string | null;
  has_password: boolean;
  url: string;
  enabled?: boolean;   // liga/desliga system-wide (raiz no backend)
  serial?: string | null;
  provider?: string | null;
  cloud?: boolean;     // câmera de nuvem (P2P) sem IP local ainda
}

// Liga/desliga a câmera no sistema todo (persiste no backend). Retorna a câmera atualizada.
export async function setCameraEnabled(id: string, enabled: boolean): Promise<SavedCamera> {
  const r = await fetch(`${API_BASE}/cameras/${id}/enabled`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ enabled }),
  });
  return r.json();
}

export interface SnapshotResult {
  image_b64: string;
  media_type: string;
}

export interface SnapshotOpts {
  cameraId?: string;
  url?: string;
  username?: string;
  password?: string;
  maxW?: number; // largura-alvo da captura (0/undefined = padrão do backend)
}

async function jsonOrThrow<T>(res: Response, label: string): Promise<T> {
  if (!res.ok) {
    let msg = `${label} -> ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail?.message) msg = body.detail.message;
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

export async function scanCameras(timeout = 3, full = false): Promise<ScanResult> {
  const params = new URLSearchParams({ timeout: String(timeout), full: String(full) });
  return jsonOrThrow(await fetch(`${API_BASE}/cameras/scan?${params}`), "scan");
}

export async function listSavedCameras(): Promise<SavedCamera[]> {
  return jsonOrThrow(await fetch(`${API_BASE}/cameras/saved`), "saved");
}

export async function addSavedCamera(body: {
  name: string;
  ip: string;
  username?: string;
  password?: string;
  port?: number;
  path?: string;
  serial?: string;
  provider?: string;
  share_key?: string;
}): Promise<SavedCamera> {
  return jsonOrThrow(
    await fetch(`${API_BASE}/cameras/saved`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
    "add saved",
  );
}

export async function deleteSavedCamera(id: string): Promise<void> {
  await fetch(`${API_BASE}/cameras/saved/${id}`, { method: "DELETE" });
}

export async function resolveSavedCamera(id: string, timeout = 3): Promise<{ found: boolean; camera: SavedCamera; candidates: DiscoveredCamera[] }> {
  return jsonOrThrow(
    await fetch(`${API_BASE}/cameras/saved/${id}/resolve?timeout=${timeout}`, { method: "POST" }),
    "resolve camera",
  );
}

export async function decodeQr(image_b64: string): Promise<{ text: string | null }> {
  return jsonOrThrow(
    await fetch(`${API_BASE}/cameras/decode_qr`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ image_b64 }),
    }),
    "decode qr",
  );
}

export interface CamRec { recording: boolean; file?: string | null; size?: number; error?: string }
export async function getCamRecord(id: string): Promise<CamRec> {
  try { const r = await fetch(`${API_BASE}/cameras/${id}/record`); return r.ok ? await r.json() : { recording: false }; }
  catch { return { recording: false }; }
}
export async function startCamRecord(id: string): Promise<CamRec> {
  return (await fetch(`${API_BASE}/cameras/${id}/record/start`, { method: "POST" })).json();
}
export async function stopCamRecord(id: string): Promise<CamRec> {
  return (await fetch(`${API_BASE}/cameras/${id}/record/stop`, { method: "POST" })).json();
}

export interface StreamStats { streams: number; bytes: number }
/** Vazão agregada dos streams de câmera ativos (monitoramento do Painel). */
export async function getStreamStats(): Promise<StreamStats> {
  try { const r = await fetch(`${API_BASE}/cameras/streams/stats`); return r.ok ? await r.json() : { streams: 0, bytes: 0 }; }
  catch { return { streams: 0, bytes: 0 }; }
}

/** Path do MediaMTX (drone/osmo) numa URL rtsp local, ou null. */
export function mtxPath(url?: string): string | null {
  const m = (url || "").match(/^rtsps?:\/\/localhost:8554\/([\w-]+)/);
  return m ? m[1] : null;
}
/** MJPEG ao vivo de um path do MediaMTX (preview suave no Estúdio). */
export function mtxMjpegUrl(path: string, w?: number): string {
  return `${API_BASE}/cameras/mtx/${path}/mjpeg${w ? `?w=${w}` : ""}`;
}

/** URL do stream MJPEG ao vivo. sub=true usa substream baixa-res; w = largura-alvo. */
export function mjpegUrl(cameraId: string, sub = false, w?: number): string {
  const q = new URLSearchParams();
  if (sub) q.set("sub", "1");
  if (w) q.set("w", String(w));
  const qs = q.toString();
  return `${API_BASE}/cameras/${cameraId}/mjpeg${qs ? `?${qs}` : ""}`;
}

export interface PtzResult {
  ok: boolean;
  supported: boolean;
  message?: string;
}

export async function ptzMove(
  cameraId: string,
  v: { pan?: number; tilt?: number; zoom?: number },
): Promise<PtzResult> {
  return jsonOrThrow(
    await fetch(`${API_BASE}/cameras/ptz/move`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ camera_id: cameraId, pan: v.pan ?? 0, tilt: v.tilt ?? 0, zoom: v.zoom ?? 0 }),
    }),
    "ptz move",
  );
}

export interface PtzPreset {
  token: string;
  name: string;
}

export async function listPresets(cameraId: string): Promise<{ ok: boolean; supported: boolean; presets: PtzPreset[]; message?: string }> {
  return jsonOrThrow(await fetch(`${API_BASE}/cameras/${cameraId}/ptz/presets`), "presets");
}

export async function savePreset(cameraId: string, name?: string): Promise<{ ok: boolean; supported: boolean; preset_token?: string; name?: string; message?: string }> {
  return jsonOrThrow(
    await fetch(`${API_BASE}/cameras/${cameraId}/ptz/presets`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: name ?? null }),
    }),
    "save preset",
  );
}

export async function gotoPreset(cameraId: string, token: string): Promise<PtzResult> {
  return jsonOrThrow(await fetch(`${API_BASE}/cameras/${cameraId}/ptz/presets/${encodeURIComponent(token)}/goto`, { method: "POST" }), "goto preset");
}

export async function deletePreset(cameraId: string, token: string): Promise<PtzResult> {
  return jsonOrThrow(await fetch(`${API_BASE}/cameras/${cameraId}/ptz/presets/${encodeURIComponent(token)}`, { method: "DELETE" }), "del preset");
}

export async function ptzStop(cameraId: string): Promise<PtzResult> {
  return jsonOrThrow(
    await fetch(`${API_BASE}/cameras/ptz/stop`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ camera_id: cameraId }),
    }),
    "ptz stop",
  );
}

// ── Configurações do modo de câmera (ONVIF Imaging) ─────────────────
export interface ImagingSettings {
  supported: boolean;
  message?: string;
  video_source_token?: string;
  ir_cut_filter?: "ON" | "OFF" | "AUTO" | null;   // ON=dia(cor) · OFF=noite(IR) · AUTO
  brightness?: number | null;
  contrast?: number | null;
  color_saturation?: number | null;
  sharpness?: number | null;
}

export interface ImagingPatch {
  ir_cut_filter?: "ON" | "OFF" | "AUTO";
  brightness?: number;
  contrast?: number;
  color_saturation?: number;
  sharpness?: number;
}

export async function getImaging(cameraId: string): Promise<ImagingSettings> {
  return jsonOrThrow(await fetch(`${API_BASE}/cameras/${cameraId}/imaging`), "imaging get");
}

export async function setImaging(cameraId: string, patch: ImagingPatch): Promise<{ ok: boolean; supported: boolean; message?: string }> {
  return jsonOrThrow(
    await fetch(`${API_BASE}/cameras/${cameraId}/imaging`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    }),
    "imaging set",
  );
}

export interface LightResult { ok: boolean; supported: boolean; on?: boolean; aux?: string; message?: string }

/** Controla a luz LED branca da câmera IP. mode "auto" = acende na detecção. */
export async function setCameraLight(
  cameraId: string, on: boolean, mode: "manual" | "auto" = "manual", kind: "white" | "ir" = "white",
): Promise<LightResult> {
  return jsonOrThrow(
    await fetch(`${API_BASE}/cameras/${cameraId}/light`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ on, kind, mode }),
    }),
    "light set",
  );
}

export async function snapshot(opts: SnapshotOpts): Promise<SnapshotResult> {
  const body = opts.cameraId
    ? { camera_id: opts.cameraId, max_w: opts.maxW ?? null }
    : { url: opts.url, username: opts.username || null, password: opts.password || null, max_w: opts.maxW ?? null };
  return jsonOrThrow(
    await fetch(`${API_BASE}/cameras/snapshot`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
    "snapshot",
  );
}
