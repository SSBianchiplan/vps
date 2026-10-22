import { create } from "zustand";
import type { SavedCamera } from "../api/cameras";
import type {
  AnalyzeParams,
  Capabilities,
  CountParams,
  DescribeParams,
  DetectParams,
  HealthMessage,
  InferenceResult,
  Mode,
  ModeParams,
  ReadParams,
  TrackParams,
  ROI,
  ROIShape,
  TaskConfig,
} from "../types";

const defaultRead = (): ReadParams => ({
  mode: "LER",
  idioma: "por",
  pattern_regex: null,
  campos_logicos: [],
  prefer_vlm: false,
});
const defaultCount = (): CountParams => ({
  mode: "CONTAR",
  classes_alvo: [],
  conf_threshold: 0.35,
  counting: "instant",
  counting_roi: null,
});
const defaultDetect = (): DetectParams => ({
  mode: "DETECTAR",
  classes_alvo: [],
  conf_threshold: 0.35,
  max_det: 50,
  notificar: false,
  notificar_classes: [],
});
const defaultTrack = (): TrackParams => ({
  mode: "RASTREAR",
  classes_alvo: [],
  conf_threshold: 0.35,
  algorithm: "bytetrack",
  counting_roi: null,
  dwell_sla_s: null,
  anonymize_persons: true,
});
const defaultDescribe = (): DescribeParams => ({
  mode: "DESCREVER",
  foco: null,
  nivel_detalhe: "medio",
  prefer_edge: false,
});
const defaultAnalyze = (): AnalyzeParams => ({
  mode: "ANALISAR",
  criterios: [],
  rotulo_ok: "OK",
  rotulo_nok: "NOK",
  rubrica: null,
  acao_nok: "nenhuma",
  crop_roi: true,
  prefer_edge: false,
});

export interface DrawState {
  shape: ROIShape;
  target: "roi" | "counting";
}

// Câmera de dispositivo local (getUserMedia) — aparece como card no Painel/Câmeras.
export interface LocalCam {
  id: string;        // dev:<deviceId>
  name: string;
  deviceId: string;
  platform: string;  // macbook | usb | obs | …
}

interface ParamsMap {
  LER: ReadParams;
  CONTAR: CountParams;
  DETECTAR: DetectParams;
  RASTREAR: TrackParams;
  DESCREVER: DescribeParams;
  ANALISAR: AnalyzeParams;
}

export type View = "painel" | "monitor" | "estudio" | "cameras" | "captura" | "automacao" | "aerea" | "osmo" | "downloads" | "vps" | "planejamento" | "aps" | "matriz" | "operadores" | "face" | "termografia" | "metrologia" | "acesso" | "e2e" | "modais" | "eventos" | "acoes" | "industria" | "estudocaso" | "iamac" | "bases" | "manual" | "seguranca";

export interface AuthUser { operator_id: string; name: string; role: "admin" | "operador" | "view"; method?: string }

export interface Toast {
  id: number;
  action_type: string;
  message: string;
  rule: string;
}

// Presets de resolução de captura (largura-alvo; 0 = nativa, sem reduzir).
export const CAPTURE_PRESETS: { w: number; label: string }[] = [
  { w: 640, label: "640 · rápido" },
  { w: 960, label: "960 · equilibrado" },
  { w: 1280, label: "1280 · HD (padrão)" },
  { w: 1920, label: "1920 · Full HD" },
  { w: 0, label: "Nativa · máx. qualidade" },
];

function initialCaptureWidth(): number {
  try {
    const raw = localStorage.getItem("vd-capture-width");
    if (raw !== null) {
      const v = Number(raw);
      if (v === 0 || (v >= 320 && v <= 4096)) return v;
    }
  } catch { /* ignore */ }
  return 1280;
}

interface State {
  // navegação
  view: View;

  // alertas AGIR (toasts)
  toasts: Toast[];

  // configuração
  mode: Mode;
  params: ParamsMap;
  prompt: string;
  roi: ROI | null;
  sourceId: string;

  // fonte de captura: dispositivo local (getUserMedia) ou câmera IP (RTSP/HTTP)
  sourceMode: "device" | "ip";
  ipUrl: string;
  ipUser: string;
  ipPass: string;
  scanOpen: boolean;

  // Captura de tela (spec §6): amostragem por fps + detecção de mudança (controle de custo VLM)
  screenFps: number;
  screenChangeDetect: boolean;
  aparenciaOpen: boolean;
  detailCameraId: string | null;
  savedCameras: SavedCamera[];
  selectedCameraId: string | null;

  // câmeras de dispositivo local (sessão) + stream ativo compartilhado
  localCameras: LocalCam[];
  activeStream: MediaStream | null;
  activeDeviceId: string | null;

  // resolução de captura (largura-alvo; 0 = nativa). Aplica a device, IP e preview.
  captureWidth: number;

  // desenho
  draw: DrawState | null;

  // runtime
  capabilities: Capabilities | null;
  connected: boolean;
  running: boolean;
  statusDetail: string;
  health: HealthMessage | null;
  lastResult: InferenceResult | null;
  log: InferenceResult[];
  error: string | null;

