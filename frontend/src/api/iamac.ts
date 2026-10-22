import { API_BASE } from "./config";

export interface Citation { source: string; title: string }
export interface AskResult { id: number; answer: string; citations: Citation[]; grounded: boolean; engine: string }
export interface Insight { kind: string; text: string; evidence: string }
export interface EvalResult { score: number; grounding: number; passed: number; total: number }

export interface ModelEntry {
  id: string; provider: string; model: string | null; label: string; note: string;
  available: boolean; loaded: boolean | null; current: boolean;
}

export interface IaStatus {
  foundation: string;
  current_model: string;
  models: ModelEntry[];
  vlm_available: boolean;
  lmstudio_available: boolean;
  lmstudio_url: string;
  apple_silicon: boolean;
  mlx_available: boolean;
  models_dir: string;
  frameworks: { name: string; role: string; ready: boolean }[];
  knowledge_chunks: number;
  flywheel: { interactions: number; feedback_pos: number; feedback_neg: number; evals: number };
  last_eval: { version: string; score: number; grounding: number; ts: string } | null;
  guardrails: string[];
}

async function j<T>(res: Response, label: string): Promise<T> {
  if (!res.ok) throw new Error(`${label} -> ${res.status}`);
  return res.json() as Promise<T>;
}
function post<T>(path: string, body?: unknown): Promise<T> {
  return fetch(`${API_BASE}${path}`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: body != null ? JSON.stringify(body) : undefined,
  }).then((r) => j<T>(r, path));
}

export async function iaStatus(): Promise<IaStatus> { return j(await fetch(`${API_BASE}/iamac/status`), "ia status"); }
export function iaAsk(question: string): Promise<AskResult> { return post("/iamac/ask", { question }); }
export function iaFeedback(id: number, vote: number) { return post<{ ok: boolean }>("/iamac/feedback", { id, vote }); }
export function iaEval(): Promise<EvalResult> { return post("/iamac/eval"); }
export function iaReindex(): Promise<{ chunks: number }> { return post("/iamac/reindex"); }
export async function iaInsights(): Promise<Insight[]> {
  const d = await j<{ insights: Insight[] }>(await fetch(`${API_BASE}/iamac/insights`), "ia insights");
  return d.insights;
}
export function iaSetModel(model_id: string): Promise<{ ok: boolean; current?: string; message?: string }> {
  return post("/iamac/model", { model_id });
}
