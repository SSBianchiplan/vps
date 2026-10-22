import { useEffect, useRef, useState } from "react";
import { useCamera } from "./hooks/useCamera";
import { me, logout } from "./api/auth";
import { LoginGate } from "./components/LoginGate";
import { AccessControlView } from "./components/views/AccessControlView";
import { useDeviceMesh } from "./hooks/useDeviceMesh";
import { useStore } from "./store/useStore";
import { VisionSocket } from "./api/ws";
import { WS_URL } from "./api/config";
import { fetchCapabilities } from "./api/client";
import { snapshot as grabFrame, listSavedCameras, mtxPath } from "./api/cameras";
import { captureFrame, frameThumb, thumbDiff } from "./lib/capture";
import { CameraScanModal } from "./components/CameraScanModal";
import { CameraDetail } from "./components/CameraDetail";
import { ModuloAparencia } from "./components/ModuloAparencia";
import { NavRail } from "./components/NavRail";
import { DashboardView } from "./components/views/DashboardView";
import { MonitorView } from "./components/views/MonitorView";
import { CamerasView } from "./components/views/CamerasView";
import { ScreenCaptureView } from "./components/views/ScreenCaptureView";
import { AerialView } from "./components/views/AerialView";
import { OsmoView } from "./components/views/OsmoView";
import { DownloadsView } from "./components/views/DownloadsView";
import { VpsView } from "./components/views/VpsView";
import { MatrizView } from "./components/views/MatrizView";
import { OperadoresView } from "./components/views/OperadoresView";
import { FaceView } from "./components/views/FaceView";
import { ThermographyView } from "./components/views/ThermographyView";
import { MetrologyView } from "./components/views/MetrologyView";
import { IaMacView } from "./components/views/IaMacView";
import { AutomacaoView } from "./components/views/AutomacaoView";
import { ApsView } from "./components/views/ApsView";
import { E2eView } from "./components/views/E2eView";
import { ModaisView } from "./components/views/ModaisView";
import { PlanejamentoView } from "./components/views/PlanejamentoView";
import { StudioView } from "./components/views/StudioView";
import { EventsView } from "./components/views/EventsView";
import { ActionsView } from "./components/views/ActionsView";
import { IndustriaView } from "./components/views/IndustriaView";
import { EstudoCasoView } from "./components/views/EstudoCasoView";
import { BasesView } from "./components/views/BasesView";
import { ManualView } from "./components/views/ManualView";
import { SecurityView } from "./components/views/SecurityView";
import { AlertToasts } from "./components/AlertToasts";
import type { Mode, ServerMessage } from "./types";

const VIEW_TITLE: Record<string, string> = {
  painel: "Painel de monitoramento",
  monitor: "Monitoramento de sinal (IoT)",
  cameras: "Gerenciar câmeras",
  captura: "Captura de Tela — a tela como câmera (ler ERP/SCADA/HMI sem API)",
  automacao: "Automação Industrial — conector OT (PLC/IHM · OPC UA/visão · OEE · read-only)",
  face: "Reconhecimento Facial — identificação consentida de operador (edge · LGPD)",
  termografia: "Termografia — manutenção preditiva (hotspot · ΔT · baseline · tendência)",
  metrologia: "Metrologia — inspeção dimensional (px→mm · tolerância · Cpk · incerteza)",
  iamac: "iaMAC — IA própria + motor de aprendizado (RAG · flywheel · eval · Mac/MLX)",
  acesso: "Acesso & Regras — usuários, papéis (admin/operador/view) e login FaceID/PIN",
  seguranca: "Cibersegurança — postura NIST CSF, integridade da trilha (cadeia de hash), ameaças e conformidade (IEC 62443/ISO 27001/LGPD/OWASP)",
  aerea: "Visão Aérea — drone ao vivo (DJI Neo 2 · RTMP→MediaMTX→WebRTC)",
  osmo: "Vídeo Osmo — DJI Osmo Pocket 3/4 (USB Webcam UVC · RTMP via Mimo)",
  downloads: "Downloads — gravações .mp4 do VisionDesk",
  estudio: "Estúdio de visão — LER · CONTAR · DETECTAR · DESCREVER · ANALISAR",
  eventos: "Linha do tempo de eventos",
  acoes: "Ações (AGIR · Vision-Language-Action)",
  industria: "Indústria — modelos de visão computacional (spec_tecnologia)",
  estudocaso: "Estudo de caso — visão industrial aplicada às câmeras",
  bases: "Bases de Dados — status dos armazenamentos",
  manual: "Manual do sistema",
};

