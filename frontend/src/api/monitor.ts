import { API_BASE } from "./config";

export type Period = "7d" | "30d" | "90d" | "12m" | "tudo";

export interface Overview {
  period: Period;
  kpis: {
    disponibilidade_media: number | null;
    alertas_detectados: number;
    consumo_total_wh: number | null;
    cameras: number;
    cameras_enabled: number;
    cameras_online: number;
    eventos_total: number;
  };
  availability_series: AvailItem[];
  events_by_day: { day: string; count: number }[];
  events_by_mode: Record<string, number>;
}

export interface AvailItem {
  id: string | null;
  name: string;
  host: string;
  bars: number;
  online: boolean;
  enabled: boolean;
  latency_ms: number | null;
}

export interface CameraSignal {
  name: string;
  host: string;
  port: number;
  online: boolean;
  enabled?: boolean;
  latency_ms: number | null;
  jitter_ms: number;
  packet_loss_pct: number;
  bars: number;
  quality: string;
  buffer_pct: number;
  fps_est: number;
  transport: string;
}

export interface WifiInfo {
  available: boolean;
  ssid?: string | null;
  rssi_dbm?: number;
  noise_dbm?: number;
  snr_db?: number;
  tx_rate_mbps?: number | null;
  bars?: number;
}

export interface LinkSlot {
  tipo: "wifi" | "conector" | "cabeada";
  label: string;
  status: string;
  note?: string;
}

export interface SignalStatus {
  wifi: WifiInfo;
  cameras: CameraSignal[];
  links: LinkSlot[];
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`GET ${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export interface MetricSample {
  time: string;
  source_id: string;
  latency_ms: number | null;
  jitter_ms: number | null;
  packet_loss: number | null;
  buffer_pct: number | null;
  fps: number | null;
  throughput_kbps: number | null;
}

export const getOverview = (period: Period) => get<Overview>(`/monitor/overview?period=${period}`);
export const getSignal = () => get<SignalStatus>(`/monitor/signal`);
export const getSeries = (sourceId?: string, limit = 120) =>
  get<{ samples: MetricSample[] }>(`/monitor/series?limit=${limit}${sourceId ? `&source_id=${encodeURIComponent(sourceId)}` : ""}`);
