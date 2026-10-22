import { useState } from "react";
import { useStore, type View } from "../store/useStore";
import { inferOnce } from "../api/client";
import { classifyImage } from "../api/classify";
import { anomalyScore, anomalyFitImages } from "../api/anomaly";
import { faceIdentify } from "../api/face";
import { thermoAnalyze } from "../api/thermo";
import { AUG_KINDS, MODALITIES, applyModality, augment } from "../lib/imgsim";
import { STATUS_LABEL, TECHS } from "../lib/industriaSpec";
import type { TaskConfig } from "../types";

// Categoria visual + tipo de execução por tecnologia.
type Kind = "detect" | "classify" | "describe" | "anomaly" | "augment" | "modality" | "face" | "thermo" | "track" | "module";
const CFG: Record<string, { kind: Kind; cat: "edge" | "vlm" | "layer"; tag: string; view?: View }> = {
  yolo: { kind: "detect", cat: "edge", tag: "Detecta + conta objetos" },
  cnn: { kind: "classify", cat: "edge", tag: "Classifica a cena (MobileNet)" },
  vit: { kind: "classify", cat: "edge", tag: "Transformer global (ViT-B/16)" },
  anomaly: { kind: "anomaly", cat: "edge", tag: "Desvio do normal (sem rótulo)" },
  edge: { kind: "detect", cat: "edge", tag: "Inferência local, latência ms" },
  vlm: { kind: "describe", cat: "vlm", tag: "Descreve o ciclo (Claude)" },
  synthetic: { kind: "augment", cat: "layer", tag: "Gera dados de treino" },
  imaging: { kind: "modality", cat: "layer", tag: "Simula térmica/IR/raio-X/3D" },
  // 3.9–3.13 (novas)
  tracking: { kind: "track", cat: "edge", tag: "Identidade no tempo · 1 frame = detecção (fluxo: modo RASTREAR)" },
  facial: { kind: "face", cat: "edge", tag: "Identifica operador (1:N, edge · template)" },
  thermo: { kind: "thermo", cat: "edge", tag: "Hotspot / ΔT (pseudo-radiométrico)" },
  metrology: { kind: "module", cat: "edge", tag: "Medição com pontos (interativo)", view: "metrologia" },
  iamac: { kind: "module", cat: "vlm", tag: "Copiloto RAG + flywheel", view: "iamac" },
  automation: { kind: "module", cat: "edge", tag: "Conector OT (PLC/IHM) · OEE · read-only", view: "automacao" },
};
const CAT_RING: Record<string, string> = {
  edge: "border-accent/40 hover:border-accent",
  vlm: "border-warn/40 hover:border-warn",
  layer: "border-muted/40 hover:border-muted border-dashed",
};
const CAT_DOT: Record<string, string> = { edge: "bg-accent", vlm: "bg-warn", layer: "bg-muted" };

function detectTask(): TaskConfig {
  return { mode: "DETECTAR", params: { mode: "DETECTAR", classes_alvo: [], conf_threshold: 0.3, max_det: 50, notificar: false, notificar_classes: [] } };
}
function describeTask(preferEdge: boolean): TaskConfig {
  return { mode: "DESCREVER", prompt: "Descreva a cena e aponte riscos.", params: { mode: "DESCREVER", foco: null, nivel_detalhe: "medio", prefer_edge: preferEdge } };
}

export interface TechRunner {
  tech: string; setTech: (t: string) => void;
  run: () => void; fitAnomaly: () => void;
  running: boolean; fitting: boolean;
  result: { kind: Kind; data: any } | null;
  shot: string | null; err: string | null;
  useToken: boolean; setUseToken: (b: boolean) => void;
}

