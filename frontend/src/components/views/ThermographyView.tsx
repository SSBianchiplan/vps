import { useCallback, useEffect, useRef, useState } from "react";
import { useStore } from "../../store/useStore";
import { snapshot } from "../../api/cameras";
import { captureFrame } from "../../lib/capture";
import {
  thermoAnalyze, thermoAssets, thermoBaseline, thermoStatus, thermoTrend, thermoUpsertAsset,
  type Severity, type ThermalAsset, type ThermalReading, type ThermalResult, type ThermoKpis,
} from "../../api/thermo";
import { btnCls, btnPrimaryCls, inputCls, labelCls } from "../../lib/ui";

type Src = { id: string; label: string; kind: "ip" | "aerial" | "device" | "screen"; cameraId?: string; url?: string };

const SEV: Record<Severity, { cls: string; label: string }> = {
  NORMAL: { cls: "border-ok/50 text-ok bg-ok/10", label: "NORMAL" },
  OBSERVAR: { cls: "border-accent-2/50 text-accent-2 bg-accent-2/10", label: "OBSERVAR" },
  AGIR: { cls: "border-warn/50 text-warn bg-warn/10", label: "AGIR" },
  CRITICO: { cls: "border-nok/50 text-nok bg-nok/10", label: "CRÍTICO" },
};

