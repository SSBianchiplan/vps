import { API_BASE } from "./config";

export interface Condition {
  field: string;
  op: string;
  value?: string | null;
  min_confidence?: number | null;
}
export interface ActionDef {
  type: string;
  target?: string;
  message?: string;
  payload_template?: Record<string, unknown>;
}
export interface Rule {
  rule_id: string;
  task_id: string | null;
  label: string;
  active: boolean;
  created_at: string;
  condition: Condition;
  actions: ActionDef[];
}
export interface ActionLog {
  action_id: string;
  rule_id: string | null;
  task_id: string | null;
  timestamp: string;
  action_type: string;
  target: string | null;
  status: string;
  http_status: number | null;
  error_message: string | null;
  retry_count: number;
}
export interface TaskRow { task_id: string; modo: string; created_at: string }

async function j<T>(r: Response, label: string): Promise<T> {
  if (!r.ok) throw new Error(`${label} -> ${r.status}`);
  return r.json() as Promise<T>;
}

export async function catalog() {
  return j<{ action_types: string[]; ops: string[] }>(await fetch(`${API_BASE}/actions/catalog`), "catalog");
}
export async function listTasks() {
  return j<TaskRow[]>(await fetch(`${API_BASE}/tasks`), "tasks");
}
export async function listRules(taskId: string) {
  return j<Rule[]>(await fetch(`${API_BASE}/tasks/${encodeURIComponent(taskId)}/rules`), "rules");
}
export async function createRule(taskId: string, body: { label: string; condition: Condition; actions: ActionDef[] }) {
  return j<Rule>(await fetch(`${API_BASE}/tasks/${encodeURIComponent(taskId)}/rules`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  }), "create rule");
}
export async function deleteRule(ruleId: string) {
  await fetch(`${API_BASE}/rules/${ruleId}`, { method: "DELETE" });
}
export async function toggleRule(ruleId: string, active: boolean) {
  await fetch(`${API_BASE}/rules/${ruleId}/toggle?active=${active}`, { method: "POST" });
}
export async function listActions(status?: string) {
  const q = status ? `?status=${status}` : "";
  return j<{ actions: ActionLog[] }>(await fetch(`${API_BASE}/actions${q}`), "actions").then((d) => d.actions);
}
export async function retryAction(id: string) {
  return j<{ status: string }>(await fetch(`${API_BASE}/actions/${id}/retry`, { method: "POST" }), "retry");
}
