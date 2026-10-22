import { useCallback, useEffect, useRef, useState } from "react";
import {
  qrUrl, scanToken, stationAction, type ScanResult,
} from "../../api/vps";
import { mjpegUrl, mtxMjpegUrl } from "../../api/cameras";
import { useStore } from "../../store/useStore";

// 📷 Scanner de token reutilizável — lê o QR (modo LER) de: local · mobile · câmera IP · Osmo · drone.
// Resolve o Tag-ID → card com a OP → operador escolhe a AÇÃO → registra no Fio. Trata permissões de câmera.
export function StationScanner({ station, operatorId, onScanned, tagHint }: {
  station: string; operatorId: string | null; onScanned: () => void; tagHint?: string;
}) {
  const saved = useStore((s) => s.savedCameras);
  const [kind, setKind] = useState("local");
  const [res, setRes] = useState<ScanResult | null>(null);
  const [card, setCard] = useState<ScanResult | null>(null);
  const [action, setAction] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [auto, setAuto] = useState(false);
  const [perm, setPerm] = useState<"idle" | "granted" | "denied" | "insecure" | "error">("idle");
  const [permMsg, setPermMsg] = useState("");
  const [retry, setRetry] = useState(0);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const live = kind === "local" || kind === "mobile";

  useEffect(() => {
    let cancelled = false;
    const stop = () => { streamRef.current?.getTracks().forEach((t) => t.stop()); streamRef.current = null; };
    const start = async () => {
      stop();
      if (!live) { setPerm("idle"); return; }
      if (!window.isSecureContext) { setPerm("insecure"); setPermMsg("Câmera exige HTTPS (contexto seguro) — acesse via https://"); return; }
      if (!navigator.mediaDevices?.getUserMedia) { setPerm("error"); setPermMsg("Navegador sem suporte a getUserMedia."); return; }
      try {
        const s = await navigator.mediaDevices.getUserMedia({
          video: kind === "mobile" ? { facingMode: { ideal: "environment" } } : true, audio: false });
        if (cancelled) { s.getTracks().forEach((t) => t.stop()); return; }
        streamRef.current = s; setPerm("granted"); setPermMsg("");
        if (videoRef.current) { videoRef.current.srcObject = s; videoRef.current.play().catch(() => {}); }
      } catch (e) {
        const n = (e as Error).name;
        if (n === "NotAllowedError" || n === "SecurityError") { setPerm("denied"); setPermMsg("Permissão de câmera negada — habilite no cadeado do navegador e tente de novo."); }
        else if (n === "NotFoundError" || n === "OverconstrainedError") { setPerm("error"); setPermMsg("Nenhuma câmera encontrada neste dispositivo."); }
        else if (n === "NotReadableError") { setPerm("error"); setPermMsg("Câmera em uso por outro app."); }
        else { setPerm("error"); setPermMsg((e as Error).message); }
      }
    };
    start();
    return () => { cancelled = true; stop(); };
  }, [kind, live, retry]);

  const doScan = useCallback(async () => {
    setBusy(true);
    try {
      const body: { station: string; operator_id?: string | null; image_b64?: string; camera_id?: string; mtx_path?: string } = { station, operator_id: operatorId };
      if (live) {
        const v = videoRef.current;
        if (!v || !v.videoWidth) { setRes({ ok: false, message: "câmera não pronta" }); return; }
        const c = document.createElement("canvas"); c.width = v.videoWidth; c.height = v.videoHeight;
        c.getContext("2d")!.drawImage(v, 0, 0);
        body.image_b64 = c.toDataURL("image/jpeg", 0.72);
      } else if (kind.startsWith("ip:")) body.camera_id = kind.slice(3);
      else if (kind.startsWith("mtx:")) body.mtx_path = kind.slice(4);
      const r = await scanToken(body);
      if (r.ok && r.resolved && r.actions?.length) {
        if (tagHint && r.tag_id && r.tag_id !== tagHint) {
          setRes({ ok: false, message: `QR lido (${r.tag_id.split(":").slice(2, 4).join(" ")}) ≠ este Fio` }); setCard(null);
        } else { setCard(r); setAction(r.actions[0].action); setNote(""); setRes(null); }
      } else { setRes(r); setCard(null); }
    } finally { setBusy(false); }
  }, [live, kind, station, operatorId, tagHint]);

  const confirm = useCallback(async () => {
    if (!card?.tag_id) return;
    setBusy(true);
    try {
      const sel = card.actions?.find((a) => a.action === action);
      const needNote = sel?.kind === "occurrence" || sel?.kind === "block";
      const out = await stationAction({ tag_id: card.tag_id, action, station, operator_id: operatorId,
        payload: needNote && note ? { note } : undefined });
      setRes({ ok: out.ok, tag_id: card.tag_id, action: out.action, state: out.state, phase: out.phase, genesis: card.genesis, operator_id: out.operator_id });
      setCard(null); setNote(""); onScanned();
    } finally { setBusy(false); }
  }, [card, action, note, station, operatorId, onScanned]);

  useEffect(() => {
    if (!auto) return;
    const id = window.setInterval(() => { if (!busy && !card) doScan(); }, 1600);
    return () => window.clearInterval(id);
  }, [auto, busy, card, doScan]);

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <select value={kind} onChange={(e) => { setKind(e.target.value); setRes(null); setCard(null); }} className="flex-1 bg-edge border border-edge rounded px-2 py-1.5 text-xs">
          <option value="local">💻 Este dispositivo</option>
          <option value="mobile">📱 Mobile (câmera traseira)</option>
          {saved.map((c) => <option key={c.id} value={`ip:${c.id}`}>📷 {c.name} (IP)</option>)}
          <option value="mtx:osmo_pocket">📷 Osmo (MediaMTX)</option>
          <option value="mtx:drone_neo2">🛸 Drone (MediaMTX)</option>
        </select>
        <label className="flex items-center gap-1 text-[10px] text-muted"><input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} /> auto</label>
      </div>

      <div className="aspect-video w-full rounded-card overflow-hidden bg-black grid place-items-center text-center">
        {live ? (
          perm === "granted" ? (
            <video ref={videoRef} muted playsInline className="w-full h-full object-cover" />
          ) : (
            <div className="p-4 text-xs text-white/80">
              <p className="text-2xl mb-1">🎥</p>
              <p>{permMsg || "Permita o acesso à câmera para escanear"}</p>
              {perm !== "insecure" && <button onClick={() => setRetry((r) => r + 1)} className="mt-2 px-3 py-1.5 rounded-card border border-accent text-accent hover:bg-accent/10">Permitir câmera</button>}
            </div>
          )
        ) : kind.startsWith("ip:") ? (
          <img src={mjpegUrl(kind.slice(3), true)} alt="ip" className="w-full h-full object-contain" />
        ) : (
          <img src={mtxMjpegUrl(kind.slice(4))} alt="mtx" className="w-full h-full object-contain" />
        )}
      </div>

      <button onClick={doScan} disabled={busy || (live && perm !== "granted")}
        className="w-full py-3 rounded-card border border-accent text-accent hover:bg-accent/10 disabled:opacity-50 font-semibold">
        📷 {busy ? "lendo…" : "APONTAR / ESCANEAR"}
      </button>
      <p className="text-[10px] text-muted text-center">a câmera (modo LER) lê o token QR e registra no Fio Dourado</p>

      {card && (
        <div className="bg-surface border border-accent/50 rounded-card p-3 space-y-2">
          <div className="flex items-center gap-3">
            <img src={qrUrl(card.tag_id!)} alt="qr" className="w-14 h-14 bg-white p-1 rounded shrink-0" />
            <div className="min-w-0 text-xs flex-1">
              <p className="font-bold text-text truncate">{card.info?.natural_key} · {card.info?.entity_type}</p>
              <p className="font-mono text-[10px] text-muted break-all">{card.tag_id}</p>
              <p className="text-[10px] text-muted mt-0.5">{card.genesis ? "● nova instância (gênese)" : `estado ${card.state} · fase ${card.phase}`}{card.info?.parent ? ` · ⤷ ${card.info.parent}` : ""}</p>
            </div>
          </div>
          <label className="block text-[10px] uppercase tracking-wider text-accent">Ação a registrar
            <select value={action} onChange={(e) => setAction(e.target.value)} className="w-full mt-1 bg-edge border border-accent/40 rounded px-2 py-1.5 text-sm text-text">
              {card.actions?.map((a) => <option key={a.action} value={a.action}>{a.label}</option>)}
            </select>
          </label>
          {(() => { const sel = card.actions?.find((a) => a.action === action); return sel && (sel.kind === "occurrence" || sel.kind === "block"); })() && (
            <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="motivo / observação" className="w-full bg-warn/10 border border-warn/40 rounded px-2 py-1.5 text-sm text-text" />
          )}
          <div className="flex gap-2">
            <button onClick={confirm} disabled={busy} className="flex-1 py-2 rounded-card border border-accent text-accent hover:bg-accent/10 disabled:opacity-50 font-semibold">✓ {busy ? "registrando…" : "Registrar ação"}</button>
            <button onClick={() => setCard(null)} className="px-3 py-2 rounded-card border border-edge text-muted hover:border-nok">Cancelar</button>
          </div>
        </div>
      )}

      {!card && res && (res.ok ? (
        <div className="flex items-center gap-3 bg-ok/5 border border-ok/40 rounded-card p-2.5">
          <img src={qrUrl(res.tag_id!)} alt="qr" className="w-16 h-16 bg-white p-1 rounded shrink-0" />
          <div className="min-w-0 text-xs">
            <p className="font-mono text-text break-all">{res.tag_id}</p>
            <p className="text-muted mt-0.5"><span className="px-1.5 py-0.5 rounded bg-accent/15 text-accent">{res.action}</span><span className="ml-1.5">{res.state} · {res.phase}</span></p>
            <p className="text-[10px] text-ok mt-0.5">✅ registrado por {res.operator_id ?? "—"}</p>
          </div>
        </div>
      ) : (
        <p className="text-xs bg-warn/10 border border-warn/40 rounded p-2 text-warn">⚠ {res.message}</p>
      ))}
    </div>
  );
}
