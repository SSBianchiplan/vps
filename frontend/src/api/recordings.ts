import { API_BASE } from "./config";

export interface Recording {
  id: string;
  source_id: string;
  timestamp: string;
  mode: string;
  classes: Record<string, number>;
  trigger: "auto" | "manual";
}

export interface RecordingConfig {
  enabled: boolean;
  classes: string[];
  cooldown_s: number;
}

async function j<T>(res: Response, label: string): Promise<T> {
  if (!res.ok) throw new Error(`${label} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export function recordingFileUrl(id: string): string {
  return `${API_BASE}/recordings/${id}/file`;
}

export async function listRecordings(sourceId?: string, limit = 100): Promise<Recording[]> {
  const p = new URLSearchParams({ limit: String(limit) });
  if (sourceId) p.set("source_id", sourceId);
  const r = await j<{ recordings: Recording[] }>(await fetch(`${API_BASE}/recordings?${p}`), "recordings");
  return r.recordings;
}

export async function getRecordingConfig(): Promise<RecordingConfig> {
  return j(await fetch(`${API_BASE}/recordings/config`), "rec config");
}

export async function setRecordingConfig(patch: Partial<RecordingConfig>): Promise<RecordingConfig> {
  return j(
    await fetch(`${API_BASE}/recordings/config`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    }),
    "rec config set",
  );
}

export async function manualRecording(sourceId: string, imageB64: string, classes?: Record<string, number>): Promise<Recording> {
  return j(
    await fetch(`${API_BASE}/recordings/manual`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source_id: sourceId, image_b64: imageB64, classes: classes ?? null }),
    }),
    "rec manual",
  );
}
