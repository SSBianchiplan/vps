// Espelha os contratos do backend (schemas Pydantic).

export type Mode = "LER" | "CONTAR" | "DETECTAR" | "RASTREAR" | "DESCREVER" | "ANALISAR";
export type ROIShape = "rect" | "line" | "zone";
export type Point = [number, number];

export interface ROI {
  shape: ROIShape;
  points: Point[];
}

export interface ReadParams {
  mode: "LER";
  idioma: string;
  pattern_regex: string | null;
  campos_logicos: string[];
  prefer_vlm: boolean;
}

export interface CountParams {
  mode: "CONTAR";
  classes_alvo: string[];
  conf_threshold: number;
  counting: "instant" | "accumulated";
  counting_roi: ROI | null;
}

export interface DetectParams {
  mode: "DETECTAR";
  classes_alvo: string[];
  conf_threshold: number;
  max_det: number;
  notificar: boolean;
  notificar_classes: string[];
}

export interface TrackParams {
  mode: "RASTREAR";
  classes_alvo: string[];
  conf_threshold: number;
  algorithm: "bytetrack" | "botsort";
  counting_roi: ROI | null;          // linha (sentido) ou zona (dwell)
  dwell_sla_s: number | null;        // alerta DWELL_EXCEEDED
  anonymize_persons: boolean;        // LGPD
}

export interface DescribeParams {
  mode: "DESCREVER";
  foco: string | null;
  nivel_detalhe: "baixo" | "medio" | "alto";
  prefer_edge: boolean;
}

export interface AnalyzeParams {
  mode: "ANALISAR";
  criterios: string[];
  rotulo_ok: string;
  rotulo_nok: string;
  rubrica: string | null;
  acao_nok: "nenhuma" | "alerta" | "mqtt";
  crop_roi: boolean;
  prefer_edge: boolean;
}

export type ModeParams = ReadParams | CountParams | DetectParams | TrackParams | DescribeParams | AnalyzeParams;

export interface TaskConfig {
  task_id?: string | null;
  mode: Mode;
  prompt?: string | null;
  params: ModeParams;
  roi?: ROI | null;
}

// ── Resultados ──────────────────────────────────────────────────────
export type BBox = number[]; // [x,y,w,h] normalizado

export interface Detection {
  classe: string;
  confianca: number;
  bbox: BBox;
  track_id: number | null;
}

export interface InferenceResult {
  detection_id: string;
  task_id: string | null;
  source_id: string | null;
  mode: Mode;
  model_name: string;
  model_type: "edge" | "vlm";
  pipeline: string;
  timestamp: string;
  latency_ms: number;
  confidence: number;
  frame_seq: number | null;
  result: Record<string, any>;
  warnings: string[];
}

// ── Mensagens WS (servidor → cliente) ───────────────────────────────
export interface ResultMessage {
  type: "result";
  result: InferenceResult;
}
export interface ErrorMessage {
  type: "error";
  code: string;
  message: string;
  frame_seq: number | null;
}
export interface HealthMessage {
  type: "health";
  fps: number;
  avg_latency_ms: number;
  last_latency_ms: number;
  model_active: string;
  pipeline: string;
  edge_available: boolean;
  vlm_available: boolean;
}
export interface StatusMessage {
  type: "status";
  state: "connected" | "running" | "stopped";
  detail: string;
}
export interface AlertMessage {
  type: "alert";
  action_type: string;
  message: string;
  rule: string;
  payload: unknown;
}
export type ServerMessage =
  | ResultMessage | ErrorMessage | HealthMessage | StatusMessage | AlertMessage;

export interface Capabilities {
  edge_detector: boolean;
  edge_ocr: boolean;
  vlm: boolean;
  claude_model: string;
  persist_frames: boolean;
  modes: Mode[];
}

export const MODE_LABELS: Record<Mode, string> = {
  LER: "Ler",
  CONTAR: "Contar",
  DETECTAR: "Detectar",
  RASTREAR: "Rastrear",
  DESCREVER: "Descrever",
  ANALISAR: "Analisar",
};
