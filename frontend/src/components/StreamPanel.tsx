import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import {
  aerialRecordingUrl, getAerialConfig, getAerialRec, getAerialStatus, getAerialTest,
  listAerialRecordings, startAerialRec, startAerialTest, stopAerialRec, stopAerialTest, whep,
  type AerialConfig, type AerialRecItem, type AerialStatus,
} from "../api/aerial";
import { btnCls, btnPrimaryCls } from "../lib/ui";
import { SignalChart } from "./SignalChart";
import { RecTimer } from "./RecTimer";

const ICE: RTCConfiguration = { iceServers: [{ urls: "stun:stun.l.google.com:19302" }] };
const N = 48, STABLE_MBPS = 0.2;
const mb = (b: number) => `${(b / 1048576).toFixed(1)} MB`;

function iceDone(pc: RTCPeerConnection): Promise<void> {
  return new Promise((res) => {
    if (pc.iceGatheringState === "complete") return res();
    const t = setTimeout(res, 800);
    pc.addEventListener("icegatheringstatechange", () => { if (pc.iceGatheringState === "complete") { clearTimeout(t); res(); } });
  });
}
// Jitter buffer pequeno (não 0): absorve jitter de WiFi/4G → reprodução FLUIDA
// mantendo latência baixa. 0 era agressivo demais e causava travadas.
function smoothBuffer(r: RTCRtpReceiver): void {
  try { (r as unknown as { jitterBufferTarget?: number }).jitterBufferTarget = 0.3; } catch { /* noop */ }
  try { (r as unknown as { playoutDelayHint?: number }).playoutDelayHint = 0.3; } catch { /* noop */ }
}

export interface StreamPanelProps {
  path: string;
  icon: string;
  title: string;
  subtitle: string;
  offlineHint: string;
  testLabel: string;
  opTitle: string;
  rtmpLabel: string;
  latencyText: string;
  steps: ReactNode;
  footerNote: ReactNode;
  hostNote?: ReactNode;      // nota abaixo da URL RTMP (host/rede)
  extras?: ReactNode;        // ex.: passo a passo VPN (drone)
  headerExtra?: ReactNode;   // ex.: abas USB/RTMP (osmo)
}

