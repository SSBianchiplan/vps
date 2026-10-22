import { useCallback, useEffect, useRef, useState } from "react";
import { labelCls } from "../../lib/ui";
import { StreamPanel } from "../StreamPanel";

// ── Modo A: USB Webcam (UVC) — getUserMedia direto, latência mínima, sem servidor ──
function UsbMode() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [deviceId, setDeviceId] = useState<string>("");
  const [err, setErr] = useState<string | null>(null);

  const start = useCallback(async (id: string) => {
    setErr(null);
    streamRef.current?.getTracks().forEach((t) => t.stop());
    try {
      const s = await navigator.mediaDevices.getUserMedia({
        video: { deviceId: id ? { exact: id } : undefined, width: 1920, height: 1080, frameRate: 30 },
        audio: false,
      });
      streamRef.current = s;
      if (videoRef.current) { videoRef.current.srcObject = s; videoRef.current.play().catch(() => undefined); }
      setDeviceId(s.getVideoTracks()[0]?.getSettings().deviceId || id);
    } catch (e) { setErr(`Falha ao abrir a câmera: ${(e as Error)?.name ?? e}`); }
  }, []);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        // 1 abertura: permissão + stream da câmera padrão de uma vez (evita abrir 2×).
        const s = await navigator.mediaDevices.getUserMedia({ video: { width: 1920, height: 1080, frameRate: 30 }, audio: false });
        if (!alive) { s.getTracks().forEach((t) => t.stop()); return; }
        const list = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === "videoinput");
        setDevices(list);
        const cur = s.getVideoTracks()[0]?.getSettings().deviceId || "";
        const osmo = list.find((c) => /osmo|pocket/i.test(c.label));
        if (osmo && osmo.deviceId !== cur) { s.getTracks().forEach((t) => t.stop()); start(osmo.deviceId); }
        else { streamRef.current = s; if (videoRef.current) { videoRef.current.srcObject = s; videoRef.current.play().catch(() => undefined); } setDeviceId(cur); }
      } catch (e) {
        setErr(window.isSecureContext === false
          ? "Câmera exige contexto seguro (https/localhost)."
          : `Permissão de câmera negada (${(e as Error)?.name ?? e}).`);
      }
    })();
    return () => { alive = false; streamRef.current?.getTracks().forEach((t) => t.stop()); };
  }, [start]);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2 flex-wrap">
        <label className={labelCls + " !mb-0"}>Dispositivo UVC</label>
        <select className="bg-edge border border-edge rounded-card px-2 py-1 text-sm text-text max-w-xs"
          value={deviceId} onChange={(e) => start(e.target.value)}>
          {devices.length === 0 && <option value="">(nenhuma câmera)</option>}
          {devices.map((d, i) => <option key={d.deviceId} value={d.deviceId}>{d.label || `Câmera ${i + 1}`}</option>)}
        </select>
        <span className="text-[11px] text-muted ml-auto">latência ~30–100 ms (cabo)</span>
      </div>
      <div className="relative bg-black rounded-card overflow-hidden flex items-center justify-center min-h-[50vh]">
        <video ref={videoRef} className="w-full h-full object-contain" autoPlay muted playsInline />
        {err && <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-muted text-sm px-4 text-center">
          <span className="text-4xl">📷</span>{err}
        </div>}
      </div>
      <p className="text-[11px] text-muted">
        Conecte o Osmo Pocket por <b>USB-C de dados</b> e selecione <b>Webcam</b> na câmera. Aparece aqui como UVC — plug-and-play, sem servidor.
      </p>
    </div>
  );
}

export function OsmoView() {
  const [mode, setMode] = useState<"usb" | "rtmp">("rtmp");
  const tabs = (
    <div className="flex gap-0.5 bg-edge rounded-card p-0.5">
      {([["usb", "🔌 USB (UVC)"], ["rtmp", "📡 RTMP (Mimo)"]] as const).map(([k, l]) => (
        <button key={k} onClick={() => setMode(k)}
          className={"px-3 py-1 text-sm rounded-card transition-colors " + (mode === k ? "bg-accent text-onaccent font-semibold" : "text-muted hover:text-text")}>{l}</button>
      ))}
    </div>
  );

  if (mode === "rtmp") {
    return (
      <StreamPanel
        path="osmo_pocket"
        icon="📷"
        title="Vídeo Osmo"
        subtitle="DJI Osmo Pocket 3/4 · RTMP → MediaMTX → WebRTC"
        offlineHint="offline — inicie o RTMP no DJI Mimo (ver instruções →)"
        testLabel="Testar sem câmera"
        opTitle="Operação (DJI Mimo)"
        rtmpLabel="RTMP (cole no DJI Mimo)"
        latencyText="latência ~1–3 s (Mimo)"
        headerExtra={tabs}
        steps={<>
          <li>Conecte o Pocket ao <b>DJI Mimo</b> (WiFi do Pocket).</li>
          <li>Menu inferior → <b>LIVESTREAM</b> → <b>RTMP</b>.</li>
          <li>Informe a <b>WiFi</b> que a câmera usará — a <b>mesma do Mac</b> (roteador local).</li>
          <li>Cole a URL RTMP abaixo; <b>1080p</b> → iniciar (~15 s).</li>
          <li>Badge fica <b className="text-nok">● AO VIVO</b> → o player conecta sozinho.</li>
        </>}
        hostNote={<p className="text-[10px] text-muted">⚠ A <b>câmera</b> empurra o RTMP pela WiFi escolhida → use o <b>IP da LAN</b> do Mac e coloque a câmera na <b>mesma WiFi</b>. Tailscale não vale aqui (a câmera não está na VPN). Remoto: IP público + port-forward 1935.</p>}
        footerNote={<>
          Osmo Pocket via Mimo. <b>USB (UVC)</b> é a opção de menor latência quando o sistema é local. Gravação <b>re-encodada em CFR</b> (alta qualidade) → reprodução fluida. Para fluidez na transmissão, prefira <b>720p/2–3 Mbps</b> se o WiFi for marginal.
        </>}
      />
    );
  }

  return (
    <div className="flex flex-col gap-4 min-h-full">
      <div className="flex items-center gap-3 flex-wrap">
        <h2 className="text-lg font-bold">📷 Vídeo Osmo</h2>
        {tabs}
        <span className="text-xs text-muted">DJI Osmo Pocket 3/4 · webcam direta (UVC)</span>
      </div>
      <UsbMode />
    </div>
  );
}
