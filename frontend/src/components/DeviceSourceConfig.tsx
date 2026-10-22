import type { CameraDevice } from "../hooks/useCamera";
import { useStore } from "../store/useStore";
import { btnCls, btnPrimaryCls, labelCls, selectCls } from "../lib/ui";

interface Props {
  devices: CameraDevice[];
  deviceId: string | null;
  active: boolean;
  error: string | null;
  onStart: (id?: string | null) => void;
  onStop: () => void;
  onSelectDevice: (id: string) => void;
}

const PLATFORMS = [
  ["macbook", "💻 MacBook"],
  ["iphone_continuity", "📱 iPhone (Continuity)"],
  ["windows", "🪟 Windows"],
  ["android", "🤖 Android (DroidCam/Iriun)"],
  ["usb", "🎥 Câmera USB"],
  ["usbc", "🔗 Câmera USB-C / placa de captura"],
  ["obs", "🎬 OBS (Virtual Camera)"],
  ["outros", "🔌 Outros"],
] as const;

// Auto-seleção do dispositivo pelo rótulo (USB/USB-C/OBS/Android…).
const DEVICE_KEYWORDS: Record<string, string[]> = {
  usb: ["usb", "cam link", "capture", "webcam"],
  usbc: ["usb", "usb-c", "type-c", "uvc", "capture"],
  obs: ["obs"],
  android: ["android", "droidcam", "iriun"],
  windows: ["integrated", "hd webcam"],
};

/** Configuração de dispositivo de captura local (compartilhada Estúdio ↔ Câmeras). */
export function DeviceSourceConfig(props: Props) {
  const sourceId = useStore((s) => s.sourceId);
  const setSourceId = useStore((s) => s.setSourceId);
  const setSourceMode = useStore((s) => s.setSourceMode);

  const onPlatformChange = (v: string) => {
    setSourceId(v);
    setSourceMode("device"); // ao configurar dispositivo, a fonte ativa passa a ser o device
    const kws = DEVICE_KEYWORDS[v];
    if (kws && props.devices.length) {
      const m = props.devices.find((d) => kws.some((k) => d.label.toLowerCase().includes(k)));
      if (m) { props.onSelectDevice(m.deviceId); props.onStart(m.deviceId); }
    }
  };

  const needHint = sourceId === "obs" || sourceId === "usb" || sourceId === "usbc";

  return (
    <div className="space-y-3">
      <div>
        <label className={labelCls}>Plataforma / dispositivo</label>
        <select className={selectCls} value={sourceId} onChange={(e) => onPlatformChange(e.target.value)}>
          {PLATFORMS.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
        </select>
        {needHint && (
          <p className="text-[10px] text-muted mt-1">
            {sourceId === "obs"
              ? "Inicie o OBS → “Iniciar Câmera Virtual”. Selecionamos a fonte e sincronizamos a imagem ao vivo."
              : "Conecte o dispositivo USB/USB-C; auto-selecionamos pelo nome. Se não achar, escolha na lista Câmera abaixo."}
          </p>
        )}
      </div>

      <div>
        <label className={labelCls}>Câmera</label>
        <select
          className={selectCls}
          value={props.deviceId ?? ""}
          onChange={(e) => {
            setSourceMode("device");
            props.onSelectDevice(e.target.value);
            if (props.active) props.onStart(e.target.value);
          }}
        >
          {props.devices.length === 0 && <option value="">(conceda permissão de câmera)</option>}
          {props.devices.map((d) => <option key={d.deviceId} value={d.deviceId}>{d.label}</option>)}
        </select>
      </div>

      <div className="flex gap-2">
        {!props.active ? (
          <button className={btnPrimaryCls} onClick={() => { setSourceMode("device"); props.onStart(props.deviceId); }}>
            Conectar câmera
          </button>
        ) : (
          <button className={btnCls} onClick={props.onStop}>Desconectar</button>
        )}
      </div>
      {props.error && <p className="text-xs text-nok">{props.error}</p>}
    </div>
  );
}
