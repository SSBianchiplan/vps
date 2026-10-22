import { mtxMjpegUrl } from "../api/cameras";

interface Props {
  path: string;        // ex.: drone_neo2 / osmo_pocket (MediaMTX)
  name: string;
  icon: string;
  online: boolean;
  live?: boolean;
  onOpen?: () => void;
}

/** Tile de fonte aérea (drone/osmo) na grade de câmeras conectadas, mesmo
 * esquema da IP/local/malha: ao ficar ONLINE mostra o feed MJPEG AO VIVO. */
export function AerialCameraCard({ path, name, icon, online, live = true, onOpen }: Props) {
  const isLive = online && live;
  return (
    <div className="group relative bg-black rounded-card overflow-hidden border border-edge">
      <div className="aspect-video w-full flex items-center justify-center">
        {isLive ? (
          <img src={mtxMjpegUrl(path, 960)} className="w-full h-full object-contain" alt={name} />
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-muted text-xs px-3 text-center gap-1">
            <span className="text-2xl opacity-60">{icon}</span>
            <span>offline</span>
            <span className="text-[10px] opacity-70">ligue a fonte para aparecer ao vivo</span>
          </div>
        )}
        <span className="absolute top-1.5 left-1.5 text-[10px] px-1.5 py-0.5 rounded bg-black/50 text-white/80">{icon} {name}</span>
        {isLive && <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-ok animate-pulse" />}
      </div>

      <div className="absolute bottom-0 inset-x-0 flex items-center gap-2 px-2 py-1.5 bg-gradient-to-t from-black/80 to-transparent">
        <span className={"w-2 h-2 rounded-full shrink-0 " + (isLive ? "bg-ok" : "bg-muted")} />
        <span className="text-xs text-white truncate flex-1" title={name}>{name}</span>
        {isLive && <span className="text-[10px] text-emerald-300 font-semibold">● AO VIVO</span>}
        {onOpen && (
          <button className="text-white/50 hover:text-accent text-xs" title="ver no módulo"
            onClick={(e) => { e.stopPropagation(); onOpen(); }}>↗</button>
        )}
      </div>
    </div>
  );
}