export function useTechRunner(captureCurrent: () => Promise<string | null>): TechRunner {
  const caps = useStore((s) => s.capabilities);
  const [tech, setTech] = useState("yolo");
  const [running, setRunning] = useState(false);
  const [fitting, setFitting] = useState(false);
  const [result, setResult] = useState<{ kind: Kind; data: any } | null>(null);
  const [shot, setShot] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [useToken, setUseToken] = useState(false);

  const sid = () => {
    const s = useStore.getState();
    return s.sourceMode === "device" ? (s.sourceId || "device")
      : s.selectedCameraId ? `cam:${s.selectedCameraId}` : "ip_camera";
  };

  const run = async () => {
    const cfg = CFG[tech];
    if (cfg.kind === "module") { setErr("Tecnologia interativa — abra o módulo dedicado."); return; }
    setErr(null); setRunning(true); setResult(null);
    try {
      const b64 = await captureCurrent();
      if (!b64) { setErr("Sem frame — inicie a câmera/fonte no preview."); return; }
      setShot(`data:image/jpeg;base64,${b64}`);
      if (cfg.kind === "face") {
        setResult({ kind: "face", data: await faceIdentify(b64) });
      } else if (cfg.kind === "thermo") {
        setResult({ kind: "thermo", data: await thermoAnalyze(`studio-${sid().replace(/[^a-zA-Z0-9_-]/g, "_")}`, b64) });
      } else if (cfg.kind === "track") {
        setResult({ kind: "track", data: await inferOnce(b64, detectTask(), sid()) });
      } else if (cfg.kind === "augment") {
        const url = `data:image/jpeg;base64,${b64}`;
        setResult({ kind: "augment", data: await Promise.all(AUG_KINDS.map(async (k) => ({ label: k, src: await augment(url, k) }))) });
      } else if (cfg.kind === "modality") {
        const url = `data:image/jpeg;base64,${b64}`;
        setResult({ kind: "modality", data: await Promise.all(MODALITIES.map(async (m) => ({ label: `${m.label}`, src: await applyModality(url, m.kind) }))) });
      } else if (cfg.kind === "classify") {
        setResult({ kind: "classify", data: await classifyImage(b64, tech === "vit" ? "vit" : "cnn", 5) });
      } else if (cfg.kind === "anomaly") {
        setResult({ kind: "anomaly", data: await anomalyScore(sid(), b64) });
      } else {
        const task = cfg.kind === "describe" ? describeTask(!(useToken && !!caps?.vlm)) : detectTask();
        setResult({ kind: cfg.kind, data: await inferOnce(b64, task, sid()) });
      }
    } catch (e) { setErr(String((e as Error)?.message ?? e)); }
    finally { setRunning(false); }
  };

  const fitAnomaly = async () => {
    setErr(null); setFitting(true);
    try {
      const frames: string[] = [];
      for (let i = 0; i < 6; i++) { const b = await captureCurrent(); if (b) frames.push(b); await new Promise((r) => setTimeout(r, 350)); }
      if (frames.length < 2) { setErr("Capture falhou — fonte ativa?"); return; }
      const r = await anomalyFitImages(sid(), frames);
      setErr(r.ok ? null : (r.message || "falha no fit"));
      if (r.ok) setResult(null);
    } catch (e) { setErr(String((e as Error)?.message ?? e)); }
    finally { setFitting(false); }
  };

  return { tech, setTech, run, fitAnomaly, running, fitting, result, shot, err, useToken, setUseToken };
}

// ── Painel esquerdo: grade visual das tecnologias ──────────────────────────
export function TechSelector({ r }: { r: TechRunner }) {
  const caps = useStore((s) => s.capabilities);
  const setView = useStore((s) => s.setView);
  const cur = TECHS.find((t) => t.id === r.tech)!;
  const cfg = CFG[r.tech];
  const isVlm = cfg.kind === "describe";
  const isModule = cfg.kind === "module";

  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Tecnologias industriais</h3>
        <div className="grid grid-cols-2 gap-2">
          {TECHS.filter((t) => CFG[t.id]).map((t) => {
            const c = CFG[t.id];
            const sel = r.tech === t.id;
            return (
              <button key={t.id} onClick={() => r.setTech(t.id)} title={t.aplicacao}
                className={"relative text-left rounded-card border p-2 transition-all " +
                  (sel ? "border-accent bg-accent/10 ring-1 ring-accent" : "bg-edge " + CAT_RING[c.cat])}>
                <span className={"absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full " + CAT_DOT[c.cat]} />
                <div className="text-lg leading-none">{t.icon}</div>
                <div className="text-[11px] font-semibold mt-1 leading-tight">{t.nome.split(" ")[0]}</div>
                <div className="text-[9px] text-muted leading-tight">{t.num}</div>
              </button>
            );
          })}
        </div>
      </div>

      <div className="vd-surface border border-edge rounded-card p-3">
        <div className="flex items-center gap-2">
          <span className="text-lg">{cur.icon}</span>
          <span className="text-sm font-bold">{cur.num} {cur.nome}</span>
        </div>
        <p className="text-[11px] text-muted mt-1">{cfg.tag}</p>
        <span className={"inline-block mt-1 text-[10px] px-2 py-0.5 rounded-full " + STATUS_LABEL[cur.vdStatus].cls}>{STATUS_LABEL[cur.vdStatus].txt}</span>

        {isVlm && (
          <label className="flex items-center gap-2 text-[11px] text-muted cursor-pointer mt-2">
            <input type="checkbox" checked={r.useToken && !!caps?.vlm} disabled={!caps?.vlm} onChange={(e) => r.setUseToken(e.target.checked)} />
            Usar IA (token Claude){!caps?.vlm ? " — sem token: local" : ""}
          </label>
        )}

        <div className="flex gap-2 mt-3">
          {isModule ? (
            <button onClick={() => cfg.view && setView(cfg.view)}
              className="flex-1 px-3 py-2 rounded-card text-sm font-semibold bg-accent text-onaccent hover:brightness-110">
              ↗ Abrir módulo
            </button>
          ) : (
            <button onClick={r.run} disabled={r.running}
              className="flex-1 px-3 py-2 rounded-card text-sm font-semibold bg-accent text-onaccent hover:brightness-110 disabled:opacity-50">
              {r.running ? "Processando…" : "▶ Testar na fonte"}
            </button>
          )}
          {r.tech === "anomaly" && (
            <button onClick={r.fitAnomaly} disabled={r.fitting} title="Capturar 6 frames normais"
              className="px-3 py-2 rounded-card text-sm border border-edge bg-edge hover:border-accent disabled:opacity-50">
              {r.fitting ? "…" : "📚"}
            </button>
          )}
        </div>
        {r.err && <p className="text-[11px] text-nok mt-2">⚠ {r.err}</p>}
        <p className="text-[10px] text-muted mt-2">{isModule ? "Tecnologia interativa — abre o módulo dedicado." : "Roda na fonte atual do Estúdio (dispositivo/câmera/tela). Edge = sem token."}</p>
      </div>
    </div>
  );
}

