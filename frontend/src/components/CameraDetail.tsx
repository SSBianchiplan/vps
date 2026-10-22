import { useEffect, useRef, useState, type PointerEvent as RPointerEvent } from "react";
import { useStore, CAPTURE_PRESETS } from "../store/useStore";
import { deletePreset, getImaging, gotoPreset, listPresets, mjpegUrl, ptzMove, ptzStop, savePreset, setCameraLight, setImaging, snapshot, type ImagingSettings, type PtzPreset, type SavedCamera } from "../api/cameras";
import { inferOnce } from "../api/client";
import { getRecordingConfig, listRecordings, manualRecording, recordingFileUrl, setRecordingConfig, type Recording } from "../api/recordings";
import { listEvents, type VisionEvent } from "../api/events";
import { btnCls, btnPrimaryCls, inputCls } from "../lib/ui";
import { MODE_LABELS, type InferenceResult, type Mode, type TaskConfig } from "../types";

// Classes-alvo do auto-gravar (COCO/YOLO → rótulo PT).
const REC_CLASSES: [string, string][] = [
  ["person", "Pessoa"], ["dog", "Cachorro"], ["cat", "Gato"],
  ["car", "Carro"], ["motorcycle", "Moto"], ["bicycle", "Bicicleta"], ["truck", "Caminhão"],
];
const clsLabel = (c: string) => REC_CLASSES.find(([k]) => k === c)?.[1] ?? c;

type Tab = "live" | "rec" | "events" | "run" | "cfg";

const RUN_MODES: Mode[] = ["LER", "CONTAR", "DETECTAR", "DESCREVER", "ANALISAR"];

const SEV_DOT: Record<string, string> = { ok: "bg-ok", nok: "bg-nok", alerta: "bg-warn", info: "bg-accent-2" };

function PtzPad({ cameraId, onMsg, zoom, onZoom, onZoomReset }: {
  cameraId: string;
  onMsg: (m: string) => void;
  zoom: number;
  onZoom: (dir: 1 | -1) => void;
  onZoomReset: () => void;
}) {
  const holdRef = useRef<number | null>(null);
  const [presets, setPresets] = useState<PtzPreset[]>([]);
  const [savingPreset, setSavingPreset] = useState(false);

  const loadPresets = () => listPresets(cameraId).then((r) => setPresets(r.presets || [])).catch(() => undefined);
  useEffect(() => { loadPresets(); /* eslint-disable-next-line */ }, [cameraId]);

  const savePos = async () => {
    const name = window.prompt("Nome da posição (preset):", `Posição ${presets.length + 1}`);
    if (name === null) return;
    setSavingPreset(true);
    try {
      const r = await savePreset(cameraId, name || undefined);
      onMsg(r.ok ? `✓ posição salva: ${r.name}` : (r.message || "presets não suportados"));
      if (r.ok) loadPresets();
    } catch (e) { onMsg(String((e as Error)?.message ?? e)); }
    finally { setSavingPreset(false); }
  };
  const goPreset = async (t: string) => {
    const r = await gotoPreset(cameraId, t).catch((e) => ({ ok: false, message: String(e) }));
    if (!r.ok) onMsg((r as { message?: string }).message || "falha ao mover");
  };
  const delPreset = async (t: string) => { await deletePreset(cameraId, t).catch(() => undefined); loadPresets(); };

  const press = async (v: { pan?: number; tilt?: number }) => {
    try { const r = await ptzMove(cameraId, v); if (!r.ok) onMsg(r.message || "PTZ indisponível"); }
    catch (e) { onMsg(String((e as Error)?.message ?? e)); }
  };
  const release = () => ptzStop(cameraId).catch(() => undefined);
  // Setas = PTZ óptico (segurar move câmeras motorizadas).
  const Arrow = ({ label, v }: { label: string; v: { pan?: number; tilt?: number } }) => (
    <button className="bg-edge border border-edge rounded-card hover:border-accent active:bg-accent/20 text-text flex items-center justify-center"
      onMouseDown={() => press(v)} onMouseUp={release} onMouseLeave={release} onTouchStart={() => press(v)} onTouchEnd={release}>
      {label}
    </button>
  );
  // Zoom = digital no preview (segurar acelera).
  const stopHold = () => { if (holdRef.current) { window.clearInterval(holdRef.current); holdRef.current = null; } };
  const startHold = (dir: 1 | -1) => { onZoom(dir); stopHold(); holdRef.current = window.setInterval(() => onZoom(dir), 150); };
  const zBtn = "flex-1 bg-edge border border-edge rounded-card hover:border-accent active:bg-accent/20 text-text text-lg font-bold py-1 select-none";
  return (
    <div className="space-y-2">
      <div className="grid grid-cols-3 grid-rows-3 gap-1 w-32 h-32 mx-auto">
        <span /><Arrow label="▲" v={{ tilt: 0.6 }} /><span />
        <Arrow label="◀" v={{ pan: -0.6 }} />
        <button className="bg-surface border border-edge rounded-card text-[9px] font-bold text-text hover:border-accent active:bg-accent/20 leading-tight disabled:opacity-50"
          onClick={savePos} disabled={savingPreset} title="Gravar a posição atual da câmera (preset)">💾<br />SALVAR</button>
        <Arrow label="▶" v={{ pan: 0.6 }} />
        <span /><Arrow label="▼" v={{ tilt: -0.6 }} /><span />
      </div>

      {presets.length > 0 && (
        <div>
          <p className="text-[10px] uppercase tracking-wider text-muted mb-1">Posições salvas</p>
          <div className="flex flex-wrap gap-1">
            {presets.map((p) => (
              <span key={p.token} className="flex items-center gap-1 text-[11px] bg-edge border border-edge rounded-full pl-2 pr-1 py-0.5">
                <button className="hover:text-accent text-text" onClick={() => goPreset(p.token)} title="Ir para esta posição">📍 {p.name}</button>
                <button className="text-muted hover:text-nok" onClick={() => delPreset(p.token)} title="Excluir">✕</button>
              </span>
            ))}
          </div>
        </div>
      )}
      <div>
        <div className="flex items-center gap-1">
          <button className={zBtn} onPointerDown={() => startHold(-1)} onPointerUp={stopHold} onPointerLeave={stopHold} disabled={zoom <= 1}>−</button>
          <span className="w-12 text-center text-xs font-mono text-text tabular-nums">{zoom.toFixed(1)}×</span>
          <button className={zBtn} onPointerDown={() => startHold(1)} onPointerUp={stopHold} onPointerLeave={stopHold} disabled={zoom >= 4}>+</button>
          <button className="px-2 py-1 text-xs rounded-card border border-edge bg-edge hover:border-accent text-muted disabled:opacity-40" onClick={onZoomReset} disabled={zoom <= 1} title="Reset zoom">⟲</button>
        </div>
        <p className="text-[10px] text-muted text-center mt-1">Zoom digital no preview</p>
      </div>
    </div>
  );
}

