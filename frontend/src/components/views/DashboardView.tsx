import { useEffect, useRef, useState } from "react";
import { useStore } from "../../store/useStore";
import { getStreamStats, listSavedCameras, type SavedCamera } from "../../api/cameras";
import { listEvents, type VisionEvent } from "../../api/events";
import { getAerialStatus } from "../../api/aerial";
import { CameraCard } from "../CameraCard";
import { LocalCameraCard } from "../LocalCameraCard";
import { MeshCameraCard } from "../MeshCameraCard";
import { AerialCameraCard } from "../AerialCameraCard";
import { SignalChart } from "../SignalChart";
import { DevicesView } from "./DevicesView";
import type { LocalCamCtl } from "../OnlineBar";
import type { DeviceMesh } from "../../hooks/useDeviceMesh";
import { btnCls, btnPrimaryCls } from "../../lib/ui";

const N = 48;

// Fontes aéreas do sistema (MediaMTX) que descem à grade quando online.
const AERIAL: { path: string; name: string; icon: string; view: "aerea" | "osmo" }[] = [
  { path: "drone_neo2", name: "Drone (Visão Aérea)", icon: "🛸", view: "aerea" },
  { path: "osmo_pocket", name: "Vídeo Osmo", icon: "📷", view: "osmo" },
];

type Layout = 1 | 4 | 9;
const COLS: Record<Layout, string> = {
  1: "grid-cols-1",
  4: "grid-cols-1 sm:grid-cols-2",
  9: "grid-cols-2 lg:grid-cols-3",
};

const SEV_DOT: Record<string, string> = {
  ok: "bg-ok",
  nok: "bg-nok",
  alerta: "bg-warn",
  info: "bg-accent-2",
};