function minIntervalFor(mode: Mode): number {
  if (mode === "CONTAR" || mode === "DETECTAR" || mode === "RASTREAR") return 350;  // edge/YOLO (rápido)
  if (mode === "LER") return 1200;
  return 2500; // DESCREVER / ANALISAR (VLM sob intervalo)
}

export default function App() {
  const camera = useCamera();
  const mesh = useDeviceMesh();
  const imgRef = useRef<HTMLImageElement | null>(null);
  const socketRef = useRef<VisionSocket | null>(null);
  const inFlight = useRef(false);
  const grabbing = useRef(false);
  const lastSent = useRef(0);
  const frameSeq = useRef(0);
  const lastThumb = useRef<Uint8Array | null>(null);  // detecção de mudança (captura de tela)

  const running = useStore((s) => s.running);
  const connected = useStore((s) => s.connected);
  const statusDetail = useStore((s) => s.statusDetail);
  const view = useStore((s) => s.view);
  const auth = useStore((s) => s.auth);
  const setAuth = useStore((s) => s.setAuth);
  const [authChecked, setAuthChecked] = useState(false);

  // Sessão: valida token salvo ao abrir.
  useEffect(() => {
    me().then(setAuth).catch(() => setAuth(null)).finally(() => setAuthChecked(true));
  }, [setAuth]);

  // Conexão WS + capacidades (uma vez).
  useEffect(() => {
    fetchCapabilities()
      .then(useStore.getState().setCapabilities)
      .catch(() => useStore.getState().setError("Backend indisponível"));
    listSavedCameras().then(useStore.getState().setSavedCameras).catch(() => undefined);

    const onMessage = (msg: ServerMessage) => {
      const st = useStore.getState();
      switch (msg.type) {
        case "result":
          st.pushResult(msg.result);
          inFlight.current = false;
          break;
        case "error":
          st.setError(`${msg.code}: ${msg.message}`);
          inFlight.current = false;
          break;
        case "health":
          st.setHealth(msg);
          break;
        case "status":
          st.setStatusDetail(msg.detail);
          break;
        case "alert":
          st.pushToast({ action_type: msg.action_type, message: msg.message, rule: msg.rule });
          if (msg.action_type === "clipboard" && msg.payload != null) {
            navigator.clipboard?.writeText(
              typeof msg.payload === "string" ? msg.payload : JSON.stringify(msg.payload),
            ).catch(() => undefined);
          }
          break;
      }
    };

    const onState = (open: boolean) => {
      useStore.getState().setConnected(open);
      if (!open) inFlight.current = false;
    };
    const onOpen = () => {
      inFlight.current = false;
      if (useStore.getState().running) socketRef.current?.control("start");
    };

    const sock = new VisionSocket(WS_URL, onMessage, onState, onOpen);
    sock.connect();
    socketRef.current = sock;
    return () => sock.close();
  }, []);

  // Dispositivo local conectado → vira card de câmera (Painel/Câmeras).
  useEffect(() => {
    if (!camera.active || !camera.deviceId) return;
    if (camera.deviceId === "screen") return;  // tela é registrada no próprio hook (startScreen)
    const label = camera.devices.find((d) => d.deviceId === camera.deviceId)?.label
      || `Dispositivo (${useStore.getState().sourceId})`;
    useStore.getState().addLocalCamera({
      id: `dev:${camera.deviceId}`,
      name: label,
      deviceId: camera.deviceId,
      platform: useStore.getState().sourceId,
    });
  }, [camera.active, camera.deviceId, camera.devices]);

  // Loop de captura com backpressure (processa o frame mais recente).
  useEffect(() => {
    if (!running) return;
    const id = window.setInterval(() => {
      const st = useStore.getState();
      const sock = socketRef.current;
      const now = performance.now();

      // Cadência: captura de tela usa fps próprio (telas mudam devagar, spec §6).
      const isScreen = st.sourceMode === "device" && st.sourceId === "screen";
      const minIv = isScreen
        ? Math.max(minIntervalFor(st.mode), Math.round(1000 / (st.screenFps || 2)))
        : minIntervalFor(st.mode);

      // Watchdogs: liberam o loop se uma resposta/grab nunca chega.
      if (inFlight.current && now - lastSent.current > 3 * minIv + 6000) {
        inFlight.current = false;
      }
      if (grabbing.current && now - lastSent.current > 15000) grabbing.current = false;

      if (!sock || !st.connected || inFlight.current) return;
      if (now - lastSent.current < minIv) return;

      // Resolução efetiva: CONTAR/DETECTAR (YOLO ~640) capam em 960 → fluido/leve;
      // LER/DESCREVER/ANALISAR usam a resolução cheia escolhida → alta qualidade.
      const hifps = st.mode === "CONTAR" || st.mode === "DETECTAR" || st.mode === "RASTREAR";
      const effW = hifps ? Math.min(960, st.captureWidth || 960) : st.captureWidth;

      if (st.sourceMode === "device") {
        if (!camera.active) return;
        const video = camera.videoRef.current;
        if (!video) return;
        // Detecção de mudança (tela): só processa quando a interface muda → controla custo VLM.
        if (isScreen && st.screenChangeDetect) {
          const thumb = frameThumb(video);
          if (thumb) {
            if (lastThumb.current && thumbDiff(thumb, lastThumb.current) < 0.008) return;
            lastThumb.current = thumb;
          }
        }
        const b64 = captureFrame(video, effW || 4096);
        if (!b64) return;
        frameSeq.current += 1;
        inFlight.current = true;
        lastSent.current = now;
        sock.sendFrame(b64, frameSeq.current, st.buildTask(), st.sourceId);
      } else {
        // Câmera IP: o backend captura o frame (RTSP/HTTP) e nós o repassamos ao WS.
        const hasTarget = st.selectedCameraId || st.ipUrl;
        if (!hasTarget || grabbing.current) return;
        grabbing.current = true;
        lastSent.current = now;
        // Stream ao vivo (câmera salva / drone / osmo): preview é o MJPEG → inferência
        // usa a MESMA resolução (compartilha o stream) e NÃO toca a img exibida.
        const liveStream = !!st.selectedCameraId || !!mtxPath(st.ipUrl);
        const grabW = liveStream ? st.captureWidth : effW;
        const opts = st.selectedCameraId
          ? { cameraId: st.selectedCameraId, maxW: grabW }
          : { url: st.ipUrl, username: st.ipUser, password: st.ipPass, maxW: grabW };
        const sid = st.selectedCameraId ? `cam:${st.selectedCameraId}` : "ip_camera";
        grabFrame(opts)
          .then(({ image_b64 }) => {
            grabbing.current = false;
            if (!liveStream && imgRef.current) imgRef.current.src = `data:image/jpeg;base64,${image_b64}`;
            frameSeq.current += 1;
            inFlight.current = true;
            socketRef.current?.sendFrame(image_b64, frameSeq.current, st.buildTask(), sid);
          })
          .catch((err) => {
            grabbing.current = false;
            useStore.getState().setError(`captura IP: ${err?.message ?? err}`);
          });
      }
    }, 120);
    return () => window.clearInterval(id);
  }, [running, camera.active, camera.videoRef]);

  const start = () => {
    useStore.getState().setRunning(true);
    socketRef.current?.control("start");
  };
  const stop = () => {
    useStore.getState().setRunning(false);
    inFlight.current = false;
    grabbing.current = false;
    socketRef.current?.control("stop");
  };
  // Captura o frame atual da fonte ativa (device ou IP) → base64, p/ o TechLab.
  const captureCurrent = async (): Promise<string | null> => {
    const st = useStore.getState();
    if (st.sourceMode === "device") {
      const video = camera.videoRef.current;
      return video ? captureFrame(video, st.captureWidth || 4096) : null;
    }
    if (!st.selectedCameraId && !st.ipUrl) return null;
    const opts = st.selectedCameraId
      ? { cameraId: st.selectedCameraId, maxW: st.captureWidth }
      : { url: st.ipUrl, username: st.ipUser, password: st.ipPass, maxW: st.captureWidth };
    const liveStream = !!st.selectedCameraId || !!mtxPath(st.ipUrl);
    try {
      const { image_b64 } = await grabFrame(opts);
      if (!liveStream && imgRef.current) imgRef.current.src = `data:image/jpeg;base64,${image_b64}`;
      return image_b64;
    } catch {
      return null;
    }
  };

  const snapshot = async () => {
    const sock = socketRef.current;
    const st = useStore.getState();
    if (!sock) return;
    if (st.sourceMode === "device") {
      const video = camera.videoRef.current;
      if (!video) return;
      const b64 = captureFrame(video, st.captureWidth || 4096);
      if (!b64) return;
      frameSeq.current += 1;
      sock.sendFrame(b64, frameSeq.current, st.buildTask(), st.sourceId);
    } else {
      if (!st.selectedCameraId && !st.ipUrl) return;
      const opts = st.selectedCameraId
        ? { cameraId: st.selectedCameraId, maxW: st.captureWidth }
        : { url: st.ipUrl, username: st.ipUser, password: st.ipPass, maxW: st.captureWidth };
      const sid = st.selectedCameraId ? `cam:${st.selectedCameraId}` : "ip_camera";
      const liveStream = !!st.selectedCameraId || !!mtxPath(st.ipUrl);
      try {
        const { image_b64 } = await grabFrame(opts);
        if (!liveStream && imgRef.current) imgRef.current.src = `data:image/jpeg;base64,${image_b64}`;
        frameSeq.current += 1;
        sock.sendFrame(image_b64, frameSeq.current, st.buildTask(), sid);
      } catch (err) {
        useStore.getState().setError(`captura IP: ${(err as Error)?.message ?? err}`);
      }
    }
  };

  return (
    <div className="h-full flex">
      {authChecked && !auth && <LoginGate />}
      <NavRail />

      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="flex items-center gap-3 px-5 py-3 border-b border-edge">
          <h1 className="text-lg font-bold tracking-tight whitespace-nowrap">
            Vision<span className="text-accent">Desk</span> + <span className="text-accent">VPS</span>
            <span className="text-muted font-normal text-sm hidden lg:inline"> — Visual Planning System</span>
          </h1>
          <span className="text-xs text-muted hidden sm:inline">{VIEW_TITLE[view]}</span>
          <div className="ml-auto flex items-center gap-2 min-w-0">
            {statusDetail && <span className="text-xs text-muted truncate">{statusDetail}</span>}
            {!connected && <span className="text-xs text-warn shrink-0">⚠ conectando ao backend…</span>}
            <span className="text-[11px] font-mono text-muted px-2 py-0.5 rounded bg-edge border border-edge shrink-0"
              title="Endereço por onde você está acessando (host:porta)">🌐 {window.location.host}</span>
            {auth && (
              <span className="flex items-center gap-1.5 shrink-0">
                <span className="text-[11px] px-2 py-0.5 rounded-full bg-accent/15 text-accent" title={auth.operator_id}>
                  {auth.name} · {auth.role}
                </span>
                <button className="text-[11px] text-muted hover:text-nok" title="Sair"
                  onClick={async () => { await logout(); setAuth(null); }}>⏻ sair</button>
              </span>
            )}
          </div>
        </header>

        <main className="flex-1 p-3 sm:p-4 overflow-y-auto">
          {view === "painel" && <DashboardView mesh={mesh} camera={{ start: camera.start, stop: camera.stop, error: camera.error, active: camera.active }} />}
          {view === "monitor" && <MonitorView />}
          {view === "cameras" && (
            <CamerasView
              devices={camera.devices}
              deviceId={camera.deviceId}
              active={camera.active}
              error={camera.error}
              onCameraStart={camera.start}
              onCameraStop={camera.stop}
              onSelectDevice={camera.setDeviceId}
              onScreenCapture={camera.startScreen}
            />
          )}
          {view === "automacao" && <AutomacaoView />}
          {view === "captura" && (
            <ScreenCaptureView
              active={camera.active}
              isScreen={camera.isScreen}
              error={camera.error}
              onScreenCapture={camera.startScreen}
              onStopCapture={camera.stop}
              onRun={start}
              onPause={stop}
              onSnapshot={snapshot}
            />
          )}
          {view === "aerea" && <AerialView />}
          {view === "osmo" && <OsmoView />}
          {view === "downloads" && <DownloadsView />}
          {view === "vps" && <VpsView />}
          {view === "planejamento" && <PlanejamentoView />}
          {view === "matriz" && <MatrizView />}
          {view === "operadores" && <OperadoresView />}
          {view === "face" && <FaceView />}
          {view === "termografia" && <ThermographyView />}
          {view === "metrologia" && <MetrologyView />}
          {view === "aps" && <ApsView />}
          {view === "e2e" && <E2eView />}
          {view === "modais" && <ModaisView />}
          {view === "eventos" && <EventsView />}
          {view === "acoes" && <ActionsView />}
          {view === "industria" && <IndustriaView />}
          {view === "estudocaso" && <EstudoCasoView />}
          {view === "iamac" && <IaMacView />}
          {view === "acesso" && <AccessControlView />}
          {view === "seguranca" && <SecurityView />}
          {view === "bases" && <BasesView />}
          {view === "manual" && <ManualView />}
          {/* Estúdio fica sempre montado para preservar a captura/stream ao trocar de aba */}
          <div className={view === "estudio" ? "min-h-full lg:h-full lg:min-h-0" : "hidden"}>
            <StudioView
              devices={camera.devices}
              deviceId={camera.deviceId}
              active={camera.active}
              error={camera.error}
              videoRef={camera.videoRef}
              imgRef={imgRef}
              onCameraStart={camera.start}
              onCameraStop={camera.stop}
              onSelectDevice={camera.setDeviceId}
              onScreenCapture={camera.startScreen}
              onRun={start}
              onPause={stop}
              onSnapshot={snapshot}
              captureCurrent={captureCurrent}
            />
          </div>
        </main>
      </div>

      <CameraScanModal />
      <CameraDetail />
      <ModuloAparencia />
      <AlertToasts />
    </div>
  );
}