// useToken=false → motor local (sem token); true → IA/Claude (VLM).
function buildTask(mode: Mode, text: string, useToken: boolean): TaskConfig {
  const t = text.trim();
  switch (mode) {
    case "LER":
      return { mode, params: { mode, idioma: "por", pattern_regex: t || null, campos_logicos: [], prefer_vlm: useToken } };
    case "CONTAR":
      return { mode, params: { mode, classes_alvo: t ? t.split(/[, \n]+/).filter(Boolean) : [], conf_threshold: 0.3, counting: "instant", counting_roi: null } };
    case "DETECTAR":
      return { mode, prompt: t || null, params: { mode, classes_alvo: [], conf_threshold: 0.3, max_det: 50, notificar: false, notificar_classes: [] } };
    case "RASTREAR":
      return { mode, params: { mode, classes_alvo: t ? t.split(/[, \n]+/).filter(Boolean) : [], conf_threshold: 0.35, algorithm: "bytetrack", counting_roi: null, dwell_sla_s: null, anonymize_persons: true } };
    case "DESCREVER":
      return { mode, prompt: t || null, params: { mode, foco: t || null, nivel_detalhe: "medio", prefer_edge: !useToken } };
    case "ANALISAR":
      return { mode, params: { mode, criterios: t ? t.split("\n").map((x) => x.trim()).filter(Boolean) : [], rotulo_ok: "OK", rotulo_nok: "NOK", rubrica: null, acao_nok: "nenhuma", crop_roi: false, prefer_edge: !useToken } };
  }
}

// Modos cujo comportamento muda com o token (VLM). CONTAR/DETECTAR são sempre locais (YOLO).
const TOKEN_MODES: Mode[] = ["LER", "DESCREVER", "ANALISAR"];

