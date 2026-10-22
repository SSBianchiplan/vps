// Streams ao vivo (drone/osmo) — relay RTMP→MediaMTX→player. spec_Drono.md + spec_osmo.md.
import { API_BASE } from "./config";

export interface AerialConfig {
  path: string;
  rtmp_host: string | null;
  rtmp_url: string | null;
  whep_proxy: string;
  hls_url: string;
  rtsp_url: string;
}
export interface AerialStatus { online: boolean; readers?: number; bytes_received?: number }
export interface AerialRec { recording: boolean; file?: string | null; size?: number; error?: string }
export interface AerialRecItem { name: string; size: number; ts: number }
export interface AerialTest { running: boolean; default_cmd?: string; error?: string }

// path opcional (default backend = drone_neo2). Osmo passa "osmo_pocket".
const q = (path?: string) => (path ? `?path=${encodeURIComponent(path)}` : "");

export async function getAerialConfig(path?: string): Promise<AerialConfig> {
  const r = await fetch(`${API_BASE}/aerial/config${q(path)}`);
  if (!r.ok) throw new Error(`aerial/config ${r.status}`);
  return r.json();
}

export async function getAerialStatus(path?: string): Promise<AerialStatus> {
  try { const r = await fetch(`${API_BASE}/aerial/status${q(path)}`); return r.ok ? await r.json() : { online: false }; }
  catch { return { online: false }; }
}

export async function getAerialTest(path?: string): Promise<AerialTest> {
  try { const r = await fetch(`${API_BASE}/aerial/test${q(path)}`); return r.ok ? await r.json() : { running: false }; }
  catch { return { running: false }; }
}
export async function startAerialTest(command?: string, path?: string): Promise<AerialTest> {
  const r = await fetch(`${API_BASE}/aerial/test/start${q(path)}`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ command }),
  });
  return r.json();
}
export async function stopAerialTest(path?: string): Promise<AerialTest> {
  return (await fetch(`${API_BASE}/aerial/test/stop${q(path)}`, { method: "POST" })).json();
}

export async function getAerialRec(path?: string): Promise<AerialRec> {
  try { const r = await fetch(`${API_BASE}/aerial/record${q(path)}`); return r.ok ? await r.json() : { recording: false }; }
  catch { return { recording: false }; }
}
export async function startAerialRec(path?: string): Promise<AerialRec> {
  return (await fetch(`${API_BASE}/aerial/record/start${q(path)}`, { method: "POST" })).json();
}
export async function stopAerialRec(path?: string): Promise<AerialRec> {
  return (await fetch(`${API_BASE}/aerial/record/stop${q(path)}`, { method: "POST" })).json();
}
export async function listAerialRecordings(path?: string): Promise<AerialRecItem[]> {
  try { const r = await fetch(`${API_BASE}/aerial/recordings${q(path)}`); return r.ok ? (await r.json()).items : []; }
  catch { return []; }
}
export function aerialRecordingUrl(name: string): string {
  return `${API_BASE}/aerial/recordings/${encodeURIComponent(name)}`;
}

// Encaminha o SDP offer ao WHEP (via backend, same-origin) e devolve o answer.
export async function whep(offerSdp: string, path?: string): Promise<string> {
  const r = await fetch(`${API_BASE}/aerial/whep${q(path)}`, {
    method: "POST", headers: { "Content-Type": "application/sdp" }, body: offerSdp,
  });
  if (!r.ok) throw new Error(`WHEP ${r.status}`);
  return r.text();
}
