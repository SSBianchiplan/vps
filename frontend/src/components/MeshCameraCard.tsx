import { useEffect, useRef } from "react";
import type { DeviceMesh } from "../hooks/useDeviceMesh";
import type { RemotePeer } from "../api/devices";

function iconFor(platform: string, facing?: string): string {
  const p = (platform || "").toLowerCase();
  if (facing === "environment") return "📷";
  if (p.includes("iphone") || p.includes("ios")) return "📱";
  if (p.includes("android")) return "🤖";
  if (p.includes("ipad") || p.includes("tablet")) return "📲";
  if (p.includes("mac") || p.includes("windows") || p.includes("desktop")) return "💻";
  return "📱";
}

/** Tile de dispositivo da MALHA (celular/tablet/outro PC) no mesmo esquema da
 * câmera local/IP: ao conectar e abrir a câmera, ASSISTE automaticamente e
 * aparece AO VIVO na grade de câmeras conectadas. */
export function MeshCameraCard({ peer, mesh, live = true }: { peer: RemotePeer; mesh: DeviceMesh; live?: boolean }) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const stream = mesh.remoteStreams[peer.peer_id];
  const hasCam = !!peer.camera;
  const { watch, unwatch } = mesh;

  // auto-assistir quando o aparelho tem câmera aberta e a grade está ao vivo
  useEffect(() => {
    if (live && hasCam) { watch(peer.peer_id); return () => unwatch(peer.peer_id); }
  }, [live, hasCam, peer.peer_id, watch, unwatch]);

  const isLive = live && hasCam && !!stream;
  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    if (isLive && stream) { v.srcObject = stream; v.play().catch(() => undefined); }
    else v.srcObject = null;
    return () => { if (v) v.srcObject = null; };
  }, [isLive, stream]);

  const icon = iconFor(peer.platform, peer.camera?.facing);
  return (
    <div className="group relative bg-black rounded-card overflow-hidden border border-edge">
      <div className="aspect-video w-full flex items-center justify-center">
        <video ref={videoRef} className={"w-full h-full object-contain " + (isLive ? "" : "hidden")} playsInline muted />
        {!isLive && (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-muted text-xs px-3 text-center gap-1">
            <span className="text-2xl opacity-60">{icon}</span>
            <span>{hasCam ? "conectando…" : "câmera fechada"}</span>
            <span className="text-[10px] opacity-70">{hasCam ? "recebendo o feed do aparelho" : "abra a câmera no aparelho"}</span>
          </div>
        )}
        <span className="absolute top-1.5 left-1.5 text-[10px] px-1.5 py-0.5 rounded bg-black/50 text-white/80">{icon} {peer.platform || "dispositivo"}</span>
      </div>

      <div className="absolute bottom-0 inset-x-0 flex items-center gap-2 px-2 py-1.5 bg-gradient-to-t from-black/80 to-transparent">
        <span className={"w-2 h-2 rounded-full shrink-0 " + (isLive ? "bg-ok" : hasCam ? "bg-warn" : "bg-muted")} />
        <span className="text-xs text-white truncate flex-1" title={peer.name}>{peer.name}</span>
        {isLive && <span className="text-[10px] text-emerald-300 font-semibold">● AO VIVO</span>}
      </div>
    </div>
  );
}