function ResultView({ r }: { r: InferenceResult }) {
  const res = r.result as any;
  const meta = (
    <div className="flex items-center gap-2 text-[10px] text-muted mb-2">
      <span className={"px-1.5 py-0.5 rounded " + (r.model_type === "edge" ? "bg-accent-2/20 text-accent-2" : "bg-accent/20 text-accent")}>
        {r.model_type === "edge" ? "⚡ local" : "🧠 IA"}
      </span>
      <span>{r.model_name}</span><span>· {r.latency_ms}ms</span>
      {r.confidence > 0 && <span>· conf {(r.confidence * 100).toFixed(0)}%</span>}
    </div>
  );

  let body: JSX.Element;
  if (r.mode === "DESCREVER") {
    body = (
      <div className="space-y-2">
        <p className="text-sm text-text">{res.descricao}</p>
        {res.objetos?.length > 0 && <p className="text-xs text-muted">Objetos: {res.objetos.join(", ")}</p>}
        {res.alertas?.length > 0 && <p className="text-xs text-warn">⚠ {res.alertas.join(" · ")}</p>}
      </div>
    );
  } else if (r.mode === "ANALISAR") {
    const ok = res.veredito === "OK";
    body = (
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <span className={"px-2 py-0.5 rounded font-bold text-sm " + (ok ? "bg-ok/20 text-ok" : "bg-nok/20 text-nok")}>{res.veredito}</span>
          <span className="text-xs text-muted">{res.resumo}</span>
        </div>
        <ul className="space-y-1">
          {res.itens_verificados?.map((it: any, i: number) => (
            <li key={i} className="text-xs flex gap-1.5"><span>{it.atende ? "✅" : "❌"}</span><span className="text-text">{it.criterio}</span><span className="text-muted">— {it.observacao}</span></li>
          ))}
        </ul>
      </div>
    );
  } else if (r.mode === "LER") {
    body = res.leituras?.length ? (
      <div className="space-y-1">{res.leituras.map((l: any, i: number) => (
        <div key={i} className="text-xs flex gap-2"><span className="font-mono text-text">{l.texto}</span>{l.campo && <span className="text-muted">({l.campo})</span>}<span className="ml-auto text-muted">{(l.confianca * 100).toFixed(0)}%</span></div>
      ))}</div>
    ) : <p className="text-xs text-muted">Nenhum texto reconhecido.</p>;
  } else {
    // CONTAR / DETECTAR
    const cont = res.contagens || {};
    const keys = Object.keys(cont);
    body = (
      <div className="space-y-2">
        <p className="text-2xl font-bold text-accent">{res.total ?? 0}<span className="text-xs text-muted font-normal ml-1">objeto(s)</span></p>
        {keys.length > 0 ? (
          <div className="flex flex-wrap gap-1.5">{keys.map((k) => (
            <span key={k} className="text-xs px-2 py-0.5 rounded bg-edge border border-edge">{k}: <b>{cont[k]}</b></span>
          ))}</div>
        ) : <p className="text-xs text-muted">Nada detectado nesta cena.</p>}
      </div>
    );
  }
  return <div className="bg-surface border border-edge rounded-card p-3">{meta}{body}</div>;
}

