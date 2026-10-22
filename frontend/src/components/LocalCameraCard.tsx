import { useEffect, useRef } from "react";
import { useStore, type LocalCam } from "../store/useStore";

interface Props {
  cam: LocalCam;
  live?: boolean;
  onRemove?: (id: string) => void;
}

/** Tile de câmera de dispositivo local (getUserMedia). Espelha o stream ativo
 * compartilhado (sem reabrir o dispositivo): ao vivo quando o device está
 * conectado (Estúdio/Câmeras); inativo caso contrário. */
export function LocalCameraCard({ cam, live = true, onRemove }: Props) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const activeStream = useStore((s) => s.activeStream);
  const activeDeviceId = useStore((s) => s.activeDeviceId);
  const isLive = live && !!activeStream && activeDeviceId === cam.deviceId;
  const isScreen = cam.platform === "screen" || cam.deviceId === "screen";
  const icon = isScreen ? "🖥" : "💻";

  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    if (isLive && activeStream) { v.srcObject = activeStream; v.play().catch(() => undefined); }
    else v.srcObject = null;
    return () => { if (v) v.srcObject = null; };
  }, [isLive, activeStream]);

  return (
    <div className="group relative bg-black rounded-card overflow-hidden border border-edge">
      <div className="aspect-video w-full flex items-center justify-center">
        <video ref={videoRef} className={"w-full h-full object-contain " + (isLive ? "" : "hidden")} playsInline muted />
        {!isLive && (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-muted text-xs px-3 text-center gap-1">
            <span className="text-2xl opacity-60">{icon}</span>
            <span>fonte inativa</span>
            <span className="text-[10px] opacity-70">{isScreen ? "inicie a captura de tela no Estúdio ou em Câmeras" : "conecte o dispositivo no Estúdio ou em Câmeras"}</span>
          </div>
        )}
        <span className="absolute top-1.5 left-1.5 text-[10px] px-1.5 py-0.5 rounded bg-black/50 text-white/80">{icon} {isScreen ? "tela" : "local"}</span>
      </div>

      <div className="absolute bottom-0 inset-x-0 flex items-center gap-2 px-2 py-1.5 bg-gradient-to-t from-black/80 to-transparent">
        <span className={"w-2 h-2 rounded-full shrink-0 " + (isLive ? "bg-ok" : "bg-muted")} />
        <span className="text-xs text-white truncate flex-1" title={cam.name}>{cam.name}</span>
        {isLive && <span className="text-[10px] text-emerald-300 font-semibold">● AO VIVO</span>}
        {onRemove && (
          <button className="text-white/50 hover:text-nok text-xs" title="remover card"
            onClick={(e) => { e.stopPropagation(); onRemove(cam.id); }}>✕</button>
        )}
      </div>
    </div>
  );
}
