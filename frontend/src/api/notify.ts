import { API_BASE } from "./config";

export interface WhatsAppConfig {
  enabled: boolean;
  phone_number_id: string | null;
  recipients: string[];
  graph_version: string;
  template_name: string;
  template_lang: string;
  template_param: boolean;
  has_token: boolean;
  configured: boolean;
}

async function j<T>(r: Response, label: string): Promise<T> {
  if (!r.ok) throw new Error(`${label} -> ${r.status}`);
  return r.json() as Promise<T>;
}

export async function getWhatsApp() {
  return j<WhatsAppConfig>(await fetch(`${API_BASE}/notify/whatsapp/config`), "wa config");
}

export async function putWhatsApp(body: {
  token?: string; phone_number_id?: string; recipients?: string[]; enabled?: boolean;
  graph_version?: string; template_name?: string; template_lang?: string; template_param?: boolean;
}) {
  return j<WhatsAppConfig>(await fetch(`${API_BASE}/notify/whatsapp/config`, {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  }), "wa save");
}

export async function testWhatsApp(message: string, opts?: { to?: string[]; use_template?: boolean; template_name?: string }) {
  return j<{ ok: boolean; error?: string; skipped?: boolean; results?: unknown }>(
    await fetch(`${API_BASE}/notify/whatsapp/test`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, ...opts }),
    }), "wa test");
}
