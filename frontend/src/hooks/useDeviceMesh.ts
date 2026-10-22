import { useCallback, useEffect, useRef, useState } from "react";
import { useStore } from "../store/useStore";
import { DEVICES_WS_URL } from "../api/config";
import type { RemoteCameraInfo, RemotePeer } from "../api/devices";

// STUN ajuda atrás de NAT; na mesma LAN os candidatos host/mDNS já bastam.
const ICE: RTCConfiguration = { iceServers: [{ urls: "stun:stun.l.google.com:19302" }] };

function guessDeviceName(): string {
  try {
    const saved = localStorage.getItem("vd-device-name");
    if (saved) return saved;
  } catch { /* ignore */ }
  const ua = typeof navigator !== "undefined" ? navigator.userAgent : "";
  if (/iPhone/.test(ua)) return "iPhone";
  if (/iPad/.test(ua)) return "iPad";
  if (/Android/.test(ua)) return "Android";
  if (/Macintosh|Mac OS/.test(ua)) return "Mac";
  if (/Windows/.test(ua)) return "Windows";
  return "Dispositivo";
}

function cameraInfo(): RemoteCameraInfo | null {
  const st = useStore.getState();
  const stream = st.activeStream;
  const track = stream?.getVideoTracks()[0];
  if (!stream || !track) return null;
  const s = track.getSettings();
  const label =
    track.label ||
    st.localCameras.find((c) => c.deviceId === st.activeDeviceId)?.name ||
    "Câmera";
  return { label, width: s.width, height: s.height, facing: (s as { facingMode?: string }).facingMode };
}

export interface DeviceMesh {
  myPeerId: string | null;
  online: boolean;
  deviceName: string;
  setDeviceName: (n: string) => void;
  roster: RemotePeer[]; // outros peers (sem o próprio)
  remoteStreams: Record<string, MediaStream>; // publisherId -> stream recebido
  watching: Record<string, boolean>; // publisherId -> conectando/ativo
  watch: (publisherId: string) => void;
  unwatch: (publisherId: string) => void;
}

const DEAD = ["failed", "closed", "disconnected"];

/**
 * Malha de dispositivos: cada cliente publica presença (câmera aberta) e pode
 * ASSISTIR o feed de outro via WebRTC P2P. A sinalização (SDP/ICE) vai pelo
 * WebSocket `/ws/devices`; o vídeo trafega direto entre os aparelhos.
 *
 * PCs são indexados por `session = "<viewerId>-><publisherId>"`, o que permite
 * que dois aparelhos se assistam mutuamente sem colidir conexões.
 */
