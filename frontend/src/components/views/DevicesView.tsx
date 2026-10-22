import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { DeviceMesh } from "../../hooks/useDeviceMesh";
import { getAerialRec, getAerialStatus, startAerialRec, stopAerialRec } from "../../api/aerial";
import { mtxMjpegUrl } from "../../api/cameras";
import { useStore, type View } from "../../store/useStore";
import { btnPrimaryCls, inputCls } from "../../lib/ui";
import { OnlineBar, type LocalCamCtl } from "../OnlineBar";

export type { LocalCamCtl };

// Card de fonte do sistema (drone/osmo): preview ao vivo + Play/Pause/Stop/Gravar + status.
function SourceCard({ icon, name, path, online, live, onOpen }: { icon: string; name: string; path: string; online: boolean; live: boolean; onOpen: () => void }) {
  const [playing, setPlaying] = useState(false);
  const [rec, setRec] = useState(false);
  useEffect(() => { if (!online || !live) setPlaying(false); }, [online, live]);
  useEffect(() => {
    let on = true; const tick = () => getAerialRec(path).then((r) => on && setRec(r.recording));
    tick(); const id = window.setInterval(tick, 3000); return () => { on = false; window.clearInterval(id); };
  }, [path]);
  const toggleRec = useCallback(async () => { setRec((await (rec ? stopAerialRec(path) : startAerialRec(path))).recording); }, [rec, path]);
  const stop = useCallback(async () => { setPlaying(false); if (rec) { await stopAerialRec(path); setRec(false); } }, [rec, path]);
  const ctl = "flex-1 py-1 rounded text-sm border transition-colors disabled:opacity-40 ";

  return (
    <div className="bg-surface border border-edge rounded-card overflow-hidden flex flex-col">
      <div className="aspect-video w-full bg-black flex items-center justify-center relative">
        {playing && online
          ? <img src={mtxMjpegUrl(path, 960)} className="w-full h-full object-contain" alt={name} />
          : <span className="text-3xl opacity-60">{icon}</span>}
        {online && <span className="absolute top-1.5 left-1.5 text-[10px] text-emerald-300 font-bold bg-black/50 px-1.5 py-0.5 rounded">● AO VIVO</span>}
        {rec && <span className="absolute top-1.5 left-1.5 mt-5 text-[10px] text-nok font-bold bg-black/50 px-1.5 py-0.5 rounded">● REC</span>}
        <span className={"absolute top-1.5 right-1.5 w-2 h-2 rounded-full " + (online ? "bg-ok animate-pulse" : "bg-muted")} title={online ? "conectado" : "offline"} />
      </div>
      <div className="p-2.5 flex flex-col gap-1.5">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-base shrink-0">{icon}</span>
          <span className="text-sm text-text truncate flex-1">{name}</span>
          <span className={"text-[10px] shrink-0 " + (online ? "text-ok" : "text-muted")}>{online ? "● conectado" : "○ offline"}</span>
        </div>
        <div className="flex items-center gap-1">
          <button className={ctl + "border-edge bg-edge hover:border-accent"} disabled={!online || playing} onClick={() => setPlaying(true)} title="Play">▶</button>
          <button className={ctl + "border-edge bg-edge hover:border-accent"} disabled={!playing} onClick={() => setPlaying(false)} title="Pause">⏸</button>
          <button className={ctl + "border-edge bg-edge hover:border-accent"} onClick={stop} title="Stop">■</button>
          <button className={ctl + (rec ? "border-nok text-nok bg-nok/10" : "border-edge bg-edge hover:border-accent")} disabled={!online && !rec} onClick={toggleRec} title="Gravar">⏺</button>
        </div>
        <button className="text-[11px] text-accent hover:underline text-left" onClick={onOpen}>Ver no módulo →</button>
      </div>
    </div>
  );
}