// ── Painel direito: resultado por tipo ─────────────────────────────────────
export function TechResultView({ r }: { r: TechRunner }) {
  if (!r.result) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-center text-muted gap-2 px-4">
        <span className="text-3xl">🧪</span>
        <p className="text-sm">Escolha uma tecnologia e clique <b className="text-text">Testar na fonte</b>.</p>
        <p className="text-[11px]">Resultado real na imagem ao vivo do Estúdio.</p>
      </div>
    );
  }
  const { kind, data } = r.result;
  return (
    <div className="h-full overflow-y-auto scroll-thin space-y-3">
      <h3 className="text-xs uppercase tracking-wider text-muted">Resultado</h3>
      {r.shot && <img src={r.shot} className="w-full rounded-card border border-edge" alt="frame analisado" />}

      {(kind === "detect" || kind === "track") && <DetectRes data={data} />}
      {kind === "classify" && <ClassifyRes data={data} />}
      {kind === "anomaly" && <AnomalyRes data={data} />}
      {kind === "describe" && <DescribeRes data={data} />}
      {kind === "face" && <FaceRes data={data} />}
      {kind === "thermo" && <ThermoRes data={data} />}
      {(kind === "augment" || kind === "modality") && <LayerRes items={data} kind={kind} />}
      {kind === "track" && <p className="text-[11px] text-muted">Fluxo (identidade no tempo, sentido, dwell, contagem por ID) roda no modo <b>RASTREAR</b>.</p>}
    </div>
  );
}

function Meta({ model, type, lat }: { model?: string; type?: string; lat?: number }) {
  return <div className="text-[10px] text-muted flex gap-2 flex-wrap">
    {model && <span>{model}</span>}{type && <span className={"px-1.5 rounded " + (type === "edge" ? "bg-accent-2/20 text-accent-2" : "bg-warn/20 text-warn")}>{type}</span>}
    {lat != null && <span>· {lat}ms</span>}
  </div>;
}

