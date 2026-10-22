import { useEffect, useRef, useState } from "react";
import { decodeQr } from "../api/cameras";
import { btnCls, btnPrimaryCls } from "../lib/ui";

export interface CamQr {
  raw: string; name?: string; ip?: string; port?: number; path?: string; username?: string; password?: string; url?: string;
  provider?: string; serial?: string; shareKey?: string; cloud?: boolean;
}

function parseUrl(s: string): Partial<CamQr> | null {
  const m = s.match(/^(rtsps?|https?):\/\/(?:([^:@/]+)(?::([^@/]+))?@)?([^:/?#]+)(?::(\d+))?(\/[^?#\s]*)?/i);
  if (!m) return null;
  return { username: m[2] || undefined, password: m[3] || undefined, ip: m[4], port: m[5] ? Number(m[5]) : undefined, path: m[6] || undefined };
}

// Aceita: URL rtsp/http, JSON, "VISIONDESK|CAM|k=v|…", pares k=v, ip ou ip:porta.
export function parseCameraQr(raw: string): CamQr | null {
  const t = (raw || "").trim();
  if (!t) return null;

  // XMEye / ICSee / Xiongmai — QR de NUVEM (P2P): contém shareKey/serial, NÃO um IP.
  if (/xmeye|icsee|xiongmai|sharekey=|\/csee|\/bcup|p2p/i.test(t)) {
    let shareKey: string | undefined, serial: string | undefined;
    try {
      const u = new URL(t);
      shareKey = u.searchParams.get("shareKey") || undefined;
      serial = u.searchParams.get("id") || u.searchParams.get("sn") || u.searchParams.get("serial") || u.searchParams.get("devId") || undefined;
    } catch { /* não é URL */ }
    if (!shareKey) shareKey = t.match(/sharekey=([\w-]+)/i)?.[1] || t.match(/\b(sa_[0-9a-f]{8,})\b/i)?.[1];
    if (!serial) serial = t.match(/\b(?:sn|id|serial)[=:]([0-9a-z]{6,})\b/i)?.[1];
    return { raw: t, provider: "xmeye", cloud: true, shareKey, serial, name: "Câmera XMEye/ICSee", port: 554, path: "/onvif1" };
  }

  const fromObj = (o: Record<string, unknown>): CamQr => {
    const g = (...k: string[]) => { for (const x of k) if (o[x] != null && o[x] !== "") return String(o[x]); return undefined; };
    const url = g("url", "rtsp", "uri", "stream_url");
    let p: CamQr = {
      raw: t, name: g("name", "title", "nome"), username: g("username", "user", "usuario", "login"),
      password: g("password", "pass", "senha", "pwd"), ip: g("ip", "host", "address", "endereco"),
      port: g("port", "porta") ? Number(g("port", "porta")) : undefined, path: g("path", "stream", "caminho"), url,
    };
    if (url && !p.ip) { const u = parseUrl(url); if (u) p = { ...p, ...u, url, raw: t }; }
    return p;
  };
  if (t.startsWith("{")) { try { return fromObj(JSON.parse(t) as Record<string, unknown>); } catch { /* not json */ } }
  if (/[=|]/.test(t) && /(ip|host|url|rtsp|user|pass|senha|port)/i.test(t)) {
    const o: Record<string, string> = {};
    t.replace(/^VISIONDESK\|?(CAM\|?)?/i, "").split(/[|;\n,]+/).forEach((kv) => { const i = kv.indexOf("="); if (i > 0) o[kv.slice(0, i).trim().toLowerCase()] = kv.slice(i + 1).trim(); });
    if (Object.keys(o).length) return fromObj(o);
  }
  const u = parseUrl(t);
  if (u) return { raw: t, url: t, ...u };
  const m = t.match(/^(\d{1,3}(?:\.\d{1,3}){3})(?::(\d+))?$/);
  if (m) return { raw: t, ip: m[1], port: m[2] ? Number(m[2]) : undefined };
  // QR só com serial/Cloud ID (Xiongmai/XMEye)
  if (/^[0-9a-f]{12,20}$/i.test(t) || /^[0-9]{9,16}$/.test(t)) return { raw: t, provider: "xmeye", cloud: true, serial: t, port: 554, path: "/onvif1" };
  return null;
}

export function CameraQrScanner({ onClose, onResult }: { onClose: () => void; onResult: (c: CamQr) => void }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const detRef = useRef<{ detect: (s: CanvasImageSource) => Promise<{ rawValue: string }[]> } | null>(null);
  const stopRef = useRef(false);
  const [err, setErr] = useState("");
  const [found, setFound] = useState<CamQr | null>(null);
  const [badRaw, setBadRaw] = useState("");
  const [manual, setManual] = useState("");

  useEffect(() => {
    stopRef.current = false;
    let stream: MediaStream | null = null;
    type BD = { new (o: { formats: string[] }): { detect: (s: CanvasImageSource) => Promise<{ rawValue: string }[]> } };
    const BDc = (window as unknown as { BarcodeDetector?: BD }).BarcodeDetector;
    if (BDc) { try { detRef.current = new BDc({ formats: ["qr_code"] }); } catch { detRef.current = null; } }

    const handle = (text: string) => {
      if (stopRef.current) return;
      const p = parseCameraQr(text);
      if (p && (p.ip || p.url || p.cloud || p.serial || p.shareKey)) { stopRef.current = true; setFound(p); }
      else setBadRaw(text);
    };
    const tick = async () => {
      const v = videoRef.current;
      if (stopRef.current || !v || !v.videoWidth) return;
      if (detRef.current) {
        try { const codes = await detRef.current.detect(v); if (codes[0]?.rawValue) return handle(codes[0].rawValue); } catch { /* ignore */ }
      } else {
        const c = document.createElement("canvas"); c.width = v.videoWidth; c.height = v.videoHeight;
        c.getContext("2d")?.drawImage(v, 0, 0);
        try { const r = await decodeQr(c.toDataURL("image/jpeg", 0.7)); if (r.text) return handle(r.text); } catch { /* ignore */ }
      }
    };

    (async () => {
      if (!navigator.mediaDevices?.getUserMedia) { setErr("Navegador sem suporte a câmera."); return; }
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" } }, audio: false });
        if (videoRef.current) { videoRef.current.srcObject = stream; await videoRef.current.play().catch(() => undefined); }
      } catch { setErr("Permita o acesso à câmera para escanear."); }
    })();
    const id = window.setInterval(tick, 650);
    return () => { stopRef.current = true; window.clearInterval(id); stream?.getTracks().forEach((t) => t.stop()); };
  }, []);

  const useManual = () => { const p = parseCameraQr(manual); if (p && (p.ip || p.url || p.cloud || p.serial || p.shareKey)) setFound(p); else setBadRaw(manual || "—"); };

  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center p-4 bg-black/60" onClick={onClose}>
      <div className="vd-surface border border-edge rounded-card w-full max-w-md p-4 space-y-3" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2"><h3 className="font-bold">📷 Configurar câmera IP por QR</h3><button className="ml-auto text-muted hover:text-text" onClick={onClose}>✕</button></div>

        {!found ? (
          <>
            <div className="aspect-video w-full rounded-card overflow-hidden bg-black grid place-items-center relative">
              <video ref={videoRef} muted playsInline className="w-full h-full object-cover" />
              <div className="absolute inset-8 border-2 border-accent/70 rounded-lg pointer-events-none" />
            </div>
            {err && <p className="text-xs text-nok">{err}</p>}
            {badRaw && <p className="text-xs text-warn">QR lido mas sem dados de câmera: <span className="font-mono">{badRaw.slice(0, 48)}</span></p>}
            <p className="text-[11px] text-muted">Aponte p/ o QR da câmera (RTSP/ONVIF). Aceita URL rtsp, JSON, <span className="font-mono">VISIONDESK|CAM|…</span> ou <span className="font-mono">ip:porta</span>. {detRef.current ? "" : "Decodificação no servidor (cv2)."}</p>
            <details className="text-xs">
              <summary className="cursor-pointer text-muted">colar conteúdo manualmente</summary>
              <textarea className="w-full mt-2 bg-edge border border-edge rounded px-2 py-1.5 text-xs font-mono" rows={2} value={manual} onChange={(e) => setManual(e.target.value)} placeholder="rtsp://USUARIO:SENHA@192.168.1.64:554/onvif1" />
              <button className={btnCls + " mt-1"} onClick={useManual}>usar texto</button>
            </details>
          </>
        ) : (
          <>
            <div className="rounded-card border border-ok/40 bg-ok/5 p-3 text-sm space-y-1">
              <div className="text-ok font-semibold text-xs">✓ QR de câmera lido{found.provider ? ` · ${found.provider.toUpperCase()}` : ""}</div>
              {[["Nome", found.name], ["Provedor", found.provider], ["Serial/Cloud", found.serial], ["ShareKey", found.shareKey], ["IP", found.ip], ["Porta", found.port], ["Caminho", found.path], ["Usuário", found.username], ["Senha", found.password ? "••••••" : undefined]].filter(([, v]) => v != null && v !== "").map(([k, v]) => (
                <div key={k} className="flex gap-2 text-xs"><span className="text-muted w-20 shrink-0">{k}</span><span className="font-mono text-text truncate">{String(v)}</span></div>
              ))}
              {found.url && <div className="text-[10px] text-muted font-mono break-all pt-1 border-t border-edge/50">{found.url}</div>}
              {found.cloud && !found.ip && (
                <div className="text-[11px] text-accent bg-accent/10 border border-accent/30 rounded px-2 py-1 mt-1">
                  Câmera de <b>nuvem XMEye/ICSee</b>. O <b>QR já libera o acesso</b>: será registrada sem IP e o sistema <b>localiza a câmera na rede local</b> (RTSP/ONVIF, porta 554 <span className="font-mono">/onvif1</span>) automaticamente.
                </div>
              )}
            </div>
            <div className="flex gap-2">
              <button className={btnPrimaryCls + " flex-1"} onClick={() => { onResult(found); onClose(); }}>{found.cloud && !found.ip ? "✓ Conectar pelo QR" : "Usar no formulário"}</button>
              <button className={btnCls} onClick={() => { setFound(null); stopRef.current = false; }}>Reler</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
