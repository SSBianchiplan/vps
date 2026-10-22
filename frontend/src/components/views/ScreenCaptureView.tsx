import { useEffect, useRef, useState } from "react";
import { useStore, CAPTURE_PRESETS } from "../../store/useStore";
import { ResultsPanel } from "../ResultsPanel";
import { ModeSelector } from "../ModeSelector";
import { getBridge, setAutoCapture, type BridgeStatus } from "../../api/vps";
import { btnCls, btnPrimaryCls, inputCls, labelCls } from "../../lib/ui";

interface Props {
  active: boolean;
  isScreen: boolean;
  error: string | null;
  onScreenCapture: () => void;   // abre/troca o compartilhamento de tela
  onStopCapture: () => void;     // encerra a captura de tela
  onRun: () => void;             // inicia a inferência (stream)
  onPause: () => void;           // pausa a inferência
  onSnapshot: () => void;
}

// Gênese pela visão: LER um nº de OP/QR na tela abre/avança um Fio Dourado (VPS).
function VpsChip() {
  const setView = useStore((s) => s.setView);
  const [bridge, setBridge] = useState<BridgeStatus | null>(null);
  useEffect(() => {
    const tick = () => getBridge().then(setBridge).catch(() => undefined);
    tick(); const id = window.setInterval(tick, 4000); return () => window.clearInterval(id);
  }, []);
  const tag = bridge?.bindings?.["screen"];
  const auto = bridge?.auto_capture ?? false;
  return (
    <span className="ml-auto flex items-center gap-2 text-xs">
      <button onClick={async () => setBridge(await setAutoCapture(!auto))}
        title="Gênese automática: LER um nº de OP/QR na tela abre um Fio Dourado"
        className={"px-2 py-1 rounded-card border transition-colors " + (auto ? "border-ok/50 text-ok bg-ok/10" : "border-edge text-muted")}>
        🧵 VPS {auto ? "ON" : "OFF"}
      </button>
      {tag && (
        <button onClick={() => setView("vps")} className="px-2 py-1 rounded-card border border-accent/50 text-accent bg-accent/10 hover:bg-accent/20" title={tag}>
          Fio: {tag.split(":").slice(2, 4).join(" ")} →
        </button>
      )}
    </span>
  );
}

// Preview espelha o stream compartilhado (sem reabrir/colidir com o videoRef do Estúdio).
function ScreenPreview({ capturing }: { capturing: boolean }) {
  const ref = useRef<HTMLVideoElement | null>(null);
  const stream = useStore((s) => s.activeStream);
  useEffect(() => {
    const v = ref.current; if (!v) return;
    if (capturing && stream) { v.srcObject = stream; v.play().catch(() => undefined); }
    else v.srcObject = null;
    return () => { if (v) v.srcObject = null; };
  }, [capturing, stream]);
  return (
    <div className="flex-1 bg-black rounded-card overflow-hidden flex items-center justify-center relative min-h-0">
      <video ref={ref} className={"w-full h-full object-contain " + (capturing ? "" : "hidden")} playsInline muted />
      {!capturing && <span className="text-muted text-sm px-4 text-center">Compartilhe uma tela/janela para iniciar a leitura por IA</span>}
      {capturing && <span className="absolute top-2 left-2 text-[10px] text-emerald-300 font-bold bg-black/50 px-1.5 py-0.5 rounded">● AO VIVO · tela</span>}
    </div>
  );
}

