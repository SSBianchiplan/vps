import type { RefObject } from "react";
import { useStore, CAPTURE_PRESETS } from "../store/useStore";
import { btnCls, btnPrimaryCls } from "../lib/ui";
import { mjpegUrl, mtxMjpegUrl, mtxPath } from "../api/cameras";
import { CanvasOverlay } from "./CanvasOverlay";
import { HealthBar } from "./HealthBar";

interface Props {
  videoRef: RefObject<HTMLVideoElement>;
  imgRef: RefObject<HTMLImageElement>;
  cameraActive: boolean;
  onStart: () => void;
  onStop: () => void;
  onSnapshot: () => void;
}

export function PreviewPanel(props: Props) {
  const running = useStore((s) => s.running);
  const connected = useStore((s) => s.connected);
  const error = useStore((s) => s.error);
  const sourceMode = useStore((s) => s.sourceMode);
  const ipUrl = useStore((s) => s.ipUrl);
  const selectedCameraId = useStore((s) => s.selectedCameraId);
  const captureWidth = useStore((s) => s.captureWidth);
  const setCaptureWidth = useStore((s) => s.setCaptureWidth);

  const mtx = mtxPath(ipUrl);
  const ipReady = !!selectedCameraId || !!ipUrl;
  const sourceReady = sourceMode === "device" ? props.cameraActive : ipReady;
  const canRun = sourceReady && connected;
  // Fonte de STREAM ao vivo (câmera salva / drone / osmo): preview MJPEG SEMPRE suave
  // (30fps), com a inferência rodando por cima (boxes). Igual à tela do osmo.
  const liveStream = sourceMode === "ip" && (!!selectedCameraId || !!mtx);
  const liveSrc = selectedCameraId
    ? mjpegUrl(selectedCameraId, false, captureWidth || undefined)
    : mtx ? mtxMjpegUrl(mtx, captureWidth || undefined) : "";

  const showPlaceholder = sourceMode === "device" ? !props.cameraActive : (!liveStream && !running);
  const placeholder =
    sourceMode === "device"
      ? "Conecte uma câmera para iniciar"
      : ipUrl
        ? "Clique em Iniciar para capturar da câmera IP (URL manual)"
        : "Selecione uma câmera/stream ou defina a URL (ou escaneie a rede)";

  return (
    <div className="flex flex-col h-full">
      <div className="relative flex-1 bg-black rounded-lg overflow-hidden flex items-center justify-center">
        {sourceMode === "device" ? (
          <video ref={props.videoRef} className="w-full h-full object-contain" playsInline muted />
        ) : liveStream ? (
          // MJPEG ao vivo (suave) — o loop em App grava snapshots p/ inferência sem tocar nesta img.
          <img ref={props.imgRef} src={liveSrc} className="w-full h-full object-contain" alt="stream ao vivo" />
        ) : (
          // URL manual: a img de captura (snapshots vêm do loop em App).
          <img ref={props.imgRef} className="w-full h-full object-contain" alt="câmera IP" />
        )}
        <CanvasOverlay mediaRef={sourceMode === "device" ? props.videoRef : props.imgRef} />
        {liveStream && (
          <span className="absolute top-2 left-2 text-[10px] text-emerald-300 font-bold bg-black/50 px-1.5 py-0.5 rounded">● AO VIVO</span>
        )}
        {showPlaceholder && (
          <div className="absolute inset-0 flex items-center justify-center text-muted text-sm px-4 text-center">
            {placeholder}
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 mt-3">
        {!running ? (
          <button className={btnPrimaryCls} disabled={!canRun} onClick={props.onStart}>
            ▶ Iniciar
          </button>
        ) : (
          <button className={btnCls} onClick={props.onStop}>
            ⏸ Pausar
          </button>
        )}
        <button className={btnCls} disabled={!canRun || running} onClick={props.onSnapshot}>
          📸 Snapshot
        </button>
        {error && <span className="text-xs text-nok ml-2 truncate">⚠ {error}</span>}
        <label className="ml-auto flex items-center gap-1.5 text-[11px] text-muted shrink-0" title="Resolução de captura — defina antes de Iniciar; o preview já reflete">
          <span>Resolução</span>
          <select
            className="bg-edge border border-edge rounded-card px-2 py-1 text-text"
            value={captureWidth}
            onChange={(e) => setCaptureWidth(Number(e.target.value))}
          >
            {CAPTURE_PRESETS.map((p) => (
              <option key={p.w} value={p.w}>{p.label}</option>
            ))}
          </select>
        </label>
      </div>

      <HealthBar />
    </div>
  );
}
