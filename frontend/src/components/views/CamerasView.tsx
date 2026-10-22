import { useEffect, useState } from "react";
import { useStore } from "../../store/useStore";
import {
  addSavedCamera,
  deleteSavedCamera,
  listSavedCameras,
  resolveSavedCamera,
  type SavedCamera,
} from "../../api/cameras";
import { CameraCard } from "../CameraCard";
import { LocalCameraCard } from "../LocalCameraCard";
import { DeviceSourceConfig } from "../DeviceSourceConfig";
import { CameraQrScanner, type CamQr } from "../CameraQrScanner";
import type { CameraDevice } from "../../hooks/useCamera";
import { btnPrimaryCls, inputCls, labelCls } from "../../lib/ui";

interface Props {
  devices?: CameraDevice[];
  deviceId?: string | null;
  active?: boolean;
  error?: string | null;
  onCameraStart?: (id?: string | null) => void;
  onCameraStop?: () => void;
  onSelectDevice?: (id: string) => void;
  onScreenCapture?: () => void;
}

export function CamerasView(props: Props = {}) {
  const saved = useStore((s) => s.savedCameras);
  const setSaved = useStore((s) => s.setSavedCameras);
  const localCams = useStore((s) => s.localCameras);
  const removeLocalCamera = useStore((s) => s.removeLocalCamera);
  const setScanOpen = useStore((s) => s.setScanOpen);
  const setSelectedCameraId = useStore((s) => s.setSelectedCameraId);
  const setDetailCameraId = useStore((s) => s.setDetailCameraId);

  const [form, setForm] = useState({ name: "", ip: "", port: "554", path: "/onvif1", username: "", password: "", serial: "", provider: "", share_key: "" });
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [qrOpen, setQrOpen] = useState(false);
  const [qrMsg, setQrMsg] = useState("");

  // Câmera de nuvem (XMEye/ICSee): o QR já libera o acesso — registra sem IP e localiza na LAN.
  const addCloudFromQr = async (c: CamQr) => {
    setError(null); setQrMsg("Registrando câmera pelo QR…");
    try {
      const cam = await addSavedCamera({
        name: c.name || "Câmera XMEye/ICSee", ip: "", port: c.port || 554, path: c.path || "/onvif1",
        username: c.username, password: c.password, serial: c.serial, provider: c.provider || "xmeye", share_key: c.shareKey,
      });
      await refresh();
      setQrMsg("✓ Câmera liberada pelo QR. Localizando na rede…");
      const r = await resolveSavedCamera(cam.id).catch(() => null);
      await refresh();
      setQrMsg(r?.found
        ? `✓ Conectada — IP ${r.camera.ip} localizado na rede.`
        : "✓ Liberada pelo QR. Sem resposta na LAN agora — use 📡 localizar quando estiver na mesma rede da câmera.");
    } catch (e) { setError(String((e as Error)?.message ?? e)); setQrMsg(""); }
    window.setTimeout(() => setQrMsg(""), 7000);
  };

  const locate = async (id: string) => {
    setQrMsg("📡 Localizando câmera na rede…");
    const r = await resolveSavedCamera(id).catch(() => null);
    await refresh();
    setQrMsg(r?.found ? `✓ IP ${r.camera.ip} vinculado.` : "Não localizei na LAN — verifique se está na mesma rede.");
    window.setTimeout(() => setQrMsg(""), 6000);
  };

  const applyQr = (c: CamQr) => {
    if (c.cloud && !c.ip) { void addCloudFromQr(c); return; }
    setForm((f) => ({
      ...f,
      name: c.name || f.name, ip: c.ip || f.ip,
      port: c.port ? String(c.port) : f.port, path: c.path || f.path,
      username: c.username || f.username, password: c.password || f.password,
      serial: c.serial || f.serial, provider: c.provider || f.provider, share_key: c.shareKey || f.share_key,
    }));
    setError(null);
    setQrMsg(`QR aplicado${c.ip ? ` · ${c.ip}` : ""} — confira e salve.`);
    window.setTimeout(() => setQrMsg(""), 5000);
  };

  const refresh = () => listSavedCameras().then(setSaved).catch(() => undefined);
  useEffect(() => { refresh(); /* eslint-disable-next-line */ }, []);

  const open = (cam: SavedCamera) => setDetailCameraId(cam.id);

  const add = async () => {
    setError(null);
    if (!form.ip.trim()) {
      setError(form.provider
        ? `Câmera ${form.provider.toUpperCase()} (nuvem P2P): o VisionDesk transmite via RTSP/ONVIF na rede local — informe o IP local da câmera (use 🔍 Escanear rede).`
        : "Informe o IP da câmera");
      return;
    }
    setAdding(true);
    try {
      await addSavedCamera({
        name: form.name.trim() || `Câmera ${form.ip}`,
        ip: form.ip.trim(),
        port: Number(form.port) || 554,
        path: form.path.trim() || "/onvif1",
        username: form.username.trim() || undefined,
        password: form.password || undefined,
        serial: form.serial.trim() || undefined,
        provider: form.provider.trim() || undefined,
        share_key: form.share_key.trim() || undefined,
      });
      setForm({ name: "", ip: "", port: "554", path: "/onvif1", username: "", password: "", serial: "", provider: "", share_key: "" });
      await refresh();
    } catch (e) {
      setError(String((e as Error)?.message ?? e));
    } finally {
      setAdding(false);
    }
  };

  return (
    <div className="flex flex-col gap-4 min-h-full">
      <div className="flex items-center gap-3 flex-wrap">
        <h2 className="text-lg font-bold">Câmeras</h2>
        <span className="text-xs text-muted">{saved.length} salva(s){localCams.length ? ` · ${localCams.length} local` : ""}</span>
        <button className={btnPrimaryCls + " ml-auto"} onClick={() => setScanOpen(true)}>
          🔍 Escanear rede
        </button>
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-4">
        {/* Lista de câmeras */}
        <div className="scroll-thin pr-1">
          {saved.length === 0 && localCams.length === 0 ? (
            <div className="h-full min-h-[240px] flex flex-col items-center justify-center gap-3 border border-dashed border-edge rounded-card text-center">
              <span className="text-4xl">📷</span>
              <p className="text-muted text-sm max-w-xs">
                Nenhuma câmera. Escaneie a rede, cadastre uma IP ao lado, ou conecte um
                dispositivo local (MacBook/USB/OBS) em “Dispositivo local”.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {localCams.map((c) => (
                <div key={c.id} className="space-y-1.5">
                  <LocalCameraCard cam={c} onRemove={removeLocalCamera} />
                  <div className="flex items-center gap-2 px-0.5">
                    <span className="text-xs text-muted truncate flex-1" title={c.deviceId}>📷 local · {c.platform}</span>
                    <button className="text-xs text-muted hover:text-nok" onClick={() => removeLocalCamera(c.id)}>remover</button>
                  </div>
                </div>
              ))}
              {saved.map((cam) => (
                <div key={cam.id} className="space-y-1.5">
                  {cam.cloud ? (
                    <div className="rounded-card border border-dashed border-accent/50 bg-accent/5 p-3 min-h-[150px] flex flex-col items-center justify-center gap-1.5 text-center">
                      <span className="text-3xl">☁️📷</span>
                      <div className="text-sm font-medium text-text">{cam.name}</div>
                      <div className="text-[11px] text-muted font-mono">{(cam.provider || "nuvem").toUpperCase()}{cam.serial ? ` · ${cam.serial}` : ""}</div>
                      <div className="text-[10px] text-warn">liberada pelo QR · localizar IP na LAN</div>
                      <button className="text-xs px-2.5 py-1 rounded-card border border-accent text-accent hover:bg-accent/10 mt-1" onClick={() => locate(cam.id)}>📡 localizar na rede</button>
                    </div>
                  ) : (
                    <CameraCard camera={cam} live onOpen={open} />
                  )}
                  <div className="flex items-center gap-2 px-0.5">
                    <span className="text-xs text-muted font-mono truncate flex-1" title={cam.url}>
                      {cam.cloud ? (cam.provider || "nuvem") : `${cam.ip}:${cam.port}`}
                      {cam.has_password && " · 🔒"}
                    </span>
                    {!cam.cloud && <button className="text-xs text-accent hover:underline" onClick={() => open(cam)}>abrir</button>}
                    <button
                      className="text-xs text-muted hover:text-nok"
                      onClick={async () => {
                        await deleteSavedCamera(cam.id);
                        if (useStore.getState().selectedCameraId === cam.id) setSelectedCameraId(null);
                        await refresh();
                      }}
                    >
                      excluir
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Dispositivos locais + cadastro IP */}
        <aside className="bg-panel rounded-card border border-edge p-4 overflow-y-auto scroll-thin space-y-4">
          {props.onCameraStart && (
            <section>
              <h3 className="text-xs uppercase tracking-wider text-muted mb-3">Dispositivo local (captura)</h3>
              <DeviceSourceConfig
                devices={props.devices ?? []}
                deviceId={props.deviceId ?? null}
                active={props.active ?? false}
                error={props.error ?? null}
                onStart={props.onCameraStart}
                onStop={props.onCameraStop ?? (() => undefined)}
                onSelectDevice={props.onSelectDevice ?? (() => undefined)}
              />
              <p className="text-[11px] text-muted mt-2">
                MacBook · iPhone · Windows · Android · USB · USB-C · OBS. A seleção vale também no <b className="text-text">Estúdio</b> (mesma fonte).
              </p>
            </section>
          )}

          {props.onScreenCapture && (
            <section>
              <h3 className="text-xs uppercase tracking-wider text-muted mb-2">🖥 Câmera de tela</h3>
              <button className={btnPrimaryCls + " w-full"} onClick={() => props.onScreenCapture?.()}>
                🖥 Capturar tela (como câmera)
              </button>
              <p className="text-[11px] text-muted mt-2">
                Lê a interface de software (ERP/SCADA/HMI/dashboard) como câmera — entra como dispositivo e
                alimenta os modos de IA no <b className="text-text">Estúdio</b>. Eventos com fonte <b>screen</b>.
              </p>
            </section>
          )}

          <section>
          <div className="flex items-center gap-2 mb-3">
            <h3 className="text-xs uppercase tracking-wider text-muted flex-1">Adicionar câmera IP</h3>
            <button className={btnPrimaryCls + " text-xs py-1"} onClick={() => setQrOpen(true)}>📷 Ler QR</button>
          </div>
          {qrMsg && <p className="text-xs text-ok mb-2">{qrMsg}</p>}
          {form.provider && (
            <div className="text-[11px] mb-2 flex items-center gap-2">
              <span className="px-1.5 py-0.5 rounded-full bg-accent/15 text-accent">{form.provider.toUpperCase()}{form.serial ? ` · ${form.serial}` : ""}{form.share_key ? " · nuvem" : ""}</span>
              <button className="text-muted hover:text-nok" onClick={() => setForm((f) => ({ ...f, provider: "", serial: "", share_key: "" }))}>limpar</button>
            </div>
          )}
          <div className="space-y-2">
            <div>
              <label className={labelCls}>Nome</label>
              <input className={inputCls} value={form.name} placeholder="Ex.: Portaria"
                onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </div>
            <div className="grid grid-cols-[1fr_84px] gap-2">
              <div>
                <label className={labelCls}>IP</label>
                <input className={inputCls + " font-mono"} value={form.ip} placeholder="192.168.1.64"
                  onChange={(e) => setForm({ ...form, ip: e.target.value })} />
              </div>
              <div>
                <label className={labelCls}>Porta</label>
                <input className={inputCls + " font-mono"} value={form.port}
                  onChange={(e) => setForm({ ...form, port: e.target.value })} />
              </div>
            </div>
            <div>
              <label className={labelCls}>Caminho RTSP</label>
              <input className={inputCls + " font-mono text-xs"} value={form.path} placeholder="/onvif1"
                onChange={(e) => setForm({ ...form, path: e.target.value })} />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className={labelCls}>Usuário</label>
                <input className={inputCls} value={form.username} placeholder="admin"
                  onChange={(e) => setForm({ ...form, username: e.target.value })} />
              </div>
              <div>
                <label className={labelCls}>Senha</label>
                <input className={inputCls} type="password" value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })} />
              </div>
            </div>
            {error && <p className="text-xs text-nok">{error}</p>}
            <button className={btnPrimaryCls + " w-full"} disabled={adding} onClick={add}>
              {adding ? "Salvando…" : "💾 Salvar câmera"}
            </button>
            <p className="text-[11px] text-muted">
              A senha é guardada apenas no backend (gitignored) e nunca enviada ao navegador.
              ICSee/Xiongmai costuma usar RTSP na porta 554, caminho <span className="font-mono">/onvif1</span>.
            </p>
          </div>
          </section>
        </aside>
      </div>
      {qrOpen && <CameraQrScanner onClose={() => setQrOpen(false)} onResult={applyQr} />}
    </div>
  );
}