function ActionRunner({ cam }: { cam: SavedCamera }) {
  const caps = useStore((s) => s.capabilities);
  const [mode, setMode] = useState<Mode>("DETECTAR");
  const [text, setText] = useState("");
  // Nos módulos o token é OPCIONAL e desligado por padrão (token "vive" no Estúdio).
  const [useToken, setUseToken] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<InferenceResult | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const tokenMode = TOKEN_MODES.includes(mode);
  const placeholder: Record<Mode, string> = {
    LER: "regex de validação (opcional, ex.: ^OP[0-9]+)",
    CONTAR: "classes-alvo (opcional, ex.: person, car)",
    DETECTAR: "instrução livre (opcional)",
    RASTREAR: "classes-alvo (opcional, ex.: caixa, palete)",
    DESCREVER: "foco da descrição (opcional)",
    ANALISAR: "critérios, um por linha (ex.: pessoa presente)",
  };

  const run = async () => {
    setErr(null); setLoading(true); setResult(null);
    try {
      const shot = await snapshot({ cameraId: cam.id, maxW: useStore.getState().captureWidth });
      const task = buildTask(mode, text, tokenMode && useToken && !!caps?.vlm);
      const r = await inferOnce(shot.image_b64, task, `cam:${cam.id}`);
      setResult(r);
    } catch (e) {
      setErr(String((e as Error)?.message ?? e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="overflow-y-auto scroll-thin space-y-3 pr-1">
      <p className="text-xs text-muted">
        Roda a ação direto nesta câmera: captura um snapshot e infere uma vez.
        DETECTAR/CONTAR/DESCREVER/ANALISAR funcionam <b>sem token</b> (motor local).
      </p>
      <div className="grid grid-cols-5 gap-1">
        {RUN_MODES.map((m) => (
          <button key={m} onClick={() => { setMode(m); setResult(null); setErr(null); }}
            className={"py-1.5 rounded text-xs font-semibold border transition-colors " +
              (mode === m ? "bg-accent text-onaccent border-accent" : "bg-edge border-edge hover:border-accent text-muted")}>
            {MODE_LABELS[m]}
          </button>
        ))}
      </div>

      <textarea className={inputCls + " h-16 resize-y text-xs"} placeholder={placeholder[mode]}
        value={text} onChange={(e) => setText(e.target.value)} />

      {tokenMode ? (
        <label className="flex items-center gap-2 text-xs text-muted cursor-pointer">
          <input type="checkbox" checked={useToken && !!caps?.vlm} disabled={!caps?.vlm}
            onChange={(e) => setUseToken(e.target.checked)} />
          Usar IA (token Claude){!caps?.vlm ? " — sem token; usando local" : useToken ? "" : " — desligado: motor local"}
        </label>
      ) : (
        <p className="text-[10px] text-muted">Este modo roda sempre local (YOLO) — não usa token.</p>
      )}
      {mode === "LER" && !caps?.edge_ocr && !caps?.vlm && (
        <p className="text-[10px] text-warn">LER exige OCR edge ou token. Instale o pacote OCR (requirements-edge) ou configure a API.</p>
      )}

      <button className={btnPrimaryCls + " w-full"} onClick={run} disabled={loading}>
        {loading ? "Processando…" : `▶ Rodar ${MODE_LABELS[mode]}`}
      </button>

      {err && <p className="text-xs text-nok">⚠ {err}</p>}
      {result && <ResultView r={result} />}
    </div>
  );
}

function CameraSettings({ cam, onMsg }: { cam: SavedCamera; onMsg: (m: string) => void }) {
  const [s, setS] = useState<ImagingSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const load = () => {
    setLoading(true);
    getImaging(cam.id).then(setS).catch((e) => setS({ supported: false, message: String(e?.message ?? e) })).finally(() => setLoading(false));
  };
  useEffect(load, [cam.id]);

  const apply = async (patch: Parameters<typeof setImaging>[1], optimistic?: Partial<ImagingSettings>) => {
    if (optimistic) setS((p) => (p ? { ...p, ...optimistic } : p));
    setBusy(true);
    try {
      const r = await setImaging(cam.id, patch);
      if (!r.ok) onMsg(r.message || "câmera recusou a alteração");
    } catch (e) { onMsg(String((e as Error)?.message ?? e)); }
    finally { setBusy(false); }
  };

  if (loading) return <div className="h-40 flex items-center justify-center text-muted text-sm">Lendo configurações…</div>;
  if (!s?.supported)
    return <div className="overflow-y-auto scroll-thin"><p className="text-sm text-warn">⚠ Esta câmera não expõe configuração de imagem por ONVIF.{s?.message ? ` (${s.message})` : ""}</p>
      <p className="text-xs text-muted mt-2">A visão noturna pode ser automática no firmware (IR). PTZ/snapshot seguem disponíveis.</p></div>;

  const DN = ([["AUTO", "Auto", "alterna por luz"], ["ON", "☀ Dia", "cor (filtro IR on)"], ["OFF", "🌙 Noite", "P&B / IR"]] as const);
  const Slider = ({ label, field, max }: { label: string; field: keyof ImagingSettings; max: number }) => {
    const val = Number(s[field] ?? 0);
    return (
      <div>
        <div className="flex justify-between text-xs text-muted mb-0.5"><span>{label}</span><span className="font-mono text-text">{val.toFixed(0)}</span></div>
        <input type="range" min={0} max={max} step={1} value={val} disabled={busy}
          onChange={(e) => setS((p) => (p ? { ...p, [field]: Number(e.target.value) } : p))}
          onPointerUp={(e) => apply({ [field]: Number((e.target as HTMLInputElement).value) } as any)}
          className="w-full accent-accent" />
      </div>
    );
  };

  return (
    <div className="overflow-y-auto scroll-thin space-y-4 pr-1">
      <div className="grid grid-cols-2 gap-2">
        <button disabled={busy} onClick={() => apply({ ir_cut_filter: "ON" }, { ir_cut_filter: "ON" })}
          className={"py-2 rounded-card border text-sm font-semibold transition-colors " +
            (s.ir_cut_filter === "ON" ? "bg-accent text-onaccent border-accent" : "bg-edge border-edge hover:border-accent text-text")}>
          🎨 Modo cor (IR desligado)
        </button>
        <button disabled={busy} onClick={() => apply({ ir_cut_filter: "OFF" }, { ir_cut_filter: "OFF" })}
          className={"py-2 rounded-card border text-sm font-semibold transition-colors " +
            (s.ir_cut_filter === "OFF" ? "bg-accent text-onaccent border-accent" : "bg-edge border-edge hover:border-accent text-text")}>
          🌙 Noturno (IR)
        </button>
      </div>
      <div>
        <label className="block text-xs font-medium text-muted mb-1">Modo dia/noite (filtro IR-cut)</label>
        <div className="grid grid-cols-3 gap-2">
          {DN.map(([v, label, hint]) => (
            <button key={v} disabled={busy} onClick={() => apply({ ir_cut_filter: v }, { ir_cut_filter: v })}
              className={"py-2 rounded-card border text-xs font-semibold transition-colors " +
                (s.ir_cut_filter === v ? "bg-accent text-onaccent border-accent" : "bg-edge border-edge hover:border-accent text-text")}>
              <span className="block">{label}</span><span className="block text-[9px] font-normal opacity-70">{hint}</span>
            </button>
          ))}
        </div>
      </div>
      <div className="space-y-3">
        <h4 className="text-xs uppercase tracking-wider text-muted">Ajustes de imagem</h4>
        <Slider label="Brilho" field="brightness" max={100} />
        <Slider label="Contraste" field="contrast" max={100} />
        <Slider label="Saturação" field="color_saturation" max={100} />
        <Slider label="Nitidez" field="sharpness" max={100} />
      </div>
      <button className={btnCls} onClick={load} disabled={busy}>↻ Recarregar da câmera</button>
      <p className="text-[10px] text-muted">Alterações são gravadas na câmera (ONVIF SetImagingSettings, persistente).</p>
    </div>
  );
}

export function CameraDetail() {
  const id = useStore((s) => s.detailCameraId);
  const close = () => useStore.getState().setDetailCameraId(null);
  const saved = useStore((s) => s.savedCameras);
  const setSelectedCameraId = useStore((s) => s.setSelectedCameraId);
  const setSourceMode = useStore((s) => s.setSourceMode);
  const setView = useStore((s) => s.setView);
  const setIp = useStore((s) => s.setIp);
  const captureWidth = useStore((s) => s.captureWidth);
  const setCaptureWidth = useStore((s) => s.setCaptureWidth);

  const cam: SavedCamera | undefined = saved.find((c) => c.id === id);

  const [tab, setTab] = useState<Tab>("live");
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [retry, setRetry] = useState(0);
  const [msg, setMsg] = useState("");
  const [events, setEvents] = useState<VisionEvent[]>([]);
  const [recs, setRecs] = useState<Recording[]>([]);
  const [autoRec, setAutoRec] = useState(false);
  const autoBusy = useRef(false);
  // Luz LED (ONVIF) — estado otimista; suporte é best-effort.
  const [lightOn, setLightOn] = useState(false);
  const [lightAuto, setLightAuto] = useState(false);
  const [lightBusy, setLightBusy] = useState(false);
  // Auto-gravar: classes-alvo (config global do backend, persistida).
  const [recClasses, setRecClasses] = useState<string[]>(["person", "dog"]);
  const [recCooldown, setRecCooldown] = useState(8);
  const imgRef = useRef<HTMLImageElement | null>(null);
  const viewRef = useRef<HTMLDivElement | null>(null);

  // Zoom digital (preview): escala 1×–4× + deslocamento por arraste.
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const dragRef = useRef<{ sx: number; sy: number; px: number; py: number } | null>(null);

  const clampPan = (p: { x: number; y: number }, z: number) => {
    const lim = (z - 1) * 50; // % máx. de deslocamento por eixo
    return { x: Math.max(-lim, Math.min(lim, p.x)), y: Math.max(-lim, Math.min(lim, p.y)) };
  };
  const zoomBy = (dir: 1 | -1) =>
    setZoom((z) => {
      const nz = Math.min(4, Math.max(1, +(z * (dir > 0 ? 1.25 : 1 / 1.25)).toFixed(3)));
      setPan((p) => clampPan(p, nz));
      return nz;
    });
  const resetZoom = () => { setZoom(1); setPan({ x: 0, y: 0 }); };

  const onPanDown = (e: RPointerEvent) => {
    if (zoom <= 1) return;
    dragRef.current = { sx: e.clientX, sy: e.clientY, px: pan.x, py: pan.y };
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
  };
  const onPanMove = (e: RPointerEvent) => {
    const d = dragRef.current; const box = viewRef.current;
    if (!d || !box) return;
    const r = box.getBoundingClientRect();
    setPan(clampPan({ x: d.px + ((e.clientX - d.sx) / r.width) * 100, y: d.py + ((e.clientY - d.sy) / r.height) * 100 }, zoom));
  };
  const onPanUp = () => { dragRef.current = null; };

  // Reset do zoom ao trocar de câmera.
  useEffect(() => { resetZoom(); }, [id]);

  useEffect(() => {
    if (!cam || tab !== "events") return;
    listEvents({ sourceId: `cam:${cam.id}`, limit: 100 }).then(setEvents).catch(() => undefined);
  }, [cam, tab]);

  const loadRecs = () => {
    if (!cam) return;
    listRecordings(`cam:${cam.id}`, 60).then(setRecs).catch(() => undefined);
  };
  useEffect(() => { if (cam && tab === "rec") loadRecs(); /* eslint-disable-next-line */ }, [cam, tab]);

  // Auto-gravar: enquanto ligado, roda DETECTAR local (edge) na câmera; o backend
  // salva o snapshot quando classes-alvo (pessoa/cachorro) aparecem.
  useEffect(() => {
    if (!cam || !autoRec) return;
    let alive = true;
    const tick = async () => {
      if (!alive || autoBusy.current) return;
      autoBusy.current = true;
      try {
        const shot = await snapshot({ cameraId: cam.id, maxW: useStore.getState().captureWidth });
        await inferOnce(shot.image_b64, buildTask("DETECTAR", "", false), `cam:${cam.id}`);
        loadRecs();
      } catch { /* silencioso */ }
      finally { autoBusy.current = false; }
    };
    const iv = window.setInterval(tick, 2500);
    tick();
    return () => { alive = false; window.clearInterval(iv); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cam, autoRec]);

  // Lê a config global de auto-gravar (classes/cooldown) ao abrir.
  useEffect(() => {
    getRecordingConfig().then((c) => { setRecClasses(c.classes); setRecCooldown(c.cooldown_s); }).catch(() => undefined);
  }, []);

  if (!cam) return null;

  // Preview MJPEG ao vivo na resolução escolhida (retry força reconexão).
  // Modal = melhor qualidade: main stream em resolução nativa (≤2560), Q85.
  const liveSrc = mjpegUrl(cam.id, false, 2560);

  const grabShot = (): string | null => {
    const img = imgRef.current;
    if (!img || !img.naturalWidth) return null;
    const cv = document.createElement("canvas");
    cv.width = img.naturalWidth; cv.height = img.naturalHeight;
    cv.getContext("2d")?.drawImage(img, 0, 0);
    try { return cv.toDataURL("image/jpeg", 0.9); } catch { return null; }
  };
  const downloadShot = () => {
    const url = grabShot(); if (!url) return;
    const a = document.createElement("a"); a.href = url; a.download = `${cam.name}-${Date.now()}.jpg`; a.click();
  };
  const captureToRecordings = async () => {
    try {
      const shot = await snapshot({ cameraId: cam.id, maxW: useStore.getState().captureWidth });
      await manualRecording(`cam:${cam.id}`, shot.image_b64);
      setMsg("✓ gravado em Gravações");
      loadRecs();
    } catch (e) { setMsg(String((e as Error)?.message ?? e)); }
  };
  const openStudio = () => {
    setSelectedCameraId(cam.id); setIp({ ipUrl: cam.url }); setSourceMode("ip"); setView("estudio"); close();
  };

  // Liga/desliga a luz LED branca (fixa). Otimista + reverte se a câmera recusar.
  const toggleLight = async () => {
    if (!cam) return;
    const next = !lightOn;
    setLightBusy(true); setLightOn(next); if (next) setLightAuto(false);
    try {
      const r = await setCameraLight(cam.id, next, "manual");
      if (!r.ok) { setLightOn(!next); setMsg(r.message || "câmera não aceitou o controle de luz"); }
      else setMsg(next ? "💡 luz acesa" : "luz apagada");
    } catch (e) { setLightOn(!next); setMsg(String((e as Error)?.message ?? e)); }
    finally { setLightBusy(false); }
  };

  // Luz automática: a câmera acende o LED branco sozinha quando detecta movimento.
  const toggleAutoLight = async () => {
    if (!cam) return;
    const next = !lightAuto;
    setLightBusy(true); setLightAuto(next); if (next) setLightOn(false);
    try {
      const r = await setCameraLight(cam.id, next, "auto");
      if (!r.ok) { setLightAuto(!next); setMsg(r.message || "câmera não aceitou luz automática"); }
      else setMsg(next ? "💡 luz automática ligada (acende na detecção)" : "luz automática desligada");
    } catch (e) { setLightAuto(!next); setMsg(String((e as Error)?.message ?? e)); }
    finally { setLightBusy(false); }
  };

  // Liga/desliga o auto-gravar: ao ligar, garante a config global habilitada.
  const toggleAutoRec = async () => {
    const next = !autoRec;
    setAutoRec(next);
    if (next) {
      try { await setRecordingConfig({ enabled: true, classes: recClasses }); } catch { /* segue */ }
    }
  };

  // Marca/desmarca uma classe-alvo do auto-gravar (persiste no backend).
  const toggleRecClass = async (cls: string) => {
    const next = recClasses.includes(cls) ? recClasses.filter((c) => c !== cls) : [...recClasses, cls];
    if (!next.length) return;            // mantém ao menos 1 classe
    setRecClasses(next);
    try { await setRecordingConfig({ classes: next }); } catch { /* ignore */ }
  };

  const fnBtn = "flex flex-col items-center gap-1 p-2 rounded-card border border-edge bg-edge hover:border-accent text-xs text-text transition-colors";

  return (
    <div className="vd-modal-overlay fixed inset-0 z-50 flex items-center justify-center p-3" onClick={close}>
      <div className="vd-modal w-full max-w-5xl max-h-[92vh] flex flex-col overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2 px-4 py-3 border-b border-edge">
          <span className={"w-2 h-2 rounded-full " + (status === "ok" ? "bg-ok" : status === "error" ? "bg-nok" : "bg-warn animate-pulse")} />
          <h2 className="font-bold">{cam.name}</h2>
          <span className="text-xs text-muted font-mono">{cam.ip}:{cam.port}</span>
          <div className="ml-auto flex items-center gap-2">
            <button className={btnCls} onClick={openStudio}>🎛 Abrir no Estúdio</button>
            <button className="text-muted hover:text-text text-lg" onClick={close}>✕</button>
          </div>
        </div>

        <div className="flex gap-1 px-4 pt-3">
          {([["live", "Ao vivo"], ["rec", "Gravações"], ["events", "Eventos"], ["run", "Analisar IA"], ["cfg", "Câmera"]] as [Tab, string][]).map(([k, label]) => (
            <button key={k} onClick={() => setTab(k)}
              className={"px-3 py-1.5 text-sm rounded-t-card border-b-2 transition-colors " +
                (tab === k ? "border-accent text-accent" : "border-transparent text-muted hover:text-text")}>
              {label}
            </button>
          ))}
        </div>

        <div className="flex-1 grid grid-cols-1 lg:grid-cols-[1fr_240px] gap-4 p-4 overflow-hidden">
          <div className="min-h-0 overflow-hidden flex flex-col">
            {tab === "live" && (
              <>
                <div ref={viewRef}
                  className={"flex-1 bg-black rounded-card overflow-hidden flex items-center justify-center relative " + (zoom > 1 ? "cursor-grab active:cursor-grabbing" : "")}
                  onPointerDown={onPanDown} onPointerMove={onPanMove} onPointerUp={onPanUp} onPointerLeave={onPanUp}
                  onDoubleClick={() => (zoom > 1 ? resetZoom() : zoomBy(1))}>
                  <img key={retry} ref={imgRef} src={liveSrc + (retry ? (liveSrc.includes("?") ? `&r=${retry}` : `?r=${retry}`) : "")} alt={cam.name}
                    className="w-full h-full object-contain select-none"
                    style={{ transform: `translate(${pan.x}%, ${pan.y}%) scale(${zoom})`, transition: dragRef.current ? "none" : "transform 0.12s" }}
                    draggable={false}
                    onLoad={() => setStatus("ok")}
                    onError={() => { setStatus("error"); window.setTimeout(() => setRetry((r) => r + 1), 4000); }} />
                  {status === "error" && <span className="absolute text-muted text-sm">⚠ sem sinal — verifique credenciais/RTSP</span>}
                  {status === "ok" && <span className="absolute top-2 left-2 text-[10px] text-emerald-300 font-bold bg-black/50 px-1.5 py-0.5 rounded">● AO VIVO</span>}
                  {zoom > 1 && <span className="absolute top-2 right-2 text-[10px] text-text font-mono bg-black/50 px-1.5 py-0.5 rounded">{zoom.toFixed(1)}× · arraste p/ mover</span>}
                </div>
                <div className="flex items-center gap-2 mt-3 flex-wrap">
                  <button className={btnPrimaryCls} onClick={downloadShot}>📸 Snapshot</button>
                  <button className={btnCls} onClick={captureToRecordings}>⏺ Capturar p/ Gravações</button>
                  <button
                    className={"px-3 py-1.5 rounded text-sm font-medium border transition-colors " +
                      (autoRec ? "border-nok text-nok bg-nok/10" : "border-edge bg-edge hover:border-accent")}
                    onClick={toggleAutoRec}
                    title="Grava automaticamente quando detecta as classes selecionadas">
                    {autoRec ? `● Gravando auto (${recClasses.map(clsLabel).join(", ")})` : "○ Auto-gravar (detecção)"}
                  </button>
                  <label className="ml-auto flex items-center gap-1.5 text-[11px] text-muted shrink-0" title="Resolução do preview e das capturas/análises desta câmera">
                    <span>Resolução</span>
                    <select className="bg-edge border border-edge rounded-card px-2 py-1 text-text"
                      value={captureWidth} onChange={(e) => setCaptureWidth(Number(e.target.value))}>
                      {CAPTURE_PRESETS.map((p) => <option key={p.w} value={p.w}>{p.label}</option>)}
                    </select>
                  </label>
                  {autoRec && (
                    <div className="w-full flex items-center gap-1.5 flex-wrap">
                      <span className="text-[11px] text-muted">Detectar:</span>
                      {REC_CLASSES.map(([k, label]) => {
                        const on = recClasses.includes(k);
                        return (
                          <button key={k} onClick={() => toggleRecClass(k)}
                            className={"text-[11px] px-2 py-0.5 rounded-full border transition-colors " +
                              (on ? "bg-accent text-onaccent border-accent" : "border-edge text-muted hover:text-text")}>
                            {label}
                          </button>
                        );
                      })}
                      <span className="text-[10px] text-muted ml-1">cooldown {recCooldown}s</span>
                    </div>
                  )}
                  {msg && <span className="text-xs text-warn truncate w-full">{msg}</span>}
                </div>
              </>
            )}

            {tab === "rec" && (
              <div className="overflow-y-auto scroll-thin">
                <div className="flex items-center gap-2 mb-3">
                  <p className="text-xs text-muted flex-1">Gravações salvas no servidor (auto por detecção + manuais).</p>
                  <button className={btnCls} onClick={loadRecs}>↻ Atualizar</button>
                </div>
                {recs.length === 0 ? (
                  <div className="h-40 flex items-center justify-center text-muted text-sm border border-dashed border-edge rounded-card text-center px-4">
                    Nenhuma gravação ainda. Ligue <b className="mx-1">Auto-gravar</b> na aba Ao vivo ou use Capturar.
                  </div>
                ) : (
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                    {recs.map((r) => (
                      <div key={r.id} className="border border-edge rounded-card overflow-hidden bg-surface">
                        <img src={recordingFileUrl(r.id)} className="w-full aspect-video object-cover" alt={r.id} loading="lazy" />
                        <div className="px-2 py-1 text-[10px] text-muted flex items-center gap-1">
                          <span className={"w-1.5 h-1.5 rounded-full " + (r.trigger === "auto" ? "bg-nok" : "bg-accent-2")} />
                          <span className="text-text truncate">{Object.entries(r.classes).map(([c, n]) => `${n}× ${c}`).join(", ") || r.mode}</span>
                          <span className="ml-auto shrink-0">{new Date(r.timestamp).toLocaleTimeString()}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {tab === "run" && <ActionRunner cam={cam} />}

            {tab === "cfg" && <CameraSettings cam={cam} onMsg={setMsg} />}

            {tab === "events" && (
              <div className="overflow-y-auto scroll-thin space-y-1.5">
                {events.length === 0 ? (
                  <div className="h-40 flex items-center justify-center text-muted text-sm">Nenhum evento para esta câmera.</div>
                ) : events.map((e) => (
                  <div key={e.detection_id} className="flex items-start gap-2 text-xs py-1.5 border-b border-edge/40">
                    <span className={"w-1.5 h-1.5 rounded-full mt-1 shrink-0 " + (SEV_DOT[e.severidade] ?? "bg-muted")} />
                    <span>{e.icone}</span>
                    <div className="min-w-0 flex-1">
                      <p className="text-text truncate">{e.titulo}</p>
                      <span className="text-muted">{e.mode} · {new Date(e.timestamp).toLocaleString()}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <aside className="overflow-y-auto scroll-thin space-y-4">
            <div>
              <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Controle PTZ</h3>
              <PtzPad cameraId={cam.id} onMsg={setMsg} zoom={zoom} onZoom={zoomBy} onZoomReset={resetZoom} />
              <p className="text-[10px] text-muted mt-1 text-center">Setas = PTZ óptico (segure). 💾 grava a posição atual.</p>
            </div>
            <div>
              <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Funções</h3>
              <div className="grid grid-cols-3 gap-2">
                <button className={fnBtn} onClick={downloadShot}><span className="text-lg">📸</span>Foto</button>
                <button className={fnBtn} onClick={() => setTab("rec")}><span className="text-lg">⏺</span>Gravar</button>
                <button className={fnBtn} onClick={() => setTab("events")}><span className="text-lg">🔔</span>Eventos</button>
                <button className={fnBtn} onClick={() => setTab("cfg")}><span className="text-lg">🌙</span>Noturno</button>
                <button className={fnBtn + (lightOn ? " border-amber-400 text-amber-300" : "")} onClick={toggleLight} disabled={lightBusy}>
                  <span className="text-lg">💡</span>{lightOn ? "Luz ✓" : "Luz"}
                </button>
                <button className={fnBtn + (lightAuto ? " border-amber-400 text-amber-300" : "")} onClick={toggleAutoLight} disabled={lightBusy}
                  title="Câmera acende a luz branca sozinha ao detectar movimento (modo Intelligent)">
                  <span className="text-lg">✨</span>{lightAuto ? "Luz auto ✓" : "Luz auto"}
                </button>
                <button className={fnBtn} onClick={() => setTab("run")}><span className="text-lg">🚨</span>Alarme</button>
                <button className={fnBtn} onClick={() => setTab("run")}><span className="text-lg">🎛</span>Análise</button>
              </div>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}