/** Painel de stream ao vivo (RTMP→MediaMTX→WebRTC) — compartilhado por drone e osmo. */
export function StreamPanel(props: StreamPanelProps) {
  const { path } = props;
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const pcRef = useRef<RTCPeerConnection | null>(null);
  const prevRef = useRef<{ bytes: number; t: number } | null>(null);
  const [cfg, setCfg] = useState<AerialConfig | null>(null);
  const [status, setStatus] = useState<AerialStatus>({ online: false });
  const [conn, setConn] = useState<"idle" | "connecting" | "live" | "error">("idle");
  const [err, setErr] = useState<string | null>(null);
  const [testCmd, setTestCmd] = useState("");
  const [testOn, setTestOn] = useState(false);
  const [testErr, setTestErr] = useState<string | null>(null);
  const [samples, setSamples] = useState<number[]>([]);
  const [mbps, setMbps] = useState(0);
  const [rec, setRec] = useState<{ recording: boolean; size: number }>({ recording: false, size: 0 });
  const [recs, setRecs] = useState<AerialRecItem[]>([]);

  const stable = status.online ? mbps >= STABLE_MBPS : false;

  useEffect(() => { getAerialConfig(path).then(setCfg).catch(() => undefined); }, [path]);
  useEffect(() => { getAerialTest(path).then((t) => { setTestOn(t.running); if (t.default_cmd) setTestCmd((c) => c || t.default_cmd!); }); }, [path]);
  const refreshRecs = useCallback(() => { listAerialRecordings(path).then(setRecs); }, [path]);
  useEffect(() => { refreshRecs(); }, [refreshRecs]);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      const [s, r] = await Promise.all([getAerialStatus(path), getAerialRec(path)]);
      if (!alive) return;
      setStatus(s); setRec({ recording: r.recording, size: r.size ?? 0 });
      const now = performance.now() / 1000, bytes = s.bytes_received ?? 0;
      if (s.online && prevRef.current) {
        const dt = now - prevRef.current.t;
        const v = dt > 0 ? Math.max(0, ((bytes - prevRef.current.bytes) * 8) / 1e6 / dt) : 0;
        setMbps(v); setSamples((p) => [...p, v].slice(-N));
      } else if (!s.online) { setMbps(0); setSamples((p) => (p.length ? [...p, 0].slice(-N) : p)); }
      prevRef.current = s.online ? { bytes, t: now } : null;
    };
    tick(); const iv = window.setInterval(tick, 1500);
    return () => { alive = false; window.clearInterval(iv); };
  }, [path]);

  const toggleTest = useCallback(async () => {
    setTestErr(null);
    const r = testOn ? await stopAerialTest(path) : await startAerialTest(testCmd, path);
    setTestOn(r.running);
    if (r.error) setTestErr(r.error);
  }, [testOn, testCmd, path]);

  const toggleRec = useCallback(async () => {
    const r = rec.recording ? await stopAerialRec(path) : await startAerialRec(path);
    setRec({ recording: r.recording, size: r.size ?? 0 });
    if (!r.recording) setTimeout(refreshRecs, 500);
  }, [rec.recording, refreshRecs, path]);

  const downloadRec = useCallback(async (name: string) => {
    try {
      const res = await fetch(aerialRecordingUrl(name));
      if (!res.ok) throw new Error(String(res.status));
      const url = URL.createObjectURL(await res.blob());
      const a = document.createElement("a"); a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 8000);
    } catch (e) { setErr(`download falhou: ${String((e as Error)?.message ?? e)}`); }
  }, []);

  const stopConn = useCallback(() => {
    pcRef.current?.close(); pcRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setConn("idle");
  }, []);

  const connect = useCallback(async () => {
    stopConn(); setErr(null); setConn("connecting");
    try {
      const pc = new RTCPeerConnection(ICE);
      pcRef.current = pc;
      pc.addTransceiver("video", { direction: "recvonly" });
      pc.addTransceiver("audio", { direction: "recvonly" });
      pc.ontrack = (e) => { smoothBuffer(e.receiver); if (videoRef.current) videoRef.current.srcObject = e.streams[0]; };
      pc.onconnectionstatechange = () => {
        const st = pc.connectionState;
        if (st === "connected") setConn("live");
        else if (["failed", "disconnected", "closed"].includes(st)) setConn((c) => (c === "live" ? "error" : c));
      };
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      await iceDone(pc);
      const answer = await whep(pc.localDescription!.sdp, path);
      await pc.setRemoteDescription({ type: "answer", sdp: answer });
      pc.getReceivers().forEach(smoothBuffer);
    } catch (e) { setErr(String((e as Error)?.message ?? e)); setConn("error"); }
  }, [stopConn, path]);

  useEffect(() => () => stopConn(), [stopConn]);
  useEffect(() => { if (status.online && conn === "idle") connect(); }, [status.online, conn, connect]);

  const live = conn === "live";
  const Field = ({ label, value }: { label: string; value: string }) => (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-muted">{label}</div>
      <code className="block text-xs bg-edge border border-edge rounded-card px-2 py-1 mt-0.5 break-all select-all">{value}</code>
    </div>
  );

  return (
    <div className="flex flex-col gap-4 min-h-full">
      <div className="flex items-center gap-3 flex-wrap">
        <h2 className="text-lg font-bold">{props.icon} {props.title}</h2>
        {props.headerExtra}
        <span className={"flex items-center gap-1.5 text-xs font-semibold " + (status.online ? "text-nok" : "text-muted")}>
          <span className={"w-2 h-2 rounded-full " + (status.online ? "bg-nok animate-pulse" : "bg-muted")} />
          {status.online ? `● AO VIVO${status.readers ? ` · ${status.readers} espectador(es)` : ""}` : "○ Offline"}
        </span>
        {rec.recording && <span className="flex items-center gap-1 text-xs font-semibold text-nok"><span className="w-2 h-2 rounded-full bg-nok animate-pulse" />REC · {mb(rec.size)}</span>}
        <span className="text-xs text-muted">{props.subtitle}</span>
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-[1fr_340px] gap-4 min-h-0">
        <div className="flex flex-col min-h-0">
          {rec.recording && <RecTimer size={rec.size} />}
          <div className="relative flex-1 bg-black rounded-card overflow-hidden flex items-center justify-center min-h-[40vh]">
            <video ref={videoRef} className="w-full h-full object-contain" autoPlay muted playsInline />
            {!live && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-muted text-sm px-4 text-center">
                <span className="text-4xl">{props.icon}</span>
                {conn === "connecting" ? "conectando…" : status.online ? "stream no ar — clique em Conectar" : props.offlineHint}
                {err && <span className="text-nok text-xs">⚠ {err}</span>}
              </div>
            )}
            {live && <span className="absolute top-2 left-2 text-[10px] text-emerald-300 font-bold bg-black/50 px-1.5 py-0.5 rounded">● AO VIVO · WebRTC</span>}
          </div>
          <div className="flex items-center gap-2 mt-3 flex-wrap">
            {!live
              ? <button className={btnPrimaryCls} disabled={conn === "connecting"} onClick={connect}>{conn === "connecting" ? "Conectando…" : "▶ Conectar"}</button>
              : <button className={btnCls} onClick={stopConn}>■ Parar</button>}
            <button className={"px-3 py-1.5 rounded text-sm font-medium border transition-colors " + (rec.recording ? "border-nok text-nok bg-nok/10" : "border-edge bg-edge hover:border-accent")}
              onClick={toggleRec} disabled={!status.online && !rec.recording}
              title="Grava a transmissão em .mp4 (qualidade original) no servidor">
              {rec.recording ? `■ Parar gravação · ${mb(rec.size)}` : "⏺ Gravar"}
            </button>
            {cfg && <a className={btnCls} href={cfg.hls_url} target="_blank" rel="noreferrer">Abrir HLS (Safari)</a>}
            <span className="text-[11px] text-muted ml-auto">{props.latencyText}</span>
          </div>
        </div>

        <aside className="bg-panel rounded-card border border-edge p-4 overflow-y-auto scroll-thin space-y-4">
          <div>
            <h3 className="text-xs uppercase tracking-wider text-muted mb-2">{props.opTitle}</h3>
            <SignalChart samples={samples} stable={stable} mbps={mbps} />
            <ol className="text-xs text-text space-y-1.5 list-decimal pl-4 mt-3">{props.steps}</ol>
            <details className="text-xs mt-3">
              <summary className="cursor-pointer text-muted hover:text-text select-none">🧪 {props.testLabel} (simular no servidor)</summary>
              <div className="mt-2 space-y-1.5">
                <button className={(testOn ? btnCls : btnPrimaryCls) + " w-full"} onClick={toggleTest}>
                  {testOn ? "■ Parar teste" : `🧪 ${props.testLabel}`}
                </button>
                <input className="w-full bg-edge border border-edge rounded-card px-2 py-1 text-[11px] font-mono text-text"
                  value={testCmd} onChange={(e) => setTestCmd(e.target.value)} spellCheck={false}
                  title="Comando ffmpeg editável, executado no servidor" />
                {testErr && <p className="text-[11px] text-nok">⚠ {testErr}</p>}
              </div>
            </details>
          </div>
          <div className="space-y-2">
            <Field label={props.rtmpLabel} value={cfg?.rtmp_url ?? `rtmp://<IP-do-servidor>:1935/${cfg?.path ?? path}`} />
            {props.hostNote}
            {cfg && <Field label="HLS" value={cfg.hls_url} />}
          </div>

          {props.extras}

          {recs.length > 0 && (
            <div>
              <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Gravações</h3>
              <div className="space-y-1">
                {recs.slice(0, 8).map((r) => (
                  <button key={r.name} onClick={() => downloadRec(r.name)} title="Baixar .mp4"
                    className="w-full flex items-center gap-2 text-[11px] bg-edge border border-edge rounded-card px-2 py-1 hover:border-accent text-left">
                    <span className="text-accent">⬇</span>
                    <span className="font-mono text-text truncate flex-1">{r.name}</span>
                    <span className="text-muted shrink-0">{mb(r.size)}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          <p className="text-[10px] text-muted">{props.footerNote}</p>
        </aside>
      </div>
    </div>
  );
}
