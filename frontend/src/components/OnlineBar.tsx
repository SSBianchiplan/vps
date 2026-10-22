import { useCallback, useEffect, useRef, useState } from "react";
import { useStore, type View } from "../store/useStore";
import { getAerialRec, getAerialStatus, startAerialRec, stopAerialRec } from "../api/aerial";
import { getCamRecord, listSavedCameras, setCameraEnabled, startCamRecord, stopCamRecord, type SavedCamera } from "../api/cameras";

// Controle mínimo do useCamera do App (mesmo caminho do Estúdio → sem conflito).
export interface LocalCamCtl {
  start: (id?: string | null) => void;
  stop: () => void;
  error: string | null;
  active: boolean;
}

// Linha: ícone + nome (visível) + status + ▶ Play · ■ Stop · ⏺ Rec.
function Row({ icon, name, online, recording, onPlay, onStop, onRec }: {
  icon: string; name: string; online: boolean; recording: boolean;
  onPlay: () => void; onStop: () => void; onRec: () => void;
}) {
  const b = "w-8 h-8 grid place-items-center rounded border text-sm transition-colors ";
  return (
    <div className="flex items-center gap-2 px-3 py-2 border-b border-edge/40 last:border-0 hover:bg-edge/30">
      <span className="text-lg shrink-0">{icon}</span>
      <div className="min-w-0 flex-1">
        <p className="text-xs text-text leading-tight break-words">{name}</p>
        <span className={"text-[10px] " + (online ? "text-ok" : "text-muted")}>{online ? "● online" : "○ offline"}</span>
      </div>
      <button className={b + "border-edge bg-edge hover:border-accent"} onClick={onPlay} title="Play">▶</button>
      <button className={b + "border-edge bg-edge hover:border-accent"} onClick={onStop} title="Stop">■</button>
      <button className={b + (recording ? "border-nok text-nok bg-nok/10" : "border-edge bg-edge hover:border-accent")} onClick={onRec} title="Gravar">⏺</button>
    </div>
  );
}

function AerialRow({ icon, name, path, view }: { icon: string; name: string; path: string; view: View }) {
  const setView = useStore((s) => s.setView);
  const [online, setOnline] = useState(false);
  const [rec, setRec] = useState(false);
  useEffect(() => {
    let on = true;
    const tick = async () => {
      const [s, r] = await Promise.all([getAerialStatus(path), getAerialRec(path)]);
      if (on) { setOnline(s.online); setRec(r.recording); }
    };
    tick(); const id = window.setInterval(tick, 3000); return () => { on = false; window.clearInterval(id); };
  }, [path]);
  const toggleRec = useCallback(async () => { setRec((await (rec ? stopAerialRec(path) : startAerialRec(path))).recording); }, [rec, path]);
  return <Row icon={icon} name={name} online={online} recording={rec}
    onPlay={() => setView(view)} onStop={() => rec && stopAerialRec(path).then(() => setRec(false))} onRec={toggleRec} />;
}

function CamRow({ cam }: { cam: SavedCamera }) {
  const setSaved = useStore((s) => s.setSavedCameras);
  const id = cam.id;
  const on = cam.enabled !== false;
  const [rec, setRec] = useState(false);
  useEffect(() => {
    let alive = true;
    const tick = () => getCamRecord(id).then((r) => alive && setRec(r.recording));
    tick(); const t = window.setInterval(tick, 3000); return () => { alive = false; window.clearInterval(t); };
  }, [id]);
  // Liga/desliga na raiz (backend) → reflete em todo o sistema; re-sincroniza a lista.
  const setOn = useCallback(async (v: boolean) => { await setCameraEnabled(id, v); setSaved(await listSavedCameras()); }, [id, setSaved]);
  const toggleRec = useCallback(async () => { setRec((await (rec ? stopCamRecord(id) : startCamRecord(id))).recording); }, [rec, id]);
  // Play = liga/conecta a câmera; Stop = parar total (desliga o stream) + parar gravação.
  const stopAll = useCallback(async () => { if (rec) { await stopCamRecord(id); setRec(false); } await setOn(false); }, [id, rec, setOn]);
  return <Row icon="📷" name={cam.name} online={on} recording={rec}
    onPlay={() => setOn(true)} onStop={stopAll} onRec={toggleRec} />;
}

/** Segmentação de câmeras do sistema (inline, dentro do card "Este dispositivo"). */
export function OnlineBar({ camera }: { camera: LocalCamCtl }) {
  const saved = useStore((s) => s.savedCameras);
  const activeStream = useStore((s) => s.activeStream);
  const recRef = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const [localRec, setLocalRec] = useState(false);

  const stopLocalRec = useCallback(() => { recRef.current?.stop(); recRef.current = null; setLocalRec(false); }, []);
  const toggleLocalRec = useCallback(() => {
    if (localRec) return stopLocalRec();
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
    mr.start(); recRef.current = mr; setLocalRec(true);
  }, [localRec, activeStream, stopLocalRec]);

  return (
    <div>
      <Row icon="💻" name="Câmera local (este dispositivo)" online={!!activeStream} recording={localRec}
        onPlay={() => camera.start()} onStop={() => { stopLocalRec(); camera.stop(); }} onRec={toggleLocalRec} />
      <AerialRow icon="🛸" name="Drone — Visão Aérea" path="drone_neo2" view="aerea" />
      <AerialRow icon="📷" name="Vídeo Osmo" path="osmo_pocket" view="osmo" />
      {saved.map((c) => <CamRow key={c.id} cam={c} />)}
      <p className="text-[10px] text-muted px-3 py-1.5">IP: ▶ liga · ■ desliga (para tudo) · ⏺ grava. Drone/Osmo: ▶ abre módulo. Gravações em Downloads.</p>
    </div>
  );
}
