// Resolve endpoints do backend. Em dev (proxy Vite) os defaults relativos bastam.

const apiBase = (import.meta.env.VITE_API_BASE as string) || "/api";

function wsUrl(): string {
  const explicit = import.meta.env.VITE_WS_URL as string | undefined;
  if (explicit) return explicit;
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/ws/stream`;
}

// WS de presença/sinalização entre dispositivos (mesma origem → passa pelo proxy do Vite).
function devicesWsUrl(): string {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/ws/devices`;
}

export const API_BASE = apiBase;
export const WS_URL = wsUrl();
export const DEVICES_WS_URL = devicesWsUrl();