  // actions
  setView: (v: View) => void;
  pushToast: (t: Omit<Toast, "id">) => void;
  dismissToast: (id: number) => void;
  setMode: (m: Mode) => void;
  setParams: <K extends Mode>(mode: K, partial: Partial<ParamsMap[K]>) => void;
  setPrompt: (p: string) => void;
  setRoi: (roi: ROI | null) => void;
  setCountingRoi: (roi: ROI | null) => void;
  setDraw: (d: DrawState | null) => void;
  auth: AuthUser | null;
  setAuth: (u: AuthUser | null) => void;
  setSourceId: (s: string) => void;
  setSourceMode: (m: "device" | "ip") => void;
  setScreenFps: (n: number) => void;
  setScreenChangeDetect: (v: boolean) => void;
  setIp: (partial: { ipUrl?: string; ipUser?: string; ipPass?: string }) => void;
  setScanOpen: (b: boolean) => void;
  setAparenciaOpen: (b: boolean) => void;
  setDetailCameraId: (id: string | null) => void;
  setSavedCameras: (c: SavedCamera[]) => void;
  setSelectedCameraId: (id: string | null) => void;
  addLocalCamera: (c: LocalCam) => void;
  removeLocalCamera: (id: string) => void;
  setActiveStream: (s: MediaStream | null, deviceId: string | null) => void;
  setCaptureWidth: (w: number) => void;

  setCapabilities: (c: Capabilities) => void;
  setConnected: (b: boolean) => void;
  setRunning: (b: boolean) => void;
  setStatusDetail: (s: string) => void;
  setHealth: (h: HealthMessage) => void;
  pushResult: (r: InferenceResult) => void;
  setError: (e: string | null) => void;
  clearLog: () => void;

  currentParams: () => ModeParams;
  buildTask: () => TaskConfig;
}

export const useStore = create<State>((set, get) => ({
  view: "painel",
  toasts: [],

  mode: "DESCREVER",
  params: {
    LER: defaultRead(),
    CONTAR: defaultCount(),
    DETECTAR: defaultDetect(),
    RASTREAR: defaultTrack(),
    DESCREVER: defaultDescribe(),
    ANALISAR: defaultAnalyze(),
  },
  prompt: "",
  roi: null,
  sourceId: "macbook",

  sourceMode: "device",
  screenFps: 2,
  screenChangeDetect: true,
  ipUrl: "",
  ipUser: "",
  ipPass: "",
  scanOpen: false,
  aparenciaOpen: false,
  detailCameraId: null,
  savedCameras: [],
  selectedCameraId: null,
  localCameras: [],
  activeStream: null,
  activeDeviceId: null,
  captureWidth: initialCaptureWidth(),

  draw: null,

  capabilities: null,
  connected: false,
  running: false,
  statusDetail: "",
  health: null,
  lastResult: null,
  log: [],
  error: null,

  setView: (v) => set({ view: v }),
  pushToast: (t) => set((s) => ({ toasts: [...s.toasts, { ...t, id: (s.toasts.length ? s.toasts[s.toasts.length - 1].id : 0) + 1 }].slice(-5) })),
  dismissToast: (id) => set((s) => ({ toasts: s.toasts.filter((x) => x.id !== id) })),
  setMode: (m) => set({ mode: m }),
  setParams: (mode, partial) =>
    set((s) => ({
      params: { ...s.params, [mode]: { ...s.params[mode], ...partial } },
    })),
  setPrompt: (p) => set({ prompt: p }),
  setRoi: (roi) => set({ roi }),
  setCountingRoi: (roi) =>
    set((s) => {
      const m = s.mode === "RASTREAR" ? "RASTREAR" : "CONTAR";  // linha/zona vale p/ ambos
      return { params: { ...s.params, [m]: { ...s.params[m], counting_roi: roi } } };
    }),
  setDraw: (d) => set({ draw: d }),
  auth: null,
  setAuth: (u) => {
    // espelha o papel legado p/ o header X-VPS-Role (compat com a RBAC do VPS)
    try {
      const legacy = u ? (u.role === "admin" ? "Admin" : u.role === "view" ? "Viewer" : "Operador") : "Admin";
      localStorage.setItem("vps-role", legacy);
    } catch { /* ignore */ }
    set({ auth: u });
  },
  setSourceId: (sid) => set({ sourceId: sid }),
  setSourceMode: (m) => set({ sourceMode: m }),
  setScreenFps: (n) => set({ screenFps: n }),
  setScreenChangeDetect: (v) => set({ screenChangeDetect: v }),
  setIp: (partial) => set((s) => ({ ...s, ...partial })),
  setScanOpen: (b) => set({ scanOpen: b }),
  setAparenciaOpen: (b) => set({ aparenciaOpen: b }),
  setDetailCameraId: (id) => set({ detailCameraId: id }),
  setSavedCameras: (c) => set({ savedCameras: c }),
  setSelectedCameraId: (id) => set({ selectedCameraId: id }),
  addLocalCamera: (c) => set((s) => s.localCameras.some((x) => x.id === c.id)
    ? { localCameras: s.localCameras.map((x) => (x.id === c.id ? c : x)) }
    : { localCameras: [...s.localCameras, c] }),
  removeLocalCamera: (id) => set((s) => ({ localCameras: s.localCameras.filter((x) => x.id !== id) })),
  setActiveStream: (s2, deviceId) => set({ activeStream: s2, activeDeviceId: deviceId }),
  setCaptureWidth: (w) => {
    try { localStorage.setItem("vd-capture-width", String(w)); } catch { /* ignore */ }
    set({ captureWidth: w });
  },

  setCapabilities: (c) => set({ capabilities: c }),
  setConnected: (b) => set({ connected: b }),
  setRunning: (b) => set({ running: b }),
  setStatusDetail: (s) => set({ statusDetail: s }),
  setHealth: (h) => set({ health: h }),
  pushResult: (r) =>
    set((s) => ({ lastResult: r, log: [r, ...s.log].slice(0, 200), error: null })),
  setError: (e) => set({ error: e }),
  clearLog: () => set({ log: [], lastResult: null }),

  currentParams: () => get().params[get().mode],
  buildTask: () => {
    const s = get();
    return {
      mode: s.mode,
      prompt: s.prompt || null,
      params: s.params[s.mode],
      roi: s.roi,
    };
  },
}));