export function ThermographyView() {
  const saved = useStore((s) => s.savedCameras);
  const activeStream = useStore((s) => s.activeStream);
  const activeDeviceId = useStore((s) => s.activeDeviceId);
  const sourceId = useStore((s) => s.sourceId);

  const vidRef = useRef<HTMLVideoElement | null>(null);
  const [srcId, setSrcId] = useState("");
  const [assets, setAssets] = useState<ThermalAsset[]>([]);
  const [assetId, setAssetId] = useState("");
  const [newAsset, setNewAsset] = useState("");
  const [res, setRes] = useState<ThermalResult | null>(null);
  const [trend, setTrend] = useState<ThermalReading[]>([]);
  const [kpis, setKpis] = useState<ThermoKpis | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const sources: Src[] = [
    ...(activeStream ? [{ id: "dev:active", kind: (activeDeviceId === "screen" ? "screen" : "device") as "screen" | "device", label: activeDeviceId === "screen" ? "🖥 Tela" : `💻 Dispositivo (${sourceId})` }] : []),
    ...saved.map((c) => ({ id: `cam:${c.id}`, label: `📷 ${c.name}`, kind: "ip" as const, cameraId: c.id })),
    { id: "aer:drone", label: "🛸 Drone", kind: "aerial" as const, url: "rtsp://localhost:8554/drone_neo2" },
    { id: "aer:osmo", label: "🎥 Osmo", kind: "aerial" as const, url: "rtsp://localhost:8554/osmo_pocket" },
  ];
  const src = sources.find((s) => s.id === srcId) ?? sources[0] ?? null;

  useEffect(() => { if (!srcId && sources.length) setSrcId(sources[0].id); /* eslint-disable-next-line */ }, [saved.length, !!activeStream]);
  useEffect(() => {
    const v = vidRef.current; if (!v) return;
    if (activeStream) { v.srcObject = activeStream; v.play().catch(() => undefined); } else v.srcObject = null;
  }, [activeStream]);

  const refreshMeta = useCallback(() => {
    thermoAssets().then((a) => { setAssets(a); setAssetId((cur) => cur || a[0]?.asset_id || ""); }).catch(() => undefined);
    thermoStatus().then(setKpis).catch(() => undefined);
  }, []);
  useEffect(() => { refreshMeta(); }, [refreshMeta]);
  useEffect(() => { if (assetId) thermoTrend(assetId).then(setTrend).catch(() => undefined); }, [assetId, res]);

  const grab = async (): Promise<string | null> => {
    if (!src) return null;
    if (src.kind === "ip") return (await snapshot({ cameraId: src.cameraId! })).image_b64;
    if (src.kind === "aerial") return (await snapshot({ url: src.url! })).image_b64;
    return vidRef.current ? captureFrame(vidRef.current, 1280) : null;
  };

  const createAsset = async () => {
    const id = newAsset.trim(); if (!id) return;
    await thermoUpsertAsset({ asset_id: id, name: id, tag_id: `VPS:PLANT:ASSET:${id}:01` });
    setNewAsset(""); setAssetId(id); refreshMeta();
  };

  const run = async (mode: "analyze" | "baseline") => {
    if (!assetId) { setMsg("crie/selecione um ativo"); return; }
    setBusy(true); setMsg("");
    try {
      const b = await grab();
      if (!b) { setMsg("sem frame da fonte"); return; }
      if (mode === "baseline") {
        const r = await thermoBaseline(assetId, b);
        setMsg(`✓ baseline ${r.baseline_tmax}°C`); refreshMeta();
      } else {
        const r = await thermoAnalyze(assetId, b);
        setRes(r); refreshMeta();
      }
    } catch (e) { setMsg(String((e as Error)?.message ?? e)); }
    finally { setBusy(false); }
  };

  const maxT = Math.max(1, ...trend.map((r) => r.t_max));
  const minT = Math.min(...trend.map((r) => r.t_max), 0);

  return (
    <div className="flex flex-col gap-3 min-h-full lg:h-full lg:min-h-0">
      <div className="flex items-center gap-2 flex-wrap shrink-0">
        <h2 className="text-lg font-bold">🌡 Termografia — Manutenção Preditiva</h2>
        <span className="text-xs text-muted">hotspot · ΔT · baseline · tendência → predição (ANALISAR térmico)</span>
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-[330px_1fr_320px] gap-4 min-h-0">
        <aside className="bg-panel rounded-card border border-edge p-4 overflow-y-auto scroll-thin space-y-4">
          <section className="border-b border-edge pb-4">
            <label className={labelCls}>Fonte</label>
            <select className={inputCls} value={src?.id ?? ""} onChange={(e) => setSrcId(e.target.value)}>
              {sources.length === 0 && <option value="">(conecte uma fonte)</option>}
              {sources.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
            </select>
            <label className={labelCls + " mt-3"}>Ativo (asset)</label>
            <select className={inputCls} value={assetId} onChange={(e) => setAssetId(e.target.value)}>
              {assets.length === 0 && <option value="">(crie um ativo)</option>}
              {assets.map((a) => <option key={a.asset_id} value={a.asset_id}>{a.name}</option>)}
            </select>
            <div className="flex gap-1 mt-2">
              <input className={inputCls} placeholder="novo ativo (ex.: QGBT-03)" value={newAsset} onChange={(e) => setNewAsset(e.target.value)} />
              <button className={btnCls} onClick={createAsset}>＋</button>
            </div>
            <div className="flex gap-2 mt-3">
              <button className={btnPrimaryCls} onClick={() => run("analyze")} disabled={busy || !src}>🌡 Analisar</button>
              <button className={btnCls} onClick={() => run("baseline")} disabled={busy || !src} title="Definir assinatura térmica saudável">Baseline</button>
            </div>
            {msg && <p className="text-[11px] text-warn mt-2">{msg}</p>}
          </section>

          <section>
            <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Notas</h3>
            <p className="text-[11px] text-muted">
              Sem FLIR radiométrico, usa-se <b>pseudo-radiometria</b> (luminância→°C na faixa do ativo).
              Para medição real, trocar a fonte por câmera FLIR (temperatura por pixel) — o pipeline é o mesmo.
              Hotspot AGIR/CRÍTICO vira <b>ocorrência</b>; tendência alta gera <b>MANUTENÇÃO RECOMENDADA</b> (→ APS).
            </p>
          </section>
        </aside>

        {/* Preview térmico + hotspot */}
        <section className="bg-panel rounded-card border border-edge p-4 overflow-hidden min-h-[50vh] lg:min-h-0 flex flex-col">
          <div className="flex-1 bg-black rounded-card overflow-hidden flex items-center justify-center relative min-h-0">
            {res?.thermal_b64
              ? <img src={`data:image/jpeg;base64,${res.thermal_b64}`} className="w-full h-full object-contain" alt="térmico" />
              : <span className="text-muted text-sm px-4 text-center">Selecione o ativo e clique <b className="mx-1">Analisar</b> para o mapa térmico.</span>}
            {res?.hotspot && (
              <div className="absolute w-6 h-6 -ml-3 -mt-3 rounded-full border-2 border-white animate-pulse"
                style={{ left: `${res.hotspot[0] * 100}%`, top: `${res.hotspot[1] * 100}%` }} title="hotspot" />
            )}
            <video ref={vidRef} className="hidden" playsInline muted />
          </div>
          {res && (
            <div className={"mt-3 shrink-0 rounded-card border px-3 py-2 flex items-center gap-3 flex-wrap " + SEV[res.severity].cls}>
              <span className="font-bold">{SEV[res.severity].label}</span>
              <span className="text-sm">T_max <b>{res.t_max}°C</b></span>
              <span className="text-sm">T_méd {res.t_avg}°C</span>
              {res.baseline != null && <span className="text-sm">ΔT {res.delta_t}°C (base {res.baseline}°C)</span>}
              {res.trend_c_per_week > 0 && <span className="text-sm">↗ {res.trend_c_per_week}°C/sem</span>}
              {res.lead_days != null && <span className="text-sm ml-auto">⏳ ~{res.lead_days} dia(s) até o limite</span>}
            </div>
          )}
        </section>

        {/* Tendência + KPIs */}
        <aside className="bg-panel rounded-card border border-edge p-4 overflow-y-auto scroll-thin space-y-4">
          {kpis && (
            <section className="border-b border-edge pb-3">
              <h3 className="text-xs uppercase tracking-wider text-muted mb-2">KPIs preditivos (CLD_)</h3>
              <div className="grid grid-cols-2 gap-1.5 text-sm">
                <div className="rounded border border-edge bg-edge/40 px-2 py-1"><div className="text-[10px] text-muted uppercase">Ativos</div><div className="font-bold">{kpis.assets}</div></div>
                <div className="rounded border border-edge bg-edge/40 px-2 py-1"><div className="text-[10px] text-muted uppercase">Em risco</div><div className="font-bold text-warn">{kpis.CLD_Assets_At_Risk}</div></div>
              </div>
              <div className="flex flex-wrap gap-1 mt-2">
                {Object.entries(kpis.CLD_Hotspots_By_Severity).map(([s, n]) => (
                  <span key={s} className={"text-[10px] px-2 py-0.5 rounded-full border " + (SEV[s as Severity]?.cls ?? "border-edge text-muted")}>{s}: {n}</span>
                ))}
              </div>
            </section>
          )}
          <section>
            <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Tendência de T_max ({trend.length})</h3>
            {trend.length < 2 ? <p className="text-xs text-muted">Analise o ativo algumas vezes para ver a tendência.</p> : (
              <>
                <div className="flex items-end gap-0.5 h-24 border-b border-l border-edge p-1">
                  {trend.map((r, i) => {
                    const h = maxT > minT ? ((r.t_max - minT) / (maxT - minT)) * 100 : 50;
                    return <div key={i} className={"flex-1 rounded-t " + (SEV[r.severity]?.cls.split(" ")[1]?.replace("text", "bg") ?? "bg-accent")}
                      style={{ height: `${Math.max(4, h)}%` }} title={`${r.t_max}°C · ${r.severity}`} />;
                  })}
                </div>
                <p className="text-[10px] text-muted mt-1">{minT.toFixed(0)}–{maxT.toFixed(0)}°C · {trend.length} leitura(s)</p>
              </>
            )}
          </section>
        </aside>
      </div>
    </div>
  );
}
