import { API_BASE } from "./config";

export interface ClassifyResult {
  supported: boolean;
  backbone?: string;
  model?: string;
  results?: { label: string; conf: number }[];
  latency_ms?: number;
  message?: string;
}

export async function classifyImage(imageB64: string, model: "cnn" | "vit", topk = 5): Promise<ClassifyResult> {
  const res = await fetch(`${API_BASE}/classify`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ image_b64: imageB64, model, topk }),
  });
  if (!res.ok) throw new Error(`classify -> ${res.status}`);
  return res.json() as Promise<ClassifyResult>;
}
