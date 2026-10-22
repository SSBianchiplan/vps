import type { CameraDevice } from "../hooks/useCamera";
import { useStore } from "../store/useStore";
import { addSavedCamera, deleteSavedCamera, listSavedCameras } from "../api/cameras";
import { btnCls, btnPrimaryCls, inputCls, labelCls } from "../lib/ui";
import { DeviceSourceConfig } from "./DeviceSourceConfig";

interface Props {
  devices: CameraDevice[];
  deviceId: string | null;
  active: boolean;
  error: string | null;
  onStart: (id?: string | null) => void;
  onStop: () => void;
  onSelectDevice: (id: string) => void;
  onScreenCapture: () => void;
}

function parseRtsp(url: string): { ip: string; port: number; path: string } | null {
  try {
    const u = new URL(url);
    return {
      ip: u.hostname,
      port: u.port ? Number(u.port) : 554,
      path: (u.pathname || "/onvif1") + (u.search || ""),
    };
  } catch {
    return null;
  }
}

export function SourceSelector(props: Props) {
  const sourceMode = useStore((s) => s.sourceMode);
  const setSourceMode = useStore((s) => s.setSourceMode);
  const sourceId = useStore((s) => s.sourceId);
  const setSourceId = useStore((s) => s.setSourceId);
  const ipUrl = useStore((s) => s.ipUrl);
  const ipUser = useStore((s) => s.ipUser);
  const ipPass = useStore((s) => s.ipPass);
  const setIp = useStore((s) => s.setIp);
  const setScanOpen = useStore((s) => s.setScanOpen);
  const saved = useStore((s) => s.savedCameras);
  const setSaved = useStore((s) => s.setSavedCameras);
  const selectedCameraId = useStore((s) => s.selectedCameraId);
  const setSelectedCameraId = useStore((s) => s.setSelectedCameraId);

  const refresh = () => listSavedCameras().then(setSaved).catch(() => undefined);

  const saveCurrent = async () => {
    const parsed = parseRtsp(ipUrl);
    if (!parsed) {
      useStore.getState().setError("URL RTSP inválida para salvar");
      return;
    }
    await addSavedCamera({
      name: `Câmera ${parsed.ip}`,
      ip: parsed.ip,
      port: parsed.port,
      path: parsed.path,
      username: ipUser || undefined,
      password: ipPass || undefined,
    });
    await refresh();
  };

  const isScreen = sourceMode === "device" && sourceId === "screen";

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-2">
        <button
          onClick={() => { setSourceMode("device"); if (sourceId === "screen") setSourceId("macbook"); }}
          className={"py-1.5 rounded text-sm border transition-colors " +
            (sourceMode === "device" && !isScreen ? "bg-accent text-onaccent border-accent" : "bg-edge border-edge hover:border-accent")}>
          Dispositivo
        </button>
        <button
          onClick={() => setSourceMode("ip")}
          className={"py-1.5 rounded text-sm border transition-colors " +
            (sourceMode === "ip" ? "bg-accent text-onaccent border-accent" : "bg-edge border-edge hover:border-accent")}>
          Câmera IP
        </button>
        <button
          onClick={() => props.onScreenCapture()}
          title="Capturar a tela (display/janela/aba) como câmera"
          className={"py-1.5 rounded text-sm border transition-colors " +
            (isScreen ? "bg-accent text-onaccent border-accent" : "bg-edge border-edge hover:border-accent")}>
          🖥 Tela
        </button>
      </div>

      {isScreen ? (
        <div className="space-y-2">
          <div className="flex items-center gap-2 px-3 py-2 rounded-card border border-accent/40 bg-accent/10">
            <span className={"w-2 h-2 rounded-full " + (props.active ? "bg-ok animate-pulse" : "bg-muted")} />
            <span className="text-sm text-text flex-1">{props.active ? "Capturando a tela" : "Tela não iniciada"}</span>
          </div>
          <div className="flex gap-2">
            <button className={btnPrimaryCls} onClick={() => props.onScreenCapture()}>
              {props.active ? "🖥 Trocar tela/janela" : "🖥 Compartilhar tela"}
            </button>
            {props.active && <button className={btnCls} onClick={props.onStop}>Parar</button>}
          </div>
          <p className="text-[11px] text-muted">
            Lê a interface de software (ERP/SCADA/HMI/dashboard) como câmera — roda LER/CONTAR/DETECTAR/DESCREVER/ANALISAR
            sobre a tela. Eventos saem com fonte <b>screen</b>. Escolha display, janela ou aba ao compartilhar.
          </p>
          {props.error && <p className="text-xs text-nok">{props.error}</p>}
        </div>
      ) : sourceMode === "device" ? (
        <DeviceSourceConfig {...props} />
      ) : (
        <>
          <div>
            <label className={labelCls}>Streams ao vivo (IA)</label>
            <div className="grid grid-cols-2 gap-2">
              {[
                { label: "🛸 Drone", url: "rtsp://localhost:8554/drone_neo2" },
                { label: "📷 Osmo", url: "rtsp://localhost:8554/osmo_pocket" },
              ].map((s) => (
                <button key={s.url}
                  onClick={() => { setSelectedCameraId(null); setIp({ ipUrl: s.url }); }}
                  className={"py-1.5 rounded text-sm border transition-colors " +
                    (ipUrl === s.url ? "bg-accent/20 border-accent" : "bg-edge border-edge hover:border-accent")}>
                  {s.label}
                </button>
              ))}
            </div>
            <p className="text-[10px] text-muted mt-1">
              Roda a IA visual (LER/CONTAR/DETECTAR/DESCREVER/ANALISAR + Tecnologias) no feed do drone/osmo — precisa estar ao vivo no módulo respectivo.
            </p>
          </div>

          {saved.length > 0 && (
            <div>
              <label className={labelCls}>Câmeras salvas (1 clique)</label>
              <div className="space-y-1">
                {saved.map((c) => (
                  <div key={c.id} className="flex items-center gap-1">
                    <button
                      onClick={() => {
                        setSelectedCameraId(c.id);
                        setIp({ ipUrl: c.url });
                      }}
                      className={
                        "flex-1 text-left px-2 py-1.5 rounded text-sm border transition-colors " +
                        (selectedCameraId === c.id
                          ? "bg-accent/20 border-accent"
                          : "bg-edge border-edge hover:border-accent")
                      }
                      title={c.url}
                    >
                      {c.name}
                      {c.has_password && <span className="text-muted"> · 🔒</span>}
                    </button>
                    <button
                      className="px-2 py-1.5 text-muted hover:text-nok"
                      title="excluir"
                      onClick={async () => {
                        await deleteSavedCamera(c.id);
                        if (selectedCameraId === c.id) setSelectedCameraId(null);
                        await refresh();
                      }}
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          <button className={btnPrimaryCls + " w-full"} onClick={() => setScanOpen(true)}>
            🔍 Escanear rede
          </button>

          <div>
            <label className={labelCls}>URL RTSP/HTTP (manual)</label>
            <input
              className={inputCls + " font-mono text-xs"}
              placeholder="rtsp://192.168.1.64:554/onvif1"
              value={ipUrl}
              onChange={(e) => {
                setIp({ ipUrl: e.target.value });
                setSelectedCameraId(null); // edição manual desativa a câmera salva
              }}
            />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className={labelCls}>Usuário</label>
              <input
                className={inputCls}
                placeholder="admin"
                value={ipUser}
                onChange={(e) => setIp({ ipUser: e.target.value })}
              />
            </div>
            <div>
              <label className={labelCls}>Senha</label>
              <input
                className={inputCls}
                type="password"
                value={ipPass}
                onChange={(e) => setIp({ ipPass: e.target.value })}
              />
            </div>
          </div>
          <button className={btnCls + " w-full"} onClick={saveCurrent}>
            💾 Salvar câmera atual
          </button>
          <p className="text-xs text-muted">
            Selecione uma câmera salva (senha guardada no backend) ou informe a URL manual e clique
            em <b>Iniciar</b>. RTSP requer OpenCV no backend.
          </p>
        </>
      )}
    </div>
  );
}