// Card da CÂMERA LOCAL (reusa o useCamera do App) + Gravar (MediaRecorder → download).
function LocalDeviceCard({ name, camera }: { name: string; camera: LocalCamCtl }) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const recRef = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const activeStream = useStore((s) => s.activeStream);
  const [paused, setPaused] = useState(false);
  const [recording, setRecording] = useState(false);
  const on = !!activeStream;
  const err = camera.error;

  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    if (v.srcObject !== activeStream) v.srcObject = activeStream;
    if (activeStream && !paused) v.play().catch(() => undefined);
  }, [activeStream, paused]);

  const stopRec = useCallback(() => { recRef.current?.stop(); recRef.current = null; setRecording(false); }, []);
  const toggleRec = useCallback(() => {
    if (recording) return stopRec();
    if (!activeStream) return;
    const mime = MediaRecorder.isTypeSupported("video/mp4") ? "video/mp4" : "video/webm";
    const mr = new MediaRecorder(activeStream, { mimeType: mime });
    chunks.current = [];
    mr.ondataavailable = (e) => { if (e.data.size) chunks.current.push(e.data); };
    mr.onstop = () => {
      const url = URL.createObjectURL(new Blob(chunks.current, { type: mime }));
      const a = document.createElement("a"); a.href = url; a.download = `local_${Date.now()}.${mime.includes("mp4") ? "mp4" : "webm"}`;
      document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 8000);
    };
    mr.start(); recRef.current = mr; setRecording(true);
  }, [recording, activeStream, stopRec]);

  const ctl = "flex-1 py-1 rounded text-sm border transition-colors disabled:opacity-40 ";
  return (
    <div className="bg-surface border border-edge rounded-card overflow-hidden flex flex-col">
      <div className="aspect-video w-full bg-black flex items-center justify-center relative">
        <video ref={videoRef} className={"w-full h-full object-contain " + (on ? "" : "hidden")} playsInline muted />
        {!on && <div className="flex flex-col items-center gap-1 text-muted text-xs"><span className="text-3xl opacity-60">💻</span><span>câmera local fechada</span></div>}
        {on && <span className="absolute top-1.5 left-1.5 text-[10px] text-emerald-300 font-bold bg-black/50 px-1.5 py-0.5 rounded">● AO VIVO</span>}
        {recording && <span className="absolute top-1.5 left-1.5 mt-5 text-[10px] text-nok font-bold bg-black/50 px-1.5 py-0.5 rounded">● REC</span>}
        <span className={"absolute top-1.5 right-1.5 w-2 h-2 rounded-full " + (on ? "bg-ok animate-pulse" : "bg-muted")} />
      </div>
      <div className="p-2.5 flex flex-col gap-1.5">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-base shrink-0">💻</span>
          <span className="text-sm text-text truncate flex-1">{name} (câmera local)</span>
          <span className={"text-[10px] shrink-0 " + (on ? "text-ok" : "text-muted")}>{on ? "● ao vivo" : "○ fechada"}</span>
        </div>
        <div className="flex items-center gap-1">
          <button className={ctl + "border-edge bg-edge hover:border-accent"} disabled={on && !paused} onClick={() => { setPaused(false); camera.start(); }} title="Play">▶</button>
          <button className={ctl + "border-edge bg-edge hover:border-accent"} disabled={!on || paused} onClick={() => { setPaused(true); videoRef.current?.pause(); }} title="Pause">⏸</button>
          <button className={ctl + "border-edge bg-edge hover:border-accent"} disabled={!on} onClick={() => { stopRec(); camera.stop(); setPaused(false); }} title="Stop">■</button>
          <button className={ctl + (recording ? "border-nok text-nok bg-nok/10" : "border-edge bg-edge hover:border-accent")} disabled={!on && !recording} onClick={toggleRec} title="Gravar">⏺</button>
        </div>
        {err && <p className="text-[10px] text-nok">⚠ {err}</p>}
      </div>
    </div>
  );
}

export function DevicesView({ mesh, camera, live = true }: { mesh: DeviceMesh; camera: LocalCamCtl; live?: boolean }) {
  const setView = useStore((s) => s.setView);
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(mesh.deviceName);
  const [src, setSrc] = useState({ drone: false, osmo: false });
  const [showList, setShowList] = useState(false);
  const btnRef = useRef<HTMLButtonElement>(null);
  const [pos, setPos] = useState({ top: 96, right: 24 });
  useEffect(() => setName(mesh.deviceName), [mesh.deviceName]);

  const toggleList = () => {
    const r = btnRef.current?.getBoundingClientRect();
    if (r) setPos({ top: r.bottom + 6, right: Math.max(8, window.innerWidth - r.right) });
    setShowList((v) => !v);
  };

  useEffect(() => {
    let on = true;
    const tick = async () => {
      const [d, o] = await Promise.all([getAerialStatus("drone_neo2"), getAerialStatus("osmo_pocket")]);
      if (on) setSrc({ drone: d.online, osmo: o.online });
    };
    tick(); const id = window.setInterval(tick, 3000);
    return () => { on = false; window.clearInterval(id); };
  }, []);

  const save = () => { mesh.setDeviceName(name); setEditing(false); };
  const go = (v: View) => () => setView(v);

  return (
    <div className="flex flex-col gap-3">
      <div className="relative flex items-center gap-3 flex-wrap bg-panel border border-edge rounded-card p-3">
        <span className="text-xs uppercase tracking-wider text-muted">Este dispositivo</span>
        {editing ? (
          <>
            <input className={inputCls + " max-w-[200px]"} value={name} autoFocus
              onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && save()} />
            <button className={btnPrimaryCls} onClick={save}>Salvar</button>
          </>
        ) : (
          <>
            <span className="text-sm font-semibold text-text">{mesh.deviceName}</span>
            <button className="text-xs text-accent hover:underline" onClick={() => setEditing(true)}>renomear</button>
          </>
        )}
        <span className="ml-auto flex items-center gap-1.5 text-xs text-muted">
          <span className={"w-2 h-2 rounded-full " + (mesh.online ? "bg-ok" : "bg-nok")} />
          {mesh.online ? "presença ativa" : "offline"}
        </span>
        <button
          ref={btnRef}
          onClick={toggleList}
          className={"text-xs px-2.5 py-1 rounded-card border transition-colors " +
            (showList ? "bg-accent text-onaccent border-accent" : "bg-edge border-edge text-muted hover:text-text")}
          title="Lista de câmeras com Play/Stop/Rec">
          📹 Câmeras
        </button>
        {showList && createPortal(
          <div style={{ top: pos.top, right: pos.right }}
            className="fixed z-[100] w-80 bg-surface border border-edge rounded-card shadow-2xl overflow-hidden">
            <div className="flex items-center px-3 py-2 border-b border-edge">
              <span className="text-xs uppercase tracking-wider text-muted font-semibold">📹 Câmeras online</span>
              <button className="ml-auto text-muted hover:text-text text-sm" onClick={() => setShowList(false)}>✕</button>
            </div>
            <div className="max-h-[70vh] overflow-y-auto scroll-thin"><OnlineBar camera={camera} /></div>
          </div>,
          document.body,
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        <LocalDeviceCard name={mesh.deviceName} camera={camera} />
        <SourceCard icon="🛸" name="Drone (Visão Aérea)" path="drone_neo2" online={src.drone} live={live} onOpen={go("aerea")} />
        <SourceCard icon="📷" name="Vídeo Osmo" path="osmo_pocket" online={src.osmo} live={live} onOpen={go("osmo")} />
      </div>
    </div>
  );
}
