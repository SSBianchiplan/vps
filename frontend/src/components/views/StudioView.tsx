import { useEffect, useState, type RefObject } from "react";
import type { CameraDevice } from "../../hooks/useCamera";
import { ConfigPanel } from "../ConfigPanel";
import { PreviewPanel } from "../PreviewPanel";
import { ResultsPanel } from "../ResultsPanel";
import { TechSelector, TechResultView, useTechRunner } from "../StudioTechLab";
import { useStore } from "../../store/useStore";
import { getBridge, setAutoCapture, type BridgeStatus } from "../../api/vps";

// Chip ao vivo: gênese pela visão (LER→Tag-ID) liga a fonte atual a um Fio Dourado.
function VpsStudioChip() {
  const setView = useStore((s) => s.setView);
  const sourceMode = useStore((s) => s.sourceMode);
  const selectedCameraId = useStore((s) => s.selectedCameraId);
  const sourceId = useStore((s) => s.sourceId);
  const [bridge, setBridge] = useState<BridgeStatus | null>(null);
  useEffect(() => {
    const tick = () => getBridge().then(setBridge).catch(() => undefined);
    tick(); const id = window.setInterval(tick, 4000); return () => window.clearInterval(id);
  }, []);
  const src = sourceMode === "device" ? sourceId : selectedCameraId ? `cam:${selectedCameraId}` : "ip_camera";
  const tag = bridge?.bindings?.[src];
  const auto = bridge?.auto_capture ?? false;
  const toggle = async () => setBridge(await setAutoCapture(!auto));
  return (
    <span className="ml-auto flex items-center gap-2 text-xs">
      <button onClick={toggle} title="Gênese automática: LER um nº de OP/QR abre um Fio Dourado"
        className={"px-2 py-1 rounded-card border transition-colors " + (auto ? "border-ok/50 text-ok bg-ok/10" : "border-edge text-muted")}>
        🧵 VPS {auto ? "ON" : "OFF"}
      </button>
      {tag ? (
        <button onClick={() => setView("vps")} className="px-2 py-1 rounded-card border border-accent/50 text-accent bg-accent/10 hover:bg-accent/20" title={tag}>
          Fio: {tag.split(":").slice(2, 4).join(" ")} →
        </button>
      ) : (
        <span className="text-muted">{auto ? "aguardando LER do Tag-ID…" : "captura desligada"}</span>
      )}
    </span>
  );
}

interface Props {
  devices: CameraDevice[];
  deviceId: string | null;
  active: boolean;
  error: string | null;
  videoRef: RefObject<HTMLVideoElement>;
  imgRef: RefObject<HTMLImageElement>;
  onCameraStart: (id?: string | null) => void;
  onCameraStop: () => void;
  onSelectDevice: (id: string) => void;
  onScreenCapture: () => void;
  onRun: () => void;
  onPause: () => void;
  onSnapshot: () => void;
  captureCurrent: () => Promise<string | null>;
}

export function StudioView(props: Props) {
  const [tab, setTab] = useState<"modos" | "tecnologias">("modos");
  const runner = useTechRunner(props.captureCurrent);

  return (
    <div className="flex flex-col gap-3 min-h-full lg:h-full lg:min-h-0">
      {/* Alternância Modos (5) ↔ Tecnologias (8) */}
      <div className="flex items-center gap-2 flex-wrap shrink-0">
        <div className="flex rounded-card border border-edge overflow-hidden">
          {([["modos", "🎛 Modos"], ["tecnologias", "🏭 Tecnologias"]] as const).map(([k, label]) => (
            <button key={k} onClick={() => setTab(k)}
              className={"px-3 py-1.5 text-sm font-semibold transition-colors " +
                (tab === k ? "bg-accent text-onaccent" : "bg-edge text-muted hover:text-text")}>
              {label}
            </button>
          ))}
        </div>
        <span className="text-xs text-muted">
          {tab === "modos" ? "Ler · Contar · Detectar · Descrever · Analisar (stream contínuo)" : "8 modelos industriais testados na fonte ao vivo (one-shot)"}
        </span>
        <VpsStudioChip />
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-[330px_1fr_370px] gap-4 min-h-0">
        <aside className="bg-panel rounded-card border border-edge p-4 overflow-y-auto scroll-thin">
          {tab === "modos" ? (
            <ConfigPanel
              devices={props.devices} deviceId={props.deviceId} active={props.active} error={props.error}
              onStart={props.onCameraStart} onStop={props.onCameraStop} onSelectDevice={props.onSelectDevice}
              onScreenCapture={props.onScreenCapture}
            />
          ) : (
            <TechSelector r={runner} />
          )}
        </aside>

        <section className="bg-panel rounded-card border border-edge p-4 overflow-hidden min-h-[55vh] lg:min-h-0">
          <PreviewPanel
            videoRef={props.videoRef} imgRef={props.imgRef} cameraActive={props.active}
            onStart={props.onRun} onStop={props.onPause} onSnapshot={props.onSnapshot}
          />
        </section>

        <aside className="bg-panel rounded-card border border-edge p-4 overflow-hidden min-h-[40vh] lg:min-h-0">
          {tab === "modos" ? <ResultsPanel /> : <TechResultView r={runner} />}
        </aside>
      </div>
    </div>
  );
}
