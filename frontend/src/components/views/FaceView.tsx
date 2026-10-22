import { useCallback, useEffect, useRef, useState } from "react";
import { useStore } from "../../store/useStore";
import { snapshot } from "../../api/cameras";
import { captureFrame } from "../../lib/capture";
import {
  faceEnroll, faceGallery, faceIdentify, faceRevoke, faceStatus,
  type FaceKpis, type FaceOperator, type IdentifyResult,
} from "../../api/face";
import { btnCls, btnPrimaryCls, inputCls, labelCls } from "../../lib/ui";

type Src = { id: string; label: string; kind: "ip" | "aerial" | "device" | "screen"; cameraId?: string; url?: string };

export function FaceView() {
  const saved = useStore((s) => s.savedCameras);
  const activeStream = useStore((s) => s.activeStream);
  const activeDeviceId = useStore((s) => s.activeDeviceId);
  const sourceId = useStore((s) => s.sourceId);
  const setView = useStore((s) => s.setView);

  const vidRef = useRef<HTMLVideoElement | null>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);
  const boxRef = useRef<HTMLDivElement | null>(null);
  const loop = useRef<number | null>(null);
  const busy = useRef(false);

  const [srcId, setSrcId] = useState("");
  const [identifying, setIdentifying] = useState(false);
  const [res, setRes] = useState<IdentifyResult | null>(null);
  const [gallery, setGallery] = useState<FaceOperator[]>([]);
  const [kpis, setKpis] = useState<FaceKpis | null>(null);
  const [name, setName] = useState("");
  const [consent, setConsent] = useState(false);
  const [msg, setMsg] = useState("");

  const sources: Src[] = [
    ...(activeStream ? [{
      id: "dev:active", kind: (activeDeviceId === "screen" ? "screen" : "device") as "screen" | "device",
      label: activeDeviceId === "screen" ? "🖥 Tela" : `💻 Dispositivo (${sourceId})`,
    }] : []),
    ...saved.map((c) => ({ id: `cam:${c.id}`, label: `📷 ${c.name}`, kind: "ip" as const, cameraId: c.id })),
    { id: "aer:osmo", label: "🎥 Osmo", kind: "aerial" as const, url: "rtsp://localhost:8554/osmo_pocket" },
  ];
  const src = sources.find((s) => s.id === srcId) ?? sources[0] ?? null;

  useEffect(() => { if (!srcId && sources.length) setSrcId(sources[0].id); /* eslint-disable-next-line */ }, [saved.length, !!activeStream]);
  useEffect(() => {
    const v = vidRef.current; if (!v) return;
    if (activeStream) { v.srcObject = activeStream; v.play().catch(() => undefined); } else v.srcObject = null;
  }, [activeStream]);

  const refreshMeta = useCallback(() => {
    faceGallery().then(setGallery).catch(() => undefined);
    faceStatus().then(setKpis).catch(() => undefined);
  }, []);
  useEffect(() => { refreshMeta(); }, [refreshMeta]);

  const grab = useCallback(async (): Promise<string | null> => {
    if (!src) return null;
    if (src.kind === "ip") { const s = await snapshot({ cameraId: src.cameraId! }); if (imgRef.current) imgRef.current.src = `data:image/jpeg;base64,${s.image_b64}`; return s.image_b64; }
    if (src.kind === "aerial") { const s = await snapshot({ url: src.url! }); if (imgRef.current) imgRef.current.src = `data:image/jpeg;base64,${s.image_b64}`; return s.image_b64; }
    return vidRef.current ? captureFrame(vidRef.current, 1280) : null;
  }, [src]);

  // Loop de identificação 1:N (client-driven, ~1.4 fps — telas/rostos mudam devagar).
  useEffect(() => {
    if (!identifying) { if (loop.current) window.clearInterval(loop.current); loop.current = null; return; }
    const tick = async () => {
      if (busy.current) return; busy.current = true;
      try { const b = await grab(); if (b) { const r = await faceIdentify(b); setRes(r); if (r.matched) refreshMeta(); } }
      catch { /* ignore */ } finally { busy.current = false; }
    };
    tick(); loop.current = window.setInterval(tick, 700);
    return () => { if (loop.current) window.clearInterval(loop.current); loop.current = null; };
  }, [identifying, grab, refreshMeta]);

  const enroll = async () => {
    if (!name.trim()) { setMsg("informe o nome do operador"); return; }
    if (!consent) { setMsg("marque o consentimento (biometria é dado sensível)"); return; }
    const b = await grab();
    if (!b) { setMsg("sem frame da fonte"); return; }
    const oid = "op_" + name.trim().toLowerCase().replace(/\s+/g, "_");
    const r = await faceEnroll(oid, name.trim(), b, consent);
    setMsg(r.ok ? `✓ ${name} cadastrado (nitidez ${r.sharpness})` : `✗ ${r.message}`);
    if (r.ok) { setName(""); setConsent(false); refreshMeta(); }
  };

  const revoke = async (oid: string) => {
    await faceRevoke(oid); refreshMeta();
  };

  // overlay do bbox sobre a mídia
  const bbox = res?.bbox;
  const sevColor = res?.matched ? "border-ok text-ok" : res?.live === false ? "border-nok text-nok" : "border-warn text-warn";

  return (
    <div className="flex flex-col gap-3 min-h-full lg:h-full lg:min-h-0">
      <div className="flex items-center gap-2 flex-wrap shrink-0">
        <h2 className="text-lg font-bold">🙂 Reconhecimento Facial</h2>
        <span className="text-xs text-muted">identificação consentida de operador · edge · template (não foto) · LGPD</span>
        <button className="ml-auto text-xs text-accent hover:underline" onClick={() => setView("operadores")}>Operadores →</button>
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-[330px_1fr_320px] gap-4 min-h-0">
        {/* Controles */}
        <aside className="bg-panel rounded-card border border-edge p-4 overflow-y-auto scroll-thin space-y-4">
          <section className="border-b border-edge pb-4">
            <label className={labelCls}>Fonte (estação)</label>
            <select className={inputCls} value={src?.id ?? ""} onChange={(e) => setSrcId(e.target.value)}>
              {sources.length === 0 && <option value="">(conecte uma câmera/dispositivo)</option>}
              {sources.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
            </select>
            <div className="flex gap-2 mt-3">
              {!identifying
                ? <button className={btnPrimaryCls} onClick={() => setIdentifying(true)} disabled={!src}>▶ Identificar (1:N)</button>
                : <button className={btnCls} onClick={() => setIdentifying(false)}>⏸ Parar</button>}
            </div>
          </section>

          <section className="border-b border-edge pb-4">
            <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Cadastrar operador (consentido)</h3>
            <input className={inputCls} placeholder="Nome do operador" value={name} onChange={(e) => setName(e.target.value)} />
            <label className="flex items-start gap-2 mt-2 text-[12px] text-text cursor-pointer">
              <input type="checkbox" className="mt-0.5" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
              <span>Consinto o uso da minha biometria facial para login/autoria nesta estação (LGPD art. 11). Sei que guarda o <b>template</b>, não a foto, e é <b>revogável</b>.</span>
            </label>
            <button className={btnCls + " w-full mt-2"} onClick={enroll} disabled={!src}>📸 Capturar &amp; cadastrar</button>
            {msg && <p className="text-[11px] text-warn mt-1">{msg}</p>}
          </section>

          <section>
            <h3 className="text-xs uppercase tracking-wider text-muted mb-2">🔒 Privacidade (LGPD)</h3>
            <ul className="text-[11px] text-muted space-y-1 list-disc pl-4">
              <li>Opt-in: sempre há fallback (PIN/crachá) — ninguém é obrigado.</li>
              <li>Edge: template no dispositivo; <b>não</b> envia foto à nuvem.</li>
              <li>Finalidade restrita: identificação/acesso — <b>nunca</b> vigilância.</li>
              <li>Revogável: retirar consentimento apaga o template.</li>
            </ul>
          </section>
        </aside>

        {/* Preview + overlay */}
        <section className="bg-panel rounded-card border border-edge p-4 overflow-hidden min-h-[50vh] lg:min-h-0 flex flex-col">
          <div ref={boxRef} className="flex-1 bg-black rounded-card overflow-hidden flex items-center justify-center relative min-h-0">
            {src?.kind === "device" || src?.kind === "screen"
              ? <video ref={vidRef} className="w-full h-full object-contain" playsInline muted />
              : <img ref={imgRef} className="w-full h-full object-contain" alt="frame" />}
            {bbox && (
              <div className={"absolute border-2 rounded " + (res?.matched ? "border-ok" : res?.live === false ? "border-nok" : "border-warn")}
                style={{ left: `${bbox[0] * 100}%`, top: `${bbox[1] * 100}%`, width: `${bbox[2] * 100}%`, height: `${bbox[3] * 100}%` }} />
            )}
            {identifying && <span className="absolute top-2 left-2 text-[10px] text-emerald-300 font-bold bg-black/50 px-1.5 py-0.5 rounded">● IDENTIFICANDO</span>}
            {!src && <span className="text-muted text-sm">Conecte uma câmera/dispositivo (ou compartilhe a tela).</span>}
          </div>
          {res && (
            <div className={"mt-3 shrink-0 rounded-card border px-3 py-2 " + sevColor}>
              {res.matched
                ? <span className="font-bold">✓ {res.name} <span className="text-xs opacity-80">· score {res.score} (≥ {res.threshold})</span></span>
                : res.live === false
                  ? <span className="font-bold">⚠ liveness/qualidade reprovada — aproxime, melhore a luz</span>
                  : <span className="font-bold">não reconhecido <span className="text-xs opacity-80">· score {res.score ?? "—"} · use PIN/crachá</span></span>}
            </div>
          )}
        </section>

        {/* Galeria + KPIs */}
        <aside className="bg-panel rounded-card border border-edge p-4 overflow-y-auto scroll-thin space-y-4">
          {kpis && (
            <section className="border-b border-edge pb-3">
              <h3 className="text-xs uppercase tracking-wider text-muted mb-2">KPIs (CLD_)</h3>
              <div className="grid grid-cols-2 gap-1.5 text-sm">
                <div className="rounded border border-edge bg-edge/40 px-2 py-1"><div className="text-[10px] text-muted uppercase">Cadastrados</div><div className="font-bold">{kpis.enrolled}</div></div>
                <div className="rounded border border-edge bg-edge/40 px-2 py-1"><div className="text-[10px] text-muted uppercase">Sucesso auth</div><div className="font-bold">{kpis.CLD_Auth_Success_Rate ?? "—"}%</div></div>
                <div className="rounded border border-edge bg-edge/40 px-2 py-1"><div className="text-[10px] text-muted uppercase">Liveness bloq.</div><div className="font-bold">{kpis.CLD_Liveness_Block_Rate}</div></div>
                <div className="rounded border border-edge bg-edge/40 px-2 py-1"><div className="text-[10px] text-muted uppercase">Negados</div><div className="font-bold">{kpis.denied}</div></div>
              </div>
              <p className="text-[10px] text-muted mt-1">algoritmo: {kpis.algo} · limiar {kpis.threshold}</p>
            </section>
          )}
          <section>
            <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Galeria autorizada ({gallery.length})</h3>
            {gallery.length === 0 ? <p className="text-xs text-muted">Nenhum operador cadastrado.</p> : (
              <ul className="space-y-1">
                {gallery.map((o) => (
                  <li key={o.operator_id} className="flex items-center gap-2 text-sm border-b border-edge/40 py-1">
                    <span className="flex-1 truncate">🙂 {o.name}</span>
                    <span className="text-[10px] text-muted">{new Date(o.consent_ts).toLocaleDateString()}</span>
                    <button className="text-muted hover:text-nok text-xs" title="Revogar consentimento (apaga template)" onClick={() => revoke(o.operator_id)}>revogar ✕</button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </aside>
      </div>
    </div>
  );
}
