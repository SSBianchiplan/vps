import { useCallback, useEffect, useRef, useState } from "react";
import { useStore } from "../../store/useStore";
import { snapshot } from "../../api/cameras";
import { captureFrame } from "../../lib/capture";
import { metroCalibrate, metroMeasure, metroStatus, type MeasureResult, type MetroKpis, type Pt } from "../../api/metro";
import { btnCls, btnPrimaryCls, inputCls, labelCls } from "../../lib/ui";

type Src = { id: string; label: string; kind: "ip" | "aerial" | "device" | "screen"; cameraId?: string; url?: string };
type Kind = "linear" | "diameter" | "angle";

export function MetrologyView() {
  const saved = useStore((s) => s.savedCameras);
  const activeStream = useStore((s) => s.activeStream);
  const activeDeviceId = useStore((s) => s.activeDeviceId);
  const sourceId = useStore((s) => s.sourceId);

  const vidRef = useRef<HTMLVideoElement | null>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);
  const wrapRef = useRef<HTMLDivElement | null>(null);

  const [srcId, setSrcId] = useState("");
  const [frame, setFrame] = useState<string | null>(null);
  const [dims, setDims] = useState<[number, number]>([0, 0]);
  const [kind, setKind] = useState<Kind>("linear");
  const [pts, setPts] = useState<Pt[]>([]);
  const [feature, setFeature] = useState("largura");
  const [nominal, setNominal] = useState(100);
  const [tolLo, setTolLo] = useState(-0.5);
  const [tolHi, setTolHi] = useState(0.5);
  const [opTag, setOpTag] = useState("");
  const [knownMm, setKnownMm] = useState(100);
  const [calRef, setCalRef] = useState("CAL-2026");
  const [res, setRes] = useState<MeasureResult | null>(null);
  const [kpis, setKpis] = useState<MetroKpis | null>(null);
  const [msg, setMsg] = useState("");

  const need = kind === "angle" ? 3 : 2;

  const sources: Src[] = [
    ...(activeStream ? [{ id: "dev:active", kind: (activeDeviceId === "screen" ? "screen" : "device") as "screen" | "device", label: activeDeviceId === "screen" ? "🖥 Tela" : `💻 Dispositivo (${sourceId})` }] : []),
    ...saved.map((c) => ({ id: `cam:${c.id}`, label: `📷 ${c.name}`, kind: "ip" as const, cameraId: c.id })),
    { id: "aer:osmo", label: "🎥 Osmo", kind: "aerial" as const, url: "rtsp://localhost:8554/osmo_pocket" },
  ];
  const src = sources.find((s) => s.id === srcId) ?? sources[0] ?? null;
  useEffect(() => { if (!srcId && sources.length) setSrcId(sources[0].id); /* eslint-disable-next-line */ }, [saved.length, !!activeStream]);
  useEffect(() => {
    const v = vidRef.current; if (!v) return;
    if (activeStream) { v.srcObject = activeStream; v.play().catch(() => undefined); } else v.srcObject = null;
  }, [activeStream]);

  const refreshKpis = useCallback(() => { metroStatus().then(setKpis).catch(() => undefined); }, []);
  useEffect(() => { refreshKpis(); }, [refreshKpis]);

  const capture = async () => {
    if (!src) return;
    setMsg(""); setPts([]); setRes(null);
    try {
      let b64: string | null = null;
      if (src.kind === "ip") b64 = (await snapshot({ cameraId: src.cameraId! })).image_b64;
      else if (src.kind === "aerial") b64 = (await snapshot({ url: src.url! })).image_b64;
      else b64 = vidRef.current ? captureFrame(vidRef.current, 1600) : null;
      if (!b64) { setMsg("sem frame"); return; }
      setFrame(`data:image/jpeg;base64,${b64}`);
    } catch (e) { setMsg(String((e as Error)?.message ?? e)); }
  };

  // clique → ponto normalizado dentro do conteúdo da imagem (object-contain)
  const onClick = (e: React.MouseEvent) => {
    const wrap = wrapRef.current, img = imgRef.current;
    if (!wrap || !img || !img.naturalWidth) return;
    const r = wrap.getBoundingClientRect();
    const scale = Math.min(r.width / img.naturalWidth, r.height / img.naturalHeight);
    const cw = img.naturalWidth * scale, ch = img.naturalHeight * scale;
    const ox = (r.width - cw) / 2, oy = (r.height - ch) / 2;
    const x = (e.clientX - r.left - ox) / cw, y = (e.clientY - r.top - oy) / ch;
    if (x < 0 || x > 1 || y < 0 || y > 1) return;
    setPts((p) => [...p, [x, y]].slice(-need) as Pt[]);
  };

  const doCalibrate = async () => {
    if (pts.length < 2) { setMsg("clique 2 pontos sobre uma referência de comprimento conhecido"); return; }
    const r = await metroCalibrate(calRef, pts[0], pts[1], knownMm, dims[0] || 1000, dims[1] || 1000);
    setMsg(r.ok ? `✓ calibrado ${calRef}: ${r.scale_mm_per_px?.toFixed(5)} mm/px` : `✗ ${r.message}`);
    setPts([]); refreshKpis();
  };
  const doMeasure = async () => {
    if (pts.length < need) { setMsg(`clique ${need} ponto(s)`); return; }
    const r = await metroMeasure({ kind, points: pts, frame_w: dims[0] || 1000, frame_h: dims[1] || 1000, feature, nominal, tol_lo: tolLo, tol_hi: tolHi, op_tag: opTag || null });
    setRes(r); if (!r.ok) setMsg(r.message || ""); else setMsg(""); refreshKpis();
  };

  // posição em px (do container) p/ desenhar os marcadores
  const markPos = (p: Pt) => {
    const wrap = wrapRef.current, img = imgRef.current;
    if (!wrap || !img || !img.naturalWidth) return { left: "0", top: "0" };
    const r = wrap.getBoundingClientRect();
    const scale = Math.min(r.width / img.naturalWidth, r.height / img.naturalHeight);
    const cw = img.naturalWidth * scale, ch = img.naturalHeight * scale;
    return { left: `${(r.width - cw) / 2 + p[0] * cw}px`, top: `${(r.height - ch) / 2 + p[1] * ch}px` };
  };

  const ok = res?.verdict === "CONFORME";
  return (
    <div className="flex flex-col gap-3 min-h-full lg:h-full lg:min-h-0">
      <div className="flex items-center gap-2 flex-wrap shrink-0">
        <h2 className="text-lg font-bold">📏 Metrologia / Inspeção Dimensional</h2>
        <span className="text-xs text-muted">medir cotas reais (px→mm calibrado) com tolerância · CONFORME/NÃO CONFORME + incerteza</span>
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-[330px_1fr_300px] gap-4 min-h-0">
        <aside className="bg-panel rounded-card border border-edge p-4 overflow-y-auto scroll-thin space-y-4">
          <section className="border-b border-edge pb-3">
            <label className={labelCls}>Fonte</label>
            <select className={inputCls} value={src?.id ?? ""} onChange={(e) => setSrcId(e.target.value)}>
              {sources.length === 0 && <option value="">(conecte uma fonte)</option>}
              {sources.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
            </select>
            <button className={btnPrimaryCls + " w-full mt-2"} onClick={capture} disabled={!src}>📸 Capturar frame</button>
            <div className="grid grid-cols-3 gap-1 mt-2">
              {(["linear", "diameter", "angle"] as Kind[]).map((k) => (
                <button key={k} onClick={() => { setKind(k); setPts([]); }}
                  className={"py-1 rounded text-xs border " + (kind === k ? "bg-accent text-onaccent border-accent" : "bg-edge border-edge")}>
                  {k === "linear" ? "Linear" : k === "diameter" ? "Diâmetro" : "Ângulo"}
                </button>
              ))}
            </div>
            <p className="text-[11px] text-muted mt-1">Clique {need} ponto(s) sobre o frame. {pts.length}/{need} marcados. <button className="text-accent hover:underline" onClick={() => setPts([])}>limpar</button></p>
          </section>

          <section className="border-b border-edge pb-3">
            <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Calibração (px→mm)</h3>
            <div className="flex gap-1">
              <input className={inputCls} value={calRef} onChange={(e) => setCalRef(e.target.value)} placeholder="ref" />
              <input className={inputCls + " w-24"} type="number" value={knownMm} onChange={(e) => setKnownMm(Number(e.target.value))} placeholder="mm" />
            </div>
            <button className={btnCls + " w-full mt-2"} onClick={doCalibrate}>Calibrar c/ 2 pontos (= {knownMm}mm)</button>
            {kpis?.calibration && <p className="text-[10px] text-muted mt-1">atual: {kpis.calibration.ref} · {kpis.calibration.scale_mm_per_px.toFixed(5)} mm/px {kpis.calibration.valid ? "✓" : "⚠ vencida"}</p>}
          </section>

          <section>
            <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Medir feature</h3>
            <input className={inputCls} value={feature} onChange={(e) => setFeature(e.target.value)} placeholder="nome (ex.: largura)" />
            <div className="grid grid-cols-3 gap-1 mt-2">
              <div><label className="text-[10px] text-muted">nominal</label><input className={inputCls} type="number" value={nominal} onChange={(e) => setNominal(Number(e.target.value))} /></div>
              <div><label className="text-[10px] text-muted">tol −</label><input className={inputCls} type="number" step="0.1" value={tolLo} onChange={(e) => setTolLo(Number(e.target.value))} /></div>
              <div><label className="text-[10px] text-muted">tol +</label><input className={inputCls} type="number" step="0.1" value={tolHi} onChange={(e) => setTolHi(Number(e.target.value))} /></div>
            </div>
            <input className={inputCls + " mt-2"} value={opTag} onChange={(e) => setOpTag(e.target.value)} placeholder="op_tag (opcional) — VPS:...:OP:..." />
            <button className={btnPrimaryCls + " w-full mt-2"} onClick={doMeasure} disabled={!frame}>📏 Medir &amp; julgar</button>
            {msg && <p className="text-[11px] text-warn mt-1">{msg}</p>}
          </section>
        </aside>

        {/* Frame + pontos */}
        <section className="bg-panel rounded-card border border-edge p-4 overflow-hidden min-h-[50vh] lg:min-h-0 flex flex-col">
          <div ref={wrapRef} onClick={onClick}
            className="flex-1 bg-black rounded-card overflow-hidden flex items-center justify-center relative min-h-0 cursor-crosshair">
            {frame
              ? <img ref={imgRef} src={frame} className="w-full h-full object-contain select-none" alt="frame"
                  onLoad={(e) => setDims([(e.target as HTMLImageElement).naturalWidth, (e.target as HTMLImageElement).naturalHeight])} draggable={false} />
              : <span className="text-muted text-sm px-4 text-center">Capture um frame e clique os pontos da cota.</span>}
            {frame && pts.map((p, i) => (
              <div key={i} className="absolute w-3 h-3 -ml-1.5 -mt-1.5 rounded-full bg-accent border border-white pointer-events-none" style={markPos(p)} />
            ))}
            <video ref={vidRef} className="hidden" playsInline muted />
          </div>
          {res?.ok && (
            <div className={"mt-3 shrink-0 rounded-card border px-3 py-2 flex items-center gap-3 flex-wrap " + (ok ? "border-ok/50 text-ok bg-ok/10" : "border-nok/50 text-nok bg-nok/10")}>
              <span className="font-bold">{ok ? "✓ CONFORME" : "✗ NÃO CONFORME"}</span>
              <span className="text-sm">{res.feature}: <b>{res.measured}{res.unit}</b></span>
              <span className="text-sm">nom {res.nominal}{res.unit} (tol {res.tol?.[0]}…{res.tol?.[1]})</span>
              <span className="text-sm">desvio {res.deviation}</span>
              <span className="text-sm ml-auto">± {res.uncertainty}{res.unit} · cal {res.calibration_ref ?? "—"}</span>
            </div>
          )}
        </section>

        {/* KPIs */}
        <aside className="bg-panel rounded-card border border-edge p-4 overflow-y-auto scroll-thin space-y-3">
          {kpis && (
            <>
              <h3 className="text-xs uppercase tracking-wider text-muted">KPIs (CLD_)</h3>
              <div className="grid grid-cols-2 gap-1.5 text-sm">
                <div className="rounded border border-edge bg-edge/40 px-2 py-1"><div className="text-[10px] text-muted uppercase">Medições</div><div className="font-bold">{kpis.measurements}</div></div>
                <div className="rounded border border-edge bg-edge/40 px-2 py-1"><div className="text-[10px] text-muted uppercase">Pass rate</div><div className="font-bold">{kpis.CLD_Measurement_Pass_Rate ?? "—"}%</div></div>
                <div className="rounded border border-edge bg-edge/40 px-2 py-1"><div className="text-[10px] text-muted uppercase">Incerteza méd</div><div className="font-bold">{kpis.CLD_Measurement_Uncertainty ?? "—"}</div></div>
                <div className="rounded border border-edge bg-edge/40 px-2 py-1"><div className="text-[10px] text-muted uppercase">Calibração</div><div className={"font-bold " + (kpis.CLD_Calibration_Validity ? "text-ok" : "text-warn")}>{kpis.CLD_Calibration_Validity ? "válida" : "—"}</div></div>
              </div>
              {Object.keys(kpis.CLD_Cpk).length > 0 && (
                <div>
                  <h3 className="text-xs uppercase tracking-wider text-muted mb-1 mt-2">Cpk por feature</h3>
                  <ul className="space-y-0.5">
                    {Object.entries(kpis.CLD_Cpk).map(([f, c]) => (
                      <li key={f} className="flex items-center justify-between text-sm border-b border-edge/40 py-1">
                        <span className="truncate">{f}</span>
                        <span className={"font-mono font-bold " + (c >= 1.33 ? "text-ok" : c >= 1 ? "text-warn" : "text-nok")}>{c}</span>
                      </li>
                    ))}
                  </ul>
                  <p className="text-[10px] text-muted mt-1">Cpk ≥ 1.33 capaz · 1–1.33 marginal · &lt;1 incapaz</p>
                </div>
              )}
              <p className="text-[11px] text-muted">Calibração rastreável: cada medição amarra a `calibration_ref`. Reprovação gera ocorrência VPS (retrabalho). Produção: óptica telecêntrica + bordas sub-pixel (Cognex/LabVIEW).</p>
            </>
          )}
        </aside>
      </div>
    </div>
  );
}
