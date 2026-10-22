import { useCallback, useEffect, useRef, useState } from "react";
import { useStore } from "../store/useStore";

export interface CameraDevice {
  deviceId: string;
  label: string;
}

function describeError(e: unknown): string {
  const name = (e as { name?: string })?.name ?? "";
  switch (name) {
    case "NotAllowedError":
    case "SecurityError":
      return "Permissão de câmera negada. Libere no navegador (ícone de câmera na barra de endereço) e no macOS: Ajustes do Sistema → Privacidade e Segurança → Câmera → habilite o navegador.";
    case "NotFoundError":
    case "OverconstrainedError":
      return "Nenhuma câmera encontrada. Conecte uma câmera (ou o iPhone via Continuity Camera) e tente novamente.";
    case "NotReadableError":
    case "TrackStartError":
      return "A câmera está em uso por outro aplicativo. Feche-o (Zoom, FaceTime, Photo Booth…) e tente de novo.";
    default:
      return `Falha ao acessar a câmera${name ? ` (${name})` : ""}. Verifique as permissões.`;
  }
}

/**
 * Captura via getUserMedia. Cobre câmera do MacBook e o iPhone via Continuity
 * Camera (que aparece como um device comum no enumerateDevices do macOS).
 */
export function useCamera() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [devices, setDevices] = useState<CameraDevice[]>([]);
  const [deviceId, setDeviceId] = useState<string | null>(null);
  const [active, setActive] = useState(false);
  const [isScreen, setIsScreen] = useState(false);  // fonte atual = captura de tela
  const [error, setError] = useState<string | null>(null);

  const supported = typeof navigator !== "undefined" && !!navigator.mediaDevices?.getUserMedia;

  const refreshDevices = useCallback(async () => {
    if (!navigator.mediaDevices?.enumerateDevices) return;
    try {
      const list = await navigator.mediaDevices.enumerateDevices();
      const cams = list
        .filter((d) => d.kind === "videoinput" && d.deviceId)
        .map((d, i) => ({ deviceId: d.deviceId, label: d.label || `Câmera ${i + 1}` }));
      setDevices(cams);
    } catch {
      /* enumerateDevices pode falhar antes da permissão; ignora */
    }
  }, []);

  const attach = useCallback(async (stream: MediaStream, requestedId?: string | null, screen = false) => {
    streamRef.current = stream;
    if (videoRef.current) {
      videoRef.current.srcObject = stream;
      await videoRef.current.play().catch(() => undefined);
    }
    const realId = screen ? "screen" : (stream.getVideoTracks()[0]?.getSettings().deviceId ?? requestedId ?? null);
    setDeviceId(realId);
    setActive(true);
    useStore.getState().setActiveStream(stream, realId); // compartilha p/ cards (Painel/Câmeras)
    if (!screen) await refreshDevices(); // após a permissão, os labels passam a vir preenchidos
  }, [refreshDevices]);

  const start = useCallback(
    async (id?: string | null) => {
      setError(null);
      setIsScreen(false);

      if (!supported) {
        setActive(false);
        setError(
          window.isSecureContext === false
            ? "Acesso à câmera exige um contexto seguro. Abra a app por http://localhost:7777 (não por IP de rede) ou via HTTPS."
            : "Este navegador não expõe a API de câmera (getUserMedia).",
        );
        return;
      }

      // Encerra qualquer stream anterior antes de abrir outro.
      streamRef.current?.getTracks().forEach((t) => t.stop());
      streamRef.current = null;

      try {
        let stream: MediaStream;
        try {
          // Constraint específica quando há device escolhido; senão, a câmera padrão.
          stream = await navigator.mediaDevices.getUserMedia({
            video: id ? { deviceId: { exact: id } } : true,
            audio: false,
          });
        } catch (inner) {
          // Fallback: se a constraint exata falhar (device sumiu/ocupado),
          // tenta a câmera padrão do sistema antes de desistir.
          if (id) {
            stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
          } else {
            throw inner;
          }
        }
        await attach(stream, id);
      } catch (e) {
        setActive(false);
        setError(describeError(e));
      }
    },
    [supported, attach],
  );

  const stop = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setActive(false);
    setIsScreen(false);
    useStore.getState().setActiveStream(null, null);
  }, []);

  /**
   * Captura de TELA (a tela como câmera) via getDisplayMedia — display, janela ou
   * aba. Anexa ao mesmo videoRef/activeStream do device, então todo o pipeline
   * (LER/CONTAR/DETECTAR/DESCREVER/ANALISAR) roda igual, com sourceId="screen".
   */
  const startScreen = useCallback(async () => {
    setError(null);
    const md = navigator.mediaDevices as MediaDevices & {
      getDisplayMedia?: (c: DisplayMediaStreamOptions) => Promise<MediaStream>;
    };
    if (!md?.getDisplayMedia) {
      setActive(false);
      setError(window.isSecureContext === false
        ? "Captura de tela exige contexto seguro. Abra por https://localhost:7777 ou HTTPS."
        : "Este navegador não suporta captura de tela (getDisplayMedia).");
      return;
    }
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    try {
      const stream = await md.getDisplayMedia({ video: { frameRate: 8 }, audio: false });
      setIsScreen(true);
      const st = useStore.getState();
      st.setSourceMode("device");           // a tela alimenta o pipeline de device
      st.setSourceId("screen");
      // usuário encerrou o compartilhamento pela UI do navegador → para tudo
      stream.getVideoTracks()[0]?.addEventListener("ended", () => stop());
      await attach(stream, "screen", true);
      // registra a tela como DISPOSITIVO (aparece no Painel/Câmeras como tile)
      st.addLocalCamera({ id: "dev:screen", name: "🖥 Tela (captura)", deviceId: "screen", platform: "screen" });
    } catch (e) {
      setActive(false); setIsScreen(false);
      const name = (e as { name?: string })?.name ?? "";
      setError(name === "NotAllowedError"
        ? "Captura de tela cancelada/negada. Clique em 🖥 Tela e escolha o que compartilhar."
        : `Falha ao capturar a tela${name ? ` (${name})` : ""}.`);
    }
  }, [attach, stop]);

  useEffect(() => {
    if (!supported) {
      setError(
        window.isSecureContext === false
          ? "Acesso à câmera exige contexto seguro. Use http://localhost:7777 (não IP) ou HTTPS."
          : "Este navegador não expõe a API de câmera (getUserMedia).",
      );
      return;
    }
    void refreshDevices();
    // Atualiza a lista quando uma câmera é conectada/desconectada (ex.: iPhone).
    navigator.mediaDevices.addEventListener?.("devicechange", refreshDevices);
    return () => {
      navigator.mediaDevices.removeEventListener?.("devicechange", refreshDevices);
      stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [supported]);

  return { videoRef, devices, deviceId, active, isScreen, error, supported, start, startScreen, stop, setDeviceId, refreshDevices };
}