export function ScreenCaptureView(props: Props) {
  const mode = useStore((s) => s.mode);
  const running = useStore((s) => s.running);
  const prompt = useStore((s) => s.prompt);
  const setPrompt = useStore((s) => s.setPrompt);
  const captureWidth = useStore((s) => s.captureWidth);
  const setCaptureWidth = useStore((s) => s.setCaptureWidth);
  const screenFps = useStore((s) => s.screenFps);
  const setScreenFps = useStore((s) => s.setScreenFps);
  const changeDetect = useStore((s) => s.screenChangeDetect);
  const setChangeDetect = useStore((s) => s.setScreenChangeDetect);

  const capturing = props.active && props.isScreen;
  const [target, setTarget] = useState("");
  useEffect(() => {
    const ms = useStore.getState().activeStream;
    setTarget(capturing ? (ms?.getVideoTracks()[0]?.label || "tela compartilhada") : "");
  }, [capturing]);

  const showPrompt = mode === "DESCREVER" || mode === "ANALISAR" || mode === "DETECTAR";

  return (
    <div className="flex flex-col gap-3 min-h-full lg:h-full lg:min-h-0">
      <div className="flex items-center gap-2 flex-wrap shrink-0">
        <h2 className="text-lg font-bold">🖥 Captura de Tela</h2>
        <span className="text-xs text-muted">a tela como câmera — LER/CONTAR/DETECTAR/DESCREVER/ANALISAR sobre a interface</span>
        <VpsChip />
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-[330px_1fr_370px] gap-4 min-h-0">
        {/* Controles */}
        <aside className="bg-panel rounded-card border border-edge p-4 overflow-y-auto scroll-thin space-y-4">
          <section className="border-b border-edge pb-4">
            <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Captura de tela</h3>
            <div className="flex items-center gap-2 px-3 py-2 rounded-card border border-accent/40 bg-accent/10 mb-2">
              <span className={"w-2 h-2 rounded-full " + (capturing ? "bg-ok animate-pulse" : "bg-muted")} />
              <span className="text-sm text-text flex-1 truncate" title={target}>
                {capturing ? (target || "capturando") : "tela não compartilhada"}
              </span>
            </div>
            <div className="flex gap-2">
              <button className={btnPrimaryCls} onClick={props.onScreenCapture}>
                {capturing ? "🖥 Trocar tela/janela" : "🖥 Compartilhar tela"}
              </button>
              {capturing && <button className={btnCls} onClick={props.onStopCapture}>Parar</button>}
            </div>
            {props.error && <p className="text-xs text-nok mt-2">{props.error}</p>}
            <p className="text-[11px] text-muted mt-2">
              Escolha display, janela ou aba ao compartilhar. Ideal p/ ler ERP/MES/SCADA/HMI sem API.
            </p>
          </section>

          <section className="border-b border-edge pb-4">
            <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Modo de IA</h3>
            <ModeSelector />
          </section>

          {showPrompt && (
            <section className="border-b border-edge pb-4">
              <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Instrução (VLM)</h3>
              <textarea className={inputCls + " h-16 resize-y"} placeholder="ex.: extraia nº da OP e status"
                value={prompt} onChange={(e) => setPrompt(e.target.value)} />
            </section>
          )}

          <section className="border-b border-edge pb-4">
            <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Amostragem (controle de custo)</h3>
            <label className={labelCls}>Taxa: {screenFps} fps</label>
            <input type="range" min={1} max={8} step={1} value={screenFps}
              onChange={(e) => setScreenFps(Number(e.target.value))} className="w-full accent-accent" />
            <label className="flex items-center gap-2 mt-2 text-sm text-text cursor-pointer">
              <input type="checkbox" checked={changeDetect} onChange={(e) => setChangeDetect(e.target.checked)} />
              Detecção de mudança (só processa quando a tela muda)
            </label>
            <label className={labelCls + " mt-3"}>Resolução de captura</label>
            <select className={inputCls} value={captureWidth} onChange={(e) => setCaptureWidth(Number(e.target.value))}>
              {CAPTURE_PRESETS.map((p) => <option key={p.w} value={p.w}>{p.label}</option>)}
            </select>
            <p className="text-[11px] text-muted mt-1">Telas mudam devagar → fps baixo + detecção de mudança minimizam chamadas ao VLM.</p>
          </section>

          <section>
            <h3 className="text-xs uppercase tracking-wider text-muted mb-2">🔒 Privacidade</h3>
            <p className="text-[11px] text-muted">
              Compartilhe só a <b>janela/região</b> necessária — nunca a tela toda por padrão. Não compartilhe
              telas de <b>login/senha</b>. Eventos saem com fonte <b>screen</b> (auditados · LGPD).
            </p>
          </section>
        </aside>

        {/* Preview ao vivo da tela + controles de inferência */}
        <section className="bg-panel rounded-card border border-edge p-4 overflow-hidden min-h-[55vh] lg:min-h-0 flex flex-col">
          <ScreenPreview capturing={capturing} />
          <div className="flex items-center gap-2 mt-3 flex-wrap shrink-0">
            {!running ? (
              <button className={btnPrimaryCls} onClick={props.onRun} disabled={!capturing} title={capturing ? "" : "compartilhe a tela primeiro"}>
                ▶ Iniciar leitura
              </button>
            ) : (
              <button className={btnCls} onClick={props.onPause}>⏸ Pausar</button>
            )}
            <button className={btnCls} onClick={props.onSnapshot} disabled={!capturing}>📸 Ler agora</button>
            <span className="text-[11px] text-muted ml-auto">{running ? `lendo a ${screenFps} fps` : "parado"}</span>
          </div>
        </section>

        {/* Resultado + log de eventos (extração estruturada) */}
        <aside className="bg-panel rounded-card border border-edge p-4 overflow-hidden min-h-[40vh] lg:min-h-0">
          <ResultsPanel />
        </aside>
      </div>
    </div>
  );
}
