import { useState } from "react";
import { mjpegUrl, type SavedCamera } from "../api/cameras";

interface Props {
  camera: SavedCamera;
  live?: boolean;
  onOpen?: (cam: SavedCamera) => void;
}

/** Tile de câmera com stream MJPEG ao vivo (baixa latência) + retry em erro. */
export function CameraCard({ camera, live = true, onOpen }: Props) {
  const off = camera.enabled === false;   // desligada no sistema (raiz backend) → não transmite
  const on = live && !off;
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [retry, setRetry] = useState(0);

  const onErr = () => {
    setStatus("error");
    window.setTimeout(() => setRetry((r) => r + 1), 4000); // reconecta após blip
  };

  const dot = status === "ok" ? "bg-ok" : status === "error" ? "bg-nok" : "bg-warn animate-pulse";

  return (
    <button
      onClick={() => onOpen?.(camera)}
      className="group relative bg-black rounded-card overflow-hidden border border-edge hover:border-accent transition-colors text-left"
    >
      <div className="aspect-video w-full flex items-center justify-center">
        {on ? (
          <img
            key={retry}
            src={mjpegUrl(camera.id, true) + (retry ? `&r=${retry}` : "")}
            alt={camera.name}
            className="w-full h-full object-contain"
            onLoad={() => setStatus("ok")}
            onError={onErr}
          />
        ) : (
          <span className="text-muted text-xs">{off ? "○ desligada" : "⏸ pausado"}</span>
        )}
        {on && status === "error" && (
          <div className="absolute inset-0 flex items-center justify-center text-muted text-xs px-3 text-center">
            ⚠ sem sinal<div className="text-[10px] opacity-70 mt-0.5">{camera.ip}</div>
          </div>
        )}
      </div>

      <div className="absolute bottom-0 inset-x-0 flex items-center gap-2 px-2 py-1.5 bg-gradient-to-t from-black/80 to-transparent">
        <span className={"w-2 h-2 rounded-full shrink-0 " + dot} />
        <span className="text-xs text-white truncate">{camera.name}</span>
        {on && status === "ok" && (
          <span className="ml-auto text-[10px] text-emerald-300 font-semibold">● AO VIVO</span>
        )}
      </div>
    </button>
  );
}