function DetectRes({ data }: { data: any }) {
  const c = data.result?.contagens ?? {};
  return <div className="vd-surface border border-edge rounded-card p-3 space-y-2">
    <Meta model={data.model_name} type={data.model_type} lat={data.latency_ms} />
    <p className="text-2xl font-bold text-accent">{data.result?.total ?? 0}<span className="text-xs text-muted font-normal"> objeto(s)</span></p>
    <div className="flex flex-wrap gap-1.5">{Object.entries(c).map(([k, n]: any) => <span key={k} className="text-xs px-2 py-0.5 rounded bg-edge border border-edge">{k}: <b>{n}</b></span>)}</div>
  </div>;
}
function ClassifyRes({ data }: { data: any }) {
  if (!data.supported) return <p className="text-xs text-warn vd-surface border border-edge rounded-card p-3">{data.message}</p>;
  return <div className="vd-surface border border-edge rounded-card p-3 space-y-1">
    <Meta model={data.backbone} type="edge" lat={data.latency_ms} />
    {(data.results ?? []).map((x: any, i: number) => (
      <div key={i} className="flex items-center gap-2 text-sm">
        <span className={"w-28 truncate " + (i === 0 ? "text-text font-semibold" : "text-muted")}>{x.label}</span>
        <div className="flex-1 h-2 bg-edge rounded overflow-hidden"><div className="h-full bg-accent" style={{ width: `${Math.min(100, x.conf * 100)}%` }} /></div>
        <span className="text-xs font-mono w-9 text-right">{(x.conf * 100).toFixed(0)}%</span>
      </div>
    ))}
  </div>;
}
function AnomalyRes({ data }: { data: any }) {
  if (!data.fitted) return <p className="text-xs text-warn vd-surface border border-edge rounded-card p-3">{data.message || "Perfil não treinado"} — clique 📚 p/ treinar a cena normal e teste de novo.</p>;
  return <div className="vd-surface border border-edge rounded-card p-3 space-y-1">
    <p className="text-2xl font-bold" style={{ color: data.anomalo ? "var(--nok)" : "var(--ok)" }}>{data.anomaly_score}</p>
    <p className={data.anomalo ? "text-nok text-sm" : "text-ok text-sm"}>{data.anomalo ? "ANOMALIA — desvio do normal" : "NORMAL"}</p>
    <p className="text-[10px] text-muted">dist {data.distance} · τ {data.tau} · refs {data.n_ref}</p>
  </div>;
}
function DescribeRes({ data }: { data: any }) {
  const al = data.result?.alertas ?? [];
  return <div className="vd-surface border border-edge rounded-card p-3 space-y-2">
    <Meta model={data.model_name} type={data.model_type} lat={data.latency_ms} />
    <p className="text-sm text-text">{data.result?.descricao || "—"}</p>
    {al.length > 0 && <p className="text-xs text-warn">⚠ {al.join(" · ")}</p>}
  </div>;
}
function FaceRes({ data }: { data: any }) {
  if (!data.ok) return <p className="text-xs text-warn vd-surface border border-edge rounded-card p-3">{data.message}</p>;
  const ok = data.matched;
  return <div className="vd-surface border border-edge rounded-card p-3 space-y-1">
    <p className={"text-lg font-bold " + (ok ? "text-ok" : data.live === false ? "text-nok" : "text-warn")}>
      {ok ? `✓ ${data.name}` : data.live === false ? "⚠ liveness/qualidade" : "não reconhecido"}
    </p>
    <p className="text-[11px] text-muted">faces {data.faces ?? 0} · score {data.score ?? "—"} (≥ {data.threshold ?? "—"}) · cadastro/gestão em Acesso &amp; Regras</p>
  </div>;
}
function ThermoRes({ data }: { data: any }) {
  const sevCls: Record<string, string> = { NORMAL: "text-ok", OBSERVAR: "text-accent-2", AGIR: "text-warn", CRITICO: "text-nok" };
  return <div className="vd-surface border border-edge rounded-card p-3 space-y-2">
    {data.thermal_b64 && <img src={`data:image/jpeg;base64,${data.thermal_b64}`} className="w-full rounded-card border border-edge" alt="térmico" />}
    <p className={"text-lg font-bold " + (sevCls[data.severity] ?? "text-text")}>{data.severity} · T_max {data.t_max}°C</p>
    <p className="text-[11px] text-muted">T_méd {data.t_avg}°C{data.baseline != null ? ` · ΔT ${data.delta_t}` : ""}{data.trend_c_per_week ? ` · ↗ ${data.trend_c_per_week}°C/sem` : ""} · baseline/tendência no módulo Termografia</p>
  </div>;
}
function LayerRes({ items, kind }: { items: { label: string; src: string }[]; kind: string }) {
  return <div>
    <p className="text-[11px] text-muted mb-2">{kind === "augment" ? "Dados sintéticos (treino offline)" : "Modalidades simuladas (troca de sensor no CAPTURE)"}</p>
    <div className="grid grid-cols-2 gap-2">
      {items.map((v, i) => <div key={i} className="border border-edge rounded-card overflow-hidden"><img src={v.src} className="w-full aspect-video object-cover" alt={v.label} /><div className="px-2 py-1 text-[10px] text-muted truncate">{v.label}</div></div>)}
    </div>
  </div>;
}