export function useDeviceMesh(): DeviceMesh {
  const wsRef = useRef<WebSocket | null>(null);
  const peerIdRef = useRef<string | null>(null);
  const pcsRef = useRef<Map<string, RTCPeerConnection>>(new Map());
  const nameRef = useRef<string>(guessDeviceName());

  const [myPeerId, setMyPeerId] = useState<string | null>(null);
  const [online, setOnline] = useState(false);
  const [deviceName, setDeviceNameState] = useState<string>(nameRef.current);
  const [roster, setRoster] = useState<RemotePeer[]>([]);
  const [remoteStreams, setRemoteStreams] = useState<Record<string, MediaStream>>({});
  const [watching, setWatching] = useState<Record<string, boolean>>({});

  const activeStream = useStore((s) => s.activeStream);
  const activeDeviceId = useStore((s) => s.activeDeviceId);

  const send = useCallback((obj: unknown) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
  }, []);

  const dropViewer = useCallback((publisherId: string, session: string) => {
    const pc = pcsRef.current.get(session);
    if (pc) { pc.close(); pcsRef.current.delete(session); }
    setWatching((w) => { const n = { ...w }; delete n[publisherId]; return n; });
    setRemoteStreams((m) => { const n = { ...m }; delete n[publisherId]; return n; });
  }, []);

  // ── Sinalização recebida (papel inferido pelo tipo da mensagem) ──────────
  const handleSignal = useCallback(async (from: string, data: { session: string; kind: string; sdp?: RTCSessionDescriptionInit; candidate?: RTCIceCandidateInit }) => {
    const { session, kind } = data;
    if (kind === "offer") {
      // Somos o PUBLISHER: alguém quer nos assistir.
      const stream = useStore.getState().activeStream;
      const old = pcsRef.current.get(session);
      if (old) { old.close(); pcsRef.current.delete(session); }
      const pc = new RTCPeerConnection(ICE);
      pcsRef.current.set(session, pc);
      pc.onicecandidate = (e) => {
        if (e.candidate) send({ type: "signal", to: from, data: { session, kind: "ice", candidate: e.candidate } });
      };
      pc.onconnectionstatechange = () => {
        if (DEAD.includes(pc.connectionState)) { pc.close(); pcsRef.current.delete(session); }
      };
      stream?.getVideoTracks().forEach((t) => pc.addTrack(t, stream));
      await pc.setRemoteDescription(data.sdp!);
      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);
      send({ type: "signal", to: from, data: { session, kind: "answer", sdp: pc.localDescription } });
    } else if (kind === "answer") {
      const pc = pcsRef.current.get(session);
      if (pc) await pc.setRemoteDescription(data.sdp!).catch(() => undefined);
    } else if (kind === "ice") {
      const pc = pcsRef.current.get(session);
      if (pc && data.candidate) await pc.addIceCandidate(data.candidate).catch(() => undefined);
    }
  }, [send]);

  // ── Conexão WS (com reconexão) ───────────────────────────────────────────
  useEffect(() => {
    let alive = true;
    let reconnect: number | null = null;
    const connect = () => {
      const ws = new WebSocket(DEVICES_WS_URL);
      wsRef.current = ws;
      ws.onopen = () => {
        setOnline(true);
        send({ type: "hello", device: { name: nameRef.current, platform: useStore.getState().sourceId }, camera: cameraInfo() });
      };
      ws.onmessage = (ev) => {
        let msg: { type: string; peer_id?: string; peers?: RemotePeer[]; from?: string; data?: never };
        try { msg = JSON.parse(ev.data); } catch { return; }
        if (msg.type === "welcome" && msg.peer_id) {
          peerIdRef.current = msg.peer_id;
          setMyPeerId(msg.peer_id);
        } else if (msg.type === "roster" && msg.peers) {
          const me = peerIdRef.current;
          setRoster(msg.peers.filter((p) => p.peer_id !== me));
        } else if (msg.type === "signal" && msg.from && msg.data) {
          void handleSignal(msg.from, msg.data);
        }
      };
      ws.onclose = () => {
        setOnline(false);
        if (alive) reconnect = window.setTimeout(connect, 1500);
      };
      ws.onerror = () => ws.close();
    };
    connect();
    return () => {
      alive = false;
      if (reconnect) window.clearTimeout(reconnect);
      pcsRef.current.forEach((pc) => pc.close());
      pcsRef.current.clear();
      wsRef.current?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Publica o estado da câmera sempre que o stream compartilhado muda.
  useEffect(() => {
    send({ type: "camera", camera: cameraInfo() });
  }, [activeStream, activeDeviceId, send]);

  const setDeviceName = useCallback((n: string) => {
    const name = n.trim() || guessDeviceName();
    nameRef.current = name;
    setDeviceNameState(name);
    try { localStorage.setItem("vd-device-name", name); } catch { /* ignore */ }
    send({ type: "hello", device: { name, platform: useStore.getState().sourceId }, camera: cameraInfo() });
  }, [send]);

  // ── Viewer: assistir o feed de um publisher ──────────────────────────────
  const watch = useCallback((publisherId: string) => {
    const me = peerIdRef.current;
    if (!me) return;
    const session = `${me}->${publisherId}`;
    if (pcsRef.current.has(session)) return;
    const pc = new RTCPeerConnection(ICE);
    pcsRef.current.set(session, pc);
    setWatching((w) => ({ ...w, [publisherId]: true }));
    pc.addTransceiver("video", { direction: "recvonly" });
    pc.ontrack = (e) => setRemoteStreams((m) => ({ ...m, [publisherId]: e.streams[0] }));
    pc.onicecandidate = (e) => {
      if (e.candidate) send({ type: "signal", to: publisherId, data: { session, kind: "ice", candidate: e.candidate } });
    };
    pc.onconnectionstatechange = () => {
      if (DEAD.includes(pc.connectionState)) dropViewer(publisherId, session);
    };
    pc.createOffer()
      .then(async (offer) => {
        await pc.setLocalDescription(offer);
        send({ type: "signal", to: publisherId, data: { session, kind: "offer", sdp: pc.localDescription } });
      })
      .catch(() => dropViewer(publisherId, session));
  }, [send, dropViewer]);

  const unwatch = useCallback((publisherId: string) => {
    const me = peerIdRef.current;
    if (!me) return;
    dropViewer(publisherId, `${me}->${publisherId}`);
  }, [dropViewer]);

  return { myPeerId, online, deviceName, setDeviceName, roster, remoteStreams, watching, watch, unwatch };
}
