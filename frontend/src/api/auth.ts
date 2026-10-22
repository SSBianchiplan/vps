import { API_BASE } from "./config";

export type Role = "admin" | "operador" | "view";

export interface AuthUser { operator_id: string; name: string; role: Role; method?: string }
export interface AccessUser {
  operator_id: string; name: string; role: Role; active: boolean;
  has_pin: boolean; has_face: boolean; created_at: string;
}
export interface MatrixRow { cap: string; admin: boolean; operador: boolean; view: boolean }

const TOKEN_KEY = "vd-auth-token";

export function getToken(): string { try { return localStorage.getItem(TOKEN_KEY) || ""; } catch { return ""; } }
function setToken(t: string) { try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY); } catch { /* */ } }
function hdr(): Record<string, string> { const t = getToken(); return t ? { "X-Auth-Token": t } : {}; }

async function j<T>(res: Response, label: string): Promise<T> {
  if (!res.ok) throw new Error(`${label} -> ${res.status}`);
  return res.json() as Promise<T>;
}
function post<T>(path: string, body?: unknown): Promise<T> {
  return fetch(`${API_BASE}${path}`, {
    method: "POST", headers: { "Content-Type": "application/json", ...hdr() },
    body: body != null ? JSON.stringify(body) : undefined,
  }).then((r) => j<T>(r, path));
}

export async function authState(): Promise<{ bootstrap_needed: boolean; roles: Role[] }> {
  return j(await fetch(`${API_BASE}/auth/state`), "auth state");
}
export async function me(): Promise<AuthUser | null> {
  const d = await j<{ authenticated: boolean; user: AuthUser | null }>(
    await fetch(`${API_BASE}/auth/me`, { headers: hdr() }), "me");
  return d.user;
}
type LoginResp = { ok: boolean; token?: string; user?: AuthUser; message?: string; live?: boolean };
function handle(r: LoginResp): LoginResp { if (r.ok && r.token) setToken(r.token); return r; }

export async function loginFace(image_b64: string): Promise<LoginResp> { return handle(await post("/auth/login/face", { image_b64 })); }
export async function loginPin(operator_id: string, pin: string): Promise<LoginResp> { return handle(await post("/auth/login/pin", { operator_id, pin })); }
export async function bootstrap(name: string, pin: string): Promise<LoginResp> { return handle(await post("/auth/bootstrap", { name, pin })); }
export async function logout(): Promise<void> { try { await post("/auth/logout"); } finally { setToken(""); } }

export async function matrix(): Promise<{ matrix: MatrixRow[]; roles: Role[] }> {
  return j(await fetch(`${API_BASE}/auth/matrix`), "matrix");
}
export async function listUsers(): Promise<AccessUser[]> {
  const d = await j<{ users: AccessUser[] }>(await fetch(`${API_BASE}/auth/users`, { headers: hdr() }), "users");
  return d.users;
}
export function createUser(body: { name: string; role: Role; pin?: string; face_b64?: string }) {
  return post<{ ok: boolean; operator_id?: string; message?: string }>("/auth/users", body);
}
export function setUserRole(operator_id: string, role: Role) { return post<{ ok: boolean }>(`/auth/users/${operator_id}/role`, { role }); }
export function setUserActive(operator_id: string, active: boolean) { return post<{ ok: boolean }>(`/auth/users/${operator_id}/active`, { active }); }
export function enrollUserFace(operator_id: string, image_b64: string) { return post<{ ok: boolean; message?: string }>(`/auth/users/${operator_id}/face`, { image_b64 }); }
export async function deleteUser(operator_id: string): Promise<{ ok: boolean }> {
  return j(await fetch(`${API_BASE}/auth/users/${operator_id}`, { method: "DELETE", headers: hdr() }), "del user");
}
