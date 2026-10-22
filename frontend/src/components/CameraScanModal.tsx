import { useState } from "react";
import { scanCameras, type ScanResult } from "../api/cameras";
import { useStore } from "../store/useStore";
import { btnPrimaryCls } from "../lib/ui";

export function CameraScanModal() {
  const open = useStore((s) => s.scanOpen);
  const setScanOpen = useStore((s) => s.setScanOpen);
  const setIp = useStore((s) => s.setIp);
  const setSourceMode = useStore((s) => s.setSourceMode);

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ScanResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);

  if (!open) return null;

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      setResult(await scanCameras(3, showAll));
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  const pick = (url: string) => {
    setIp({ ipUrl: url });
    setSourceMode("ip");
    setScanOpen(false);
  };

  return (
    <div
      className="vd-modal-overlay fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={() => setScanOpen(false)}
    >
      <div
        className="vd-modal w-full max-w-2xl max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 p-4 border-b border-edge">
          <h2 className="font-bold">Escanear câmeras IP na rede</h2>
          <button className="ml-auto text-muted hover:text-text" onClick={() => setScanOpen(false)}>
            ✕
          </button>
        </div>

        <div className="p-4 flex items-center gap-3 border-b border-edge">
          <button className={btnPrimaryCls} disabled={loading} onClick={run}>
            {loading ? "Escaneando…" : "Escanear rede"}
          </button>
          <label className="flex items-center gap-1.5 text-xs text-muted">
            <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} />
            mostrar todos os hosts
          </label>
          {result && (
            <span className="text-xs text-muted ml-auto">
              rede {result.subnet ?? "?"} · {result.cameras.length} encontrada(s)
              {!result.opencv && " · ⚠ RTSP requer OpenCV"}
            </span>
          )}
        </div>

        <div className="p-4 overflow-y-auto scroll-thin space-y-3">
          {error && <p className="text-sm text-nok">{error}</p>}
          {!result && !loading && (
            <p className="text-sm text-muted">
              Clique em “Escanear rede” para procurar câmeras (ONVIF + portas RTSP/Xiongmai/Dahua).
            </p>
          )}
          {result?.cameras.length === 0 && (
            <p className="text-sm text-muted">Nenhuma câmera encontrada na sub-rede.</p>
          )}
          {result?.cameras.map((cam) => (
            <div key={cam.ip} className="border border-edge rounded p-3">
              <div className="flex items-center gap-2 mb-2">
                <span className="font-mono text-accent">{cam.ip}</span>
                {cam.onvif?.name && <span className="text-sm text-text">{cam.onvif.name}</span>}
                <span className="text-xs text-muted ml-auto">portas: {cam.ports.join(", ") || "—"}</span>
              </div>
              {cam.rtsp_candidates.length > 0 && (
                <div className="space-y-1">
                  <p className="text-xs text-muted">URLs RTSP candidatas (clique para usar):</p>
                  <div className="flex flex-col gap-1">
                    {cam.rtsp_candidates.slice(0, 6).map((url) => (
                      <button
                        key={url}
                        onClick={() => pick(url)}
                        className="text-left text-xs font-mono text-text hover:text-accent truncate"
                        title={url}
                      >
                        {url}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>

        <div className="p-3 border-t border-edge text-xs text-muted">
          Dica: muitas câmeras exigem usuário/senha — informe-os na fonte “Câmera IP”. A URL escolhida
          vira a fonte; ajuste o caminho se necessário (ICSee/Xiongmai costuma usar a porta 34567 e RTSP em 554).
        </div>
      </div>
    </div>
  );
}