export function DashboardView({ mesh, camera }: { mesh: DeviceMesh; camera: LocalCamCtl }) {
  const saved = useStore((s) => s.savedCameras);
  const setSaved = useStore((s) => s.setSavedCameras);
  const localCams = useStore((s) => s.localCameras);
  const removeLocalCamera = useStore((s) => s.removeLocalCamera);
  const setView = useStore((s) => s.setView);
  const setScanOpen = useStore((s) => s.setScanOpen);
  const setDetailCameraId = useStore((s) => s.setDetailCameraId);

  // Home abre travada na grade 9 (preferência persistida).
  const [layout, setLayoutState] = useState<Layout>(() => {
    try { const v = Number(localStorage.getItem("vd-home-layout")); return (v === 1 || v === 4 || v === 9) ? (v as Layout) : 9; }
    catch { return 9; }
  });
  const setLayout = (l: Layout) => {
    setLayoutState(l);
    try { localStorage.setItem("vd-home-layout", String(l)); } catch { /* ignore */ }
  };
  const [live, setLive] = useState(true);
  const [recent, setRecent] = useState<VisionEvent[]>([]);
  // Monitoramento: vazão agregada das câmeras conectadas (mesmo gráfico do drone/osmo).
  const prevRef = useRef<{ bytes: number; t: number } | null>(null);
  const [samples, setSamples] = useState<number[]>([]);
  const [mbps, setMbps] = useState(0);
  const [streamsN, setStreamsN] = useState(0);
  const monStable = streamsN > 0 ? mbps >= 0.1 : true;
  const [aerialOn, setAerialOn] = useState<Record<string, boolean>>({});

  // Poll de status das fontes aéreas (drone/osmo) → online aparece na grade.
  useEffect(() => {
    let on = true;
    const tick = async () => {
      const res = await Promise.all(AERIAL.map((a) => getAerialStatus(a.path).catch(() => ({ online: false }))));
      if (on) setAerialOn(Object.fromEntries(AERIAL.map((a, i) => [a.path, res[i].online])));
    };
    tick();
    const id = window.setInterval(tick, 3000);
    return () => { on = false; window.clearInterval(id); };
  }, []);

  useEffect(() => {
    listSavedCameras().then(setSaved).catch(() => undefined);
  }, [setSaved]);

  useEffect(() => {
    let on = true;
    const load = () => listEvents({ limit: 8 }).then((e) => on && setRecent(e)).catch(() => undefined);
    load();
    const id = window.setInterval(load, 10000);
    return () => {
      on = false;
      window.clearInterval(id);
    };
  }, []);

  // Poll da vazão dos streams ativos a cada 1.5s → Mbps por delta de bytes.
  useEffect(() => {
    let on = true;
    const tick = async () => {
      const s = await getStreamStats();
      if (!on) return;
      setStreamsN(s.streams);
      const now = performance.now() / 1000;
      if (prevRef.current) {
        const dt = now - prevRef.current.t;
        const v = dt > 0 ? Math.max(0, ((s.bytes - prevRef.current.bytes) * 8) / 1e6 / dt) : 0;
        setMbps(v); setSamples((p) => [...p, v].slice(-N));
      }
      prevRef.current = { bytes: s.bytes, t: now };
    };
    tick();
    const id = window.setInterval(tick, 1500);
    return () => { on = false; window.clearInterval(id); };
  }, []);

  const openCamera = (cam: SavedCamera) => setDetailCameraId(cam.id);

  // Dispositivos da malha com câmera ABERTA → aparecem ao vivo na grade (mesmo esquema das IP/local).
  const meshCams = mesh.roster.filter((p) => p.camera);
  // Fontes aéreas (drone/osmo) ONLINE → descem à grade junto das câmeras IP.
  const aerialCams = AERIAL.filter((a) => aerialOn[a.path]);

  return (
    <div className="flex flex-col gap-4 min-h-full">
      {/* Toolbar */}
      <div className="flex items-center gap-3 flex-wrap">
        <h2 className="text-lg font-bold">Painel</h2>
        <span className="text-xs text-muted">
          {saved.length + localCams.length + meshCams.length + aerialCams.length} câmera(s)
          {localCams.length ? ` · ${localCams.length} local` : ""}
          {meshCams.length ? ` · ${meshCams.length} dispositivo(s)` : ""}
          {aerialCams.length ? ` · ${aerialCams.length} aérea(s)` : ""}
        </span>

        <div className="ml-auto flex items-center gap-2">
          <div className="flex rounded-card border border-edge overflow-hidden">
            {([1, 4, 9] as Layout[]).map((l) => (
              <button
                key={l}
                onClick={() => setLayout(l)}
                className={
                  "px-3 py-1.5 text-sm transition-colors " +
                  (layout === l ? "bg-accent text-onaccent" : "bg-edge text-muted hover:text-text")
                }
                title={`Multiview ${l}`}
              >
                {l === 1 ? "◻" : l === 4 ? "▦" : "▩"} {l}
              </button>
            ))}
          </div>
          <button
            className={btnCls}
            onClick={() => setLive((v) => !v)}
            title="Pausar/retomar atualização ao vivo"
          >
            {live ? "⏸ Ao vivo" : "▶ Pausado"}
          </button>
          <button className={btnPrimaryCls} onClick={() => setScanOpen(true)}>
            🔍 Escanear
          </button>
        </div>
      </div>

      <div className="flex-1 grid grid-cols-1 xl:grid-cols-[1fr_300px] gap-4">
        {/* Dispositivos & fontes + grade de câmeras */}
        <div className="scroll-thin pr-1 space-y-4">
          <DevicesView mesh={mesh} camera={camera} live={live} />
          {saved.length === 0 && localCams.length === 0 && meshCams.length === 0 && aerialCams.length === 0 ? (
            <div className="h-full min-h-[300px] flex flex-col items-center justify-center text-center gap-3 border border-dashed border-edge rounded-card">
              <span className="text-4xl">📷</span>
              <p className="text-muted text-sm max-w-xs">
                Nenhuma câmera ainda. Escaneie a rede Wi-Fi, adicione uma câmera IP, ou conecte
                um dispositivo local (MacBook/USB/OBS) no Estúdio ou em Câmeras.
              </p>
              <button className={btnPrimaryCls} onClick={() => setScanOpen(true)}>
                🔍 Escanear rede
              </button>
            </div>
          ) : (
            <div className={"grid gap-3 " + COLS[layout]}>
              {localCams.map((c) => (
                <LocalCameraCard key={c.id} cam={c} live={live} onRemove={removeLocalCamera} />
              ))}
              {meshCams.map((p) => (
                <MeshCameraCard key={p.peer_id} peer={p} mesh={mesh} live={live} />
              ))}
              {aerialCams.map((a) => (
                <AerialCameraCard key={a.path} path={a.path} name={a.name} icon={a.icon}
                  online live={live} onOpen={() => setView(a.view)} />
              ))}
              {saved.map((cam) => (
                <CameraCard key={cam.id} camera={cam} live={live} onOpen={openCamera} />
              ))}
            </div>
          )}
        </div>

        {/* Coluna lateral: monitoramento + eventos */}
        <div className="flex flex-col gap-4 min-h-0">
        <div className="bg-panel rounded-card border border-edge p-3 shrink-0">
          <div className="flex items-center gap-2 mb-2">
            <h3 className="text-xs uppercase tracking-wider text-muted">Monitoramento — vazão</h3>
            <span className="ml-auto text-[10px] text-muted">{streamsN} câmera(s) ativa(s)</span>
          </div>
          <SignalChart samples={samples} stable={monStable} mbps={mbps} />
        </div>
        <aside className="bg-panel rounded-card border border-edge p-3 flex flex-col gap-3 flex-1 min-h-[30vh] lg:min-h-0">
          <div className="flex items-center gap-2">
            <h3 className="text-xs uppercase tracking-wider text-muted">Eventos recentes</h3>
            <button
              className="ml-auto text-xs text-accent hover:underline"
              onClick={() => setView("eventos")}
            >
              ver todos →
            </button>
          </div>
          <div className="flex-1 overflow-y-auto scroll-thin space-y-1.5">
            {recent.length === 0 ? (
              <p className="text-xs text-muted">Sem eventos ainda.</p>
            ) : (
              recent.map((e) => (
                <div key={e.detection_id} className="flex items-start gap-2 text-xs py-1 border-b border-edge/40">
                  <span className={"w-1.5 h-1.5 rounded-full mt-1 shrink-0 " + (SEV_DOT[e.severidade] ?? "bg-muted")} />
                  <div className="min-w-0">
                    <div className="flex items-center gap-1 text-muted">
                      <span>{e.icone}</span>
                      <span className="truncate">{e.source_label}</span>
                      <span className="ml-auto whitespace-nowrap">
                        {new Date(e.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                    <p className="text-text truncate">{e.titulo}</p>
                  </div>
                </div>
              ))
            )}
          </div>
        </aside>
        </div>
      </div>
    </div>
  );
}
