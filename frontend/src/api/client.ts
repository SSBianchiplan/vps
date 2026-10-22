import { API_BASE } from "./config";
import type { Capabilities, InferenceResult, TaskConfig } from "../types";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`GET ${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export async function fetchCapabilities(): Promise<Capabilities> {
  return get<Capabilities>("/capabilities");
}

export async function createTask(task: TaskConfig): Promise<string> {
  const res = await fetch(`${API_BASE}/tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(task),
  });
  if (!res.ok) throw new Error(`POST /tasks -> ${res.status}`);
  const data = (await res.json()) as { task_id: string };
  return data.task_id;
}

/** Inferência one-shot (snapshot único) via REST — usada pelo runner do modal. */
export async function inferOnce(
  imageB64: string,
  task: TaskConfig,
  sourceId?: string,
): Promise<InferenceResult> {
  const res = await fetch(`${API_BASE}/infer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ image_b64: imageB64, task, source_id: sourceId ?? null }),
  });
  if (!res.ok) {
    let msg = `infer -> ${res.status}`;
    try {
      const b = await res.json();
      if (b?.detail?.message) msg = b.detail.message;
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
  return res.json() as Promise<InferenceResult>;
}

export function exportUrl(taskId: string | null, format: "csv" | "json"): string {
  const params = new URLSearchParams({ format });
  if (taskId) params.set("task_id", taskId);
  return `${API_BASE}/export?${params.toString()}`;
}
