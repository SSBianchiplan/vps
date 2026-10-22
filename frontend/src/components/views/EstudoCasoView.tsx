import { useEffect, useRef, useState } from "react";
import { useStore } from "../../store/useStore";
import { snapshot } from "../../api/cameras";
import { captureFrame } from "../../lib/capture";
import { inferOnce } from "../../api/client";
import { anomalyFit, anomalyScore, type AnomalyScore } from "../../api/anomaly";
import { classifyImage, type ClassifyResult } from "../../api/classify";
import { faceIdentify } from "../../api/face";
import { thermoAnalyze } from "../../api/thermo";
import { iaInsights } from "../../api/iamac";
import { otSimulate, otStatus } from "../../api/automation";
import { STATUS_LABEL, TECHS } from "../../lib/industriaSpec";
import { AUG_KINDS, MODALITIES, applyModality, augment } from "../../lib/imgsim";
import type { InferenceResult, TaskConfig } from "../../types";
import { btnPrimaryCls } from "../../lib/ui";

type SimKind = "detect" | "classify" | "describe" | "edge" | "anomaly" | "augment" | "modality" | "face" | "thermo" | "metro" | "iagen" | "ot";

const SIM: Record<string, SimKind> = {
  cnn: "classify", yolo: "detect", tracking: "detect", vit: "classify", anomaly: "anomaly",
  vlm: "describe", edge: "edge", synthetic: "augment", imaging: "modality", facial: "face", thermo: "thermo", metrology: "metro", iamac: "iagen", automation: "ot",
};

const ISA95 = [
  ["L0", "Sensor/câmera + iluminação + trigger", "Câmera IP (RGB, IR-cut ONVIF)"],
  ["L1", "Edge device (inferência)", "YOLO11 / VLM local"],
  ["L2", "PLC / controlador", "Atuação — não conectado (piloto)"],
  ["L3", "MES / Historian", "Eventos + Gravações"],
  ["L4", "ERP / BI", "Painel / KPIs"],
];

// Motor aplicável por tecnologia: local (edge), ia (VLM), both (escolha), na (client-side).
const MOTOR_BY_TECH: Record<string, "local" | "ia" | "both" | "na"> = {
  cnn: "local", yolo: "local", tracking: "local", facial: "local", thermo: "local", metrology: "local", iamac: "local", automation: "local", edge: "local", anomaly: "local", vit: "local",
  vlm: "both", synthetic: "na", imaging: "na",
};

interface Run {
  tech: string; num: string; motor: string; pipeline?: string; model_type?: string;
  latency?: number; result: string; detail: string; ts: string;
}

function detectTask(): TaskConfig {
  return { mode: "DETECTAR", params: { mode: "DETECTAR", classes_alvo: [], conf_threshold: 0.3, max_det: 50, notificar: false, notificar_classes: [] } };
}
function describeTask(alvo: string[], preferEdge: boolean): TaskConfig {
  const foco = alvo.length ? `a cena e a presença de ${alvo.join(", ")}` : "a cena e o ciclo";
  return { mode: "DESCREVER", prompt: `Foque em: ${foco}. Aponte anomalias/riscos.`, params: { mode: "DESCREVER", foco, nivel_detalhe: "medio", prefer_edge: preferEdge } };
}

function buildReport(runs: Run[], camName: string) {
  const inferRuns = runs.filter((r) => r.latency != null);
  const edge = inferRuns.filter((r) => r.model_type === "edge");
  const vlm = inferRuns.filter((r) => r.model_type === "vlm");
  const avg = (a: Run[]) => (a.length ? Math.round(a.reduce((s, r) => s + (r.latency || 0), 0) / a.length) : 0);
  const flagged = runs.filter((r) => /ALERTA|FAIL|ANOMALIA/i.test(r.result));
  const techsRun = Array.from(new Set(runs.map((r) => `${r.num} ${r.tech}`)));

  const findings: string[] = [];
  if (edge.length) findings.push(`Edge (YOLO): latência média ${avg(edge)} ms — apto a decisão peça-a-peça (<200 ms, §2).`);
  if (vlm.length) findings.push(`VLM (Claude): latência média ${avg(vlm)} ms — nível de ciclo (segundos), não de peça.`);
  if (flagged.length) findings.push(`${flagged.length} simulação(ões) sinalizaram desvio: ${flagged.map((r) => `${r.tech}→${r.result}`).join("; ")}.`);
  else if (inferRuns.length) findings.push("Nenhum desvio sinalizado nas simulações de inferência (cena nominal).");
  const lowDetect = edge.some((r) => /vazio/.test(r.detail));
  if (lowDetect) findings.push("Baixa taxa de detecção em alguma cena — verifique iluminação/IR (§4.3) ou use Anomalia (3.4) p/ desvios sem rótulo.");
  if (runs.some((r) => /modalidades/.test(r.result))) findings.push("Imageamento (3.8) é troca de sensor no CAPTURE — térmica/raio-X/3D exigem hardware dedicado.");
  if (runs.some((r) => r.tech.toLowerCase().includes("rastre"))) findings.push("Rastreamento (3.9): a simulação aqui é por frame (detecção). Fluxo real (identidade no tempo, sentido, dwell/cycle time, contagem sem duplicidade) roda no Estúdio → modo RASTREAR sobre o stream.");
  if (runs.some((r) => r.tech.toLowerCase().includes("facial"))) findings.push("Reconhecimento Facial (3.10): identificação 1:N por snapshot (edge, template não foto). Login/cadastro consentido e galeria revogável ficam no módulo Reconhecimento Facial. Biometria é dado sensível (LGPD) — opt-in + fallback PIN/crachá obrigatórios.");
  if (runs.some((r) => r.tech.toLowerCase().includes("termog"))) findings.push("Termografia (3.11): leitura pseudo-radiométrica por snapshot. Baseline por ativo, tendência (°C/sem) e predição (MANUTENÇÃO RECOMENDADA → APS) ficam no módulo Termografia. Medição REAL exige câmera FLIR radiométrica (temperatura por pixel).");
  if (runs.some((r) => r.tech.toLowerCase().includes("metrolog"))) findings.push("Metrologia (3.12): medição é interativa (clicar a cota). Calibração rastreável px→mm, tolerância → CONFORME/NÃO CONFORME + incerteza e Cpk ficam no módulo Metrologia. Precisão industrial: óptica telecêntrica + bordas sub-pixel.");

  const rec = [
    "Vigilância/contagem peça-a-peça → **YOLO (3.2)** no **Edge (3.6)** — ms, sem token.",
    "Auditoria de ciclo/segurança/contexto → **VLM (3.5)**.",
    "Defeito raro/intrusão inédita (sem rótulo) → **Anomalia (3.4)** com human-in-the-loop.",
    "Decisão síncrona com a linha → **Edge (3.6)** sempre; payload rico → MES via TCP/IP.",
  ];
  const verdict = flagged.length ? "⚠ ATENÇÃO — desvios detectados" : (inferRuns.length ? "✅ NOMINAL" : "— sem inferência");

  const md = [
    `# Relatório de simulação — VisionDesk Indústria`,
    `**Câmera:** ${camName}  ·  **Simulações:** ${runs.length}  ·  **Veredito:** ${verdict}`,
    ``, `## Tecnologias simuladas`, ...techsRun.map((t) => `- ${t}`),
    ``, `## Execuções`,
    `| Tech | Motor | Pipeline | Latência | Resultado |`, `|---|---|---|---|---|`,
    ...runs.map((r) => `| ${r.num} ${r.tech} | ${r.motor} | ${r.pipeline ?? "-"} | ${r.latency != null ? r.latency + "ms" : "-"} | ${r.result} |`),
    ``, `## Diagnóstico`, ...findings.map((f) => `- ${f}`),
    ``, `## Recomendação (matriz §7)`, ...rec.map((r) => `- ${r.replace(/\*\*/g, "")}`),
  ].join("\n");

  return { findings, rec, verdict, md, flagged: flagged.length };
}

function Stage({ n, tag, title, badge, children }: { n: number; tag: string; title: string; badge?: string; children: React.ReactNode }) {
  return (
    <div className="vd-surface border border-edge rounded-card p-3">
      <div className="flex items-center gap-2 mb-1.5">
        <span className="w-5 h-5 rounded-full bg-accent text-onaccent text-[11px] flex items-center justify-center font-bold">{n}</span>
        <span className="font-mono text-xs text-muted">{tag}</span>
        <span className="font-bold text-sm">{title}</span>
        {badge && <span className="ml-auto text-[10px] px-2 py-0.5 rounded-full bg-accent/15 text-accent">{badge}</span>}
      </div>
      <div className="text-sm text-text">{children}</div>
    </div>
  );
}

export function EstudoCasoView() {
  const saved = useStore((s) => s.savedCameras);
  const caps = useStore((s) => s.capabilities);
  const setView = useStore((s) => s.setView);
  const [camId, setCamId] = useState<string>("");
  const [techId, setTechId] = useState("yolo");
  const [alvoStr, setAlvoStr] = useState("person, dog");
  const [running, setRunning] = useState(false);
  const [shot, setShot] = useState<string | null>(null);
  const [res, setRes] = useState<InferenceResult | null>(null);
  const [anom, setAnom] = useState<AnomalyScore | null>(null);
  const [clf, setClf] = useState<ClassifyResult | null>(null);
  const [fitting, setFitting] = useState(false);
  const [variants, setVariants] = useState<{ label: string; src: string }[]>([]);
  const [motor, setMotor] = useState<"ia" | "local">("local");
  const [runs, setRuns] = useState<Run[]>([]);
  const [err, setErr] = useState<string | null>(null);

  // Fonte unificada: TODOS os dispositivos (IP salvas + drone/osmo + dispositivo local + tela).
  const activeStream = useStore((s) => s.activeStream);
  const activeDeviceId = useStore((s) => s.activeDeviceId);
  const sourceId = useStore((s) => s.sourceId);
  const vidRef = useRef<HTMLVideoElement | null>(null);
  useEffect(() => {
    const v = vidRef.current; if (!v) return;
    if (activeStream) { v.srcObject = activeStream; v.play().catch(() => undefined); } else v.srcObject = null;
  }, [activeStream]);

  type Src = { id: string; label: string; kind: "ip" | "aerial" | "device" | "screen"; cameraId?: string; url?: string; sid: string };
  const sources: Src[] = [
    ...saved.map((c) => ({ id: `cam:${c.id}`, label: `📷 ${c.name}`, kind: "ip" as const, cameraId: c.id, sid: `cam:${c.id}` })),
    { id: "aer:drone", label: "🛸 Drone (aéreo)", kind: "aerial" as const, url: "rtsp://localhost:8554/drone_neo2", sid: "drone_neo2" },
    { id: "aer:osmo", label: "🎥 Osmo (vídeo)", kind: "aerial" as const, url: "rtsp://localhost:8554/osmo_pocket", sid: "osmo_pocket" },
    ...(activeStream ? [{
      id: "dev:active",
      label: activeDeviceId === "screen" ? "🖥 Tela (captura)" : `💻 Dispositivo (${sourceId})`,
      kind: (activeDeviceId === "screen" ? "screen" : "device") as "screen" | "device",
      sid: activeDeviceId === "screen" ? "screen" : sourceId,
    }] : []),
  ];
  useEffect(() => { if (!camId && sources.length) setCamId(sources[0].id); /* eslint-disable-next-line */ }, [saved.length, !!activeStream]);
  const src = sources.find((s) => s.id === camId) ?? sources[0] ?? null;

  // Captura um frame da fonte selecionada (backend p/ IP/aéreo; client-side p/ device/tela).
  const captureB64 = async (): Promise<{ b64: string; sid: string } | null> => {
    if (!src) return null;
    if (src.kind === "ip") return { b64: (await snapshot({ cameraId: src.cameraId! })).image_b64, sid: src.sid };
    if (src.kind === "aerial") return { b64: (await snapshot({ url: src.url! })).image_b64, sid: src.sid };
    const b = vidRef.current ? captureFrame(vidRef.current, 1280) : null;  // device/tela (getUserMedia/getDisplayMedia)
    return b ? { b64: b, sid: src.sid } : null;
  };
  const alvo = alvoStr.split(/[,\s]+/).map((x) => x.trim().toLowerCase()).filter(Boolean);
  const tech = TECHS.find((t) => t.id === techId)!;
  const kind = SIM[techId];
  const isInfer = kind === "detect" || kind === "describe" || kind === "edge";
  const isAnom = kind === "anomaly";
  const isClassify = kind === "classify";
  const motorCap = MOTOR_BY_TECH[techId];
  // motor efetivo: techs edge-only ficam em local; "both" respeita o toggle (sem token → local).
  const useIA = motorCap === "ia" || (motorCap === "both" && motor === "ia" && !!caps?.vlm);
  const pushRun = (r: Omit<Run, "ts">) => setRuns((p) => [{ ...r, ts: new Date().toLocaleTimeString() }, ...p].slice(0, 20));

  const run = async () => {
    if (kind === "iagen") {   // iaMAC: agente de ganhos (não precisa de frame)
      setErr(null); setRunning(true);
      try { const ins = await iaInsights(); pushRun({ tech: tech.nome, num: tech.num, motor: "RAG/agente", result: `${ins.length} insight(s)`, detail: ins[0]?.text || "abra o módulo iaMAC" }); }
      catch (e) { setErr(String((e as Error)?.message ?? e)); } finally { setRunning(false); }
      return;
    }
    if (kind === "ot") {      // Automação: simula leitura PLC/IHM (não precisa de frame)
      setErr(null); setRunning(true);
      try { const r = await otSimulate(); const k = await otStatus(); pushRun({ tech: tech.nome, num: tech.num, motor: "conector OT", result: `${r.count} evento(s)`, detail: `OEE ${k.CLD_OEE}% · disp ${k.CLD_Machine_Availability}% · prod ${k.CLD_Production_Count}` }); }
      catch (e) { setErr(String((e as Error)?.message ?? e)); } finally { setRunning(false); }
      return;
    }
    if (!src) return;
    setErr(null); setRunning(true); setRes(null); setAnom(null); setClf(null); setVariants([]);
    try {
      const cap = await captureB64();
      if (!cap) { setErr("fonte sem frame (conecte/compartilhe a fonte e tente de novo)"); setRunning(false); return; }
      const s = { image_b64: cap.b64 };
      const url = `data:image/jpeg;base64,${s.image_b64}`;
      setShot(url);
      if (kind === "classify") {
        const backbone: "cnn" | "vit" = techId === "vit" ? "vit" : "cnn";
        const c = await classifyImage(s.image_b64, backbone, 5);
        setClf(c);
        const top = c.results?.[0];
        pushRun({ tech: tech.nome, num: tech.num, motor: `Local (${backbone === "vit" ? "ViT" : "CNN"})`, latency: c.latency_ms, model_type: "edge", result: top ? `${top.label} ${(top.conf * 100).toFixed(0)}%` : "—", detail: c.backbone || backbone });
      } else if (kind === "augment") {
        const v = await Promise.all(AUG_KINDS.map(async (k) => ({ label: k, src: await augment(url, k) })));
        setVariants(v);
        pushRun({ tech: tech.nome, num: tech.num, motor: "client-side", result: `${v.length} variações`, detail: "augmentations p/ treino offline" });
      } else if (kind === "modality") {
        const v = await Promise.all(MODALITIES.map(async (m) => ({ label: `${m.label} — ${m.reveals}`, src: await applyModality(url, m.kind) })));
        setVariants(v);
        pushRun({ tech: tech.nome, num: tech.num, motor: "client-side", result: `${v.length} modalidades`, detail: "simulação de sensores (térmica/IR/raio-X/3D)" });
      } else if (kind === "anomaly") {
        const a = await anomalyScore(cap.sid, s.image_b64);
        setAnom(a);
        pushRun({ tech: tech.nome, num: tech.num, motor: "local (YOLO emb)", result: a.fitted ? (a.anomalo ? `ANOMALIA ${a.anomaly_score}` : `NORMAL ${a.anomaly_score}`) : "não treinado", detail: a.fitted ? `dist ${a.distance} · τ ${a.tau}` : (a.message || "") });
      } else if (kind === "face") {
        const f = await faceIdentify(s.image_b64);
        const out = !f.ok ? "SEM FACE" : f.matched ? `${f.name} ✓` : f.live === false ? "LIVENESS/QUAL." : "NÃO RECONHECIDO";
        pushRun({ tech: tech.nome, num: tech.num, motor: "local (edge)", result: out, detail: f.ok ? `faces ${f.faces ?? 0} · score ${f.score ?? "—"} (≥ ${f.threshold ?? "—"})` : (f.message || "") });
      } else if (kind === "thermo") {
        const t = await thermoAnalyze(`caso-${src.sid.replace(/[^a-zA-Z0-9_-]/g, "_")}`, s.image_b64);
        pushRun({ tech: tech.nome, num: tech.num, motor: "local (pseudo-radio)", result: t.severity, detail: `T_max ${t.t_max}°C · T_méd ${t.t_avg}°C${t.baseline != null ? ` · ΔT ${t.delta_t}` : ""}` });
      } else if (kind === "metro") {
        pushRun({ tech: tech.nome, num: tech.num, motor: "interativo", result: "→ módulo Metrologia", detail: "medição precisa de pontos (clique a cota) — abra o módulo Metrologia" });
      } else {
        const task = kind === "describe" ? describeTask(alvo, !useIA) : detectTask();
        const r = await inferOnce(s.image_b64, task, cap.sid);
        setRes(r);
        const c: Record<string, number> = (r.result?.contagens as any) ?? {};
        const al: string[] = (r.result?.alertas as any) ?? [];
        const h = Object.entries(c).filter(([k]) => alvo.includes(k.toLowerCase()));
        const out = kind === "describe" ? (al.length ? "ALERTA" : "PASS")
          : (h.length ? "ALERTA/FAIL" : "PASS");
        pushRun({ tech: tech.nome, num: tech.num, motor: r.model_type === "vlm" ? "IA (VLM)" : "Local (edge)", pipeline: r.pipeline, model_type: r.model_type, latency: r.latency_ms, result: String(out), detail: kind === "describe" ? (al.join("; ") || "sem alerta") : Object.entries(c).map(([k, n]) => `${n}×${k}`).join(", ") || "vazio" });
      }
    } catch (e) { setErr(String((e as Error)?.message ?? e)); }
    finally { setRunning(false); }
  };

  const fitAnom = async () => {
    if (!src || src.kind !== "ip" || !src.cameraId) { setErr("Treino de anomalia: selecione uma câmera IP salva."); return; }
    setFitting(true); setErr(null);
    try { const r = await anomalyFit(src.cameraId, 8); setErr(r.ok ? null : (r.message || "falha no fit")); if (r.ok) setAnom(null); }
    catch (e) { setErr(String((e as Error)?.message ?? e)); }
    finally { setFitting(false); }
  };

  // Derivações (modos de inferência).
  const contagens: Record<string, number> = (res?.result?.contagens as any) ?? {};
  const hits = Object.entries(contagens).filter(([c]) => alvo.includes(c.toLowerCase()));
  const total = (res?.result?.total as number) ?? 0;
  const alertas: string[] = (res?.result?.alertas as any) ?? [];

  let fail = false, resultado = "—";
  if (res) {
    if (kind === "describe") { fail = alertas.length > 0; resultado = fail ? "ALERTA" : "PASS"; }
    else { fail = hits.length > 0; resultado = fail ? "ALERTA / FAIL" : "PASS"; }
  } else if (anom?.fitted) {
    fail = !!anom.anomalo; resultado = fail ? "ANOMALIA" : "NORMAL";
  }
  const badge = ({ detect: "YOLO 3.2·Edge 3.6", classify: "CNN 3.1 (via YOLO)", describe: techId === "vit" ? "ViT 3.3 → VLM" : "VLM 3.5", edge: "Edge 3.6", anomaly: "Anomalia 3.4 (sim)", face: "Facial 3.10 (edge)", thermo: "Termografia 3.11 (pseudo)", metro: "Metrologia 3.12", iagen: "iaMAC 3.13", ot: "Automação 3.14" } as Record<string, string>)[kind] ?? "";

  return (
    <div className="h-full overflow-y-auto scroll-thin pr-1">
      {/* espelho oculto do stream ativo (dispositivo/tela) p/ captura client-side */}
      <video ref={vidRef} className="hidden" playsInline muted />
      <div className="max-w-4xl mx-auto space-y-4 pb-8">
        <div>
          <h1 className="text-2xl font-bold">🧪 Estudo de caso — simulação das tecnologias</h1>
          <p className="text-sm text-muted mt-1">
            Escolha uma tecnologia do <button className="text-accent hover:underline" onClick={() => setView("industria")}>catálogo</button> e
            simule-a numa câmera real. Modelos reais locais (YOLO, CNN/MobileNet, ViT, anomalia PatchCore-lite) + VLM; filtros client-side p/ captura/treino (3.7/3.8).
          </p>
        </div>

        {/* Abas das 8 tecnologias (conforme catálogo) */}
        <div className="flex flex-wrap gap-1.5">
          {TECHS.map((t) => (
            <button key={t.id} onClick={() => { setTechId(t.id); setRes(null); setAnom(null); setClf(null); setVariants([]); }}
              className={"px-2.5 py-1.5 rounded-card text-xs font-medium border transition-colors flex items-center gap-1.5 " +
                (techId === t.id ? "bg-accent text-onaccent border-accent" : "bg-edge border-edge hover:border-accent text-text")}>
              <span>{t.icon}</span><span>{t.num} {t.nome}</span>
            </button>
          ))}
        </div>

        {/* Tecnologia selecionada (resumo do catálogo) */}
        <div className="vd-surface border border-edge rounded-card p-3">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-lg">{tech.icon}</span>
            <span className="font-bold text-sm">{tech.num} · {tech.nome}</span>
            <span className={"text-[10px] px-2 py-0.5 rounded-full " + STATUS_LABEL[tech.vdStatus].cls}>{STATUS_LABEL[tech.vdStatus].txt}</span>
          </div>
          <p className="text-xs text-muted mt-1">{tech.aplicacao}</p>
        </div>

        {/* Controles */}
        {saved.length === 0 ? (
          <span className="text-sm text-warn">Nenhuma câmera salva — cadastre em <button className="text-accent underline" onClick={() => setView("cameras")}>Câmeras</button>.</span>
        ) : (
          <div className="space-y-2">
            <div className="flex items-center gap-2 flex-wrap">
              <select className="bg-edge border border-edge rounded px-2 py-1.5 text-sm" value={camId} onChange={(e) => setCamId(e.target.value)}>
                {sources.length === 0 && <option value="">(nenhuma fonte)</option>}
                {sources.map((sx) => <option key={sx.id} value={sx.id}>{sx.label}</option>)}
              </select>
              <button className={btnPrimaryCls} onClick={run} disabled={running}>{running ? "Processando…" : "▶ Rodar simulação"}</button>
              {err && <span className="text-xs text-nok">⚠ {err}</span>}
            </div>

            {/* Motor de inferência — adaptado por tecnologia */}
            {motorCap !== "na" && (
              <div>
                <label className="block text-xs font-medium text-muted mb-1">Motor de inferência</label>
                <div className="flex gap-2">
                  <button type="button" disabled={motorCap === "local"}
                    onClick={() => setMotor("ia")}
                    className={"flex-1 px-2 py-1.5 rounded text-xs border text-left transition-colors " +
                      (useIA ? "border-accent bg-accent/15 text-text" : "border-edge bg-edge text-muted hover:border-accent") +
                      (motorCap === "local" ? " opacity-40 cursor-not-allowed" : "")}>
                    <span className="block font-semibold">🧠 IA (VLM)</span>
                    <span className="block text-[10px] text-muted">{caps?.vlm ? "Claude · mais rico" : "sem token"}</span>
                  </button>
                  <button type="button" disabled={motorCap === "ia"}
                    onClick={() => setMotor("local")}
                    className={"flex-1 px-2 py-1.5 rounded text-xs border text-left transition-colors " +
                      (!useIA ? "border-accent bg-accent/15 text-text" : "border-edge bg-edge text-muted hover:border-accent") +
                      (motorCap === "ia" ? " opacity-40 cursor-not-allowed" : "")}>
                    <span className="block font-semibold">⚡ Local (edge)</span>
                    <span className="block text-[10px] text-muted">YOLO · sem token</span>
                  </button>
                </div>
                <p className="text-[10px] text-muted mt-1">
                  {motorCap === "local" ? "Esta tecnologia roda na borda (sem token)." :
                    motorCap === "ia" ? "Esta tecnologia usa o VLM (token); sem chave, cai no local." :
                      "IA = contexto rico (Claude); Local = YOLO sem token. " + (!caps?.vlm ? "Sem token → local." : "")}
                </p>
              </div>
            )}
            {(kind === "detect" || kind === "describe") && (
              <div className="flex items-center gap-2">
                <label className="text-xs text-muted">Classes-alvo:</label>
                <input className="flex-1 bg-edge border border-edge rounded px-2 py-1 text-sm font-mono" value={alvoStr} onChange={(e) => setAlvoStr(e.target.value)} placeholder="person, dog…" />
              </div>
            )}
            {isAnom && (
              <div className="flex items-center gap-2 flex-wrap">
                <button className="px-3 py-1.5 rounded text-sm border border-edge bg-edge hover:border-accent disabled:opacity-40" onClick={fitAnom} disabled={fitting}>
                  {fitting ? "Treinando…" : "📚 Treinar normais (8 frames)"}
                </button>
                <span className="text-[11px] text-muted">Capture a cena "normal" 1×; depois rode p/ pontuar desvios.</span>
              </div>
            )}
            {kind === "describe" && techId !== "vit" && !caps?.vlm && <p className="text-[11px] text-warn">Sem token — cai no motor local (descrição via YOLO).</p>}
          </div>
        )}

        {/* KPIs (inferência) */}
        {res && isInfer && (
          <div className="grid grid-cols-3 gap-3">
            <div className="vd-surface border border-edge rounded-card p-3">
              <div className="text-[10px] uppercase tracking-wider text-muted">CLD_Inference_Latency_ms</div>
              <div className="text-2xl font-bold text-accent">{res.latency_ms}<span className="text-xs text-muted font-normal"> ms</span></div>
              <div className="text-[10px] text-muted">{res.model_type === "edge" ? "edge (alvo: ms)" : "VLM (alvo: s)"}</div>
            </div>
            <div className="vd-surface border border-edge rounded-card p-3">
              <div className="text-[10px] uppercase tracking-wider text-muted">Result</div>
              <div className={"text-2xl font-bold " + (fail ? "text-nok" : "text-ok")}>{resultado}</div>
            </div>
            <div className="vd-surface border border-edge rounded-card p-3">
              <div className="text-[10px] uppercase tracking-wider text-muted">{kind === "describe" ? "Alertas" : "Objetos"}</div>
              <div className="text-2xl font-bold text-text">{kind === "describe" ? alertas.length : total}</div>
            </div>
          </div>
        )}

        {/* Saída da simulação */}
        {isInfer ? (
          <div className="space-y-2">
            <Stage n={1} tag="CAPTURE" title="Aquisição" badge="L0">
              {shot ? <img src={shot} className="rounded-card border border-edge max-h-48" alt="frame" /> : <span className="text-muted">Frame de {src ? src.label : "—"}.</span>}
            </Stage>
            <Stage n={2} tag="PREPROCESS" title="Normalização" badge="resize/ROI">
              <span className="text-muted">{kind === "describe" ? "Resize ≤1024px (VLM)." : "Resize ≤640px (edge)."}</span>
            </Stage>
            <Stage n={3} tag="INFER" title="Modelo" badge={badge}>
              {res ? (
                <div className="space-y-1">
                  <div className="text-xs text-muted">{res.model_name} · {res.pipeline} · {res.model_type} · {res.latency_ms}ms</div>
                  {kind === "describe" ? (
                    <><p className="text-text">{(res.result?.descricao as string) || "—"}</p>{alertas.length > 0 && <p className="text-warn text-xs">⚠ {alertas.join(" · ")}</p>}</>
                  ) : (
                    Object.keys(contagens).length ? (
                      <div className="flex flex-wrap gap-1.5">
                        {Object.entries(contagens).map(([c, n]) => (
                          <span key={c} className={"text-xs px-2 py-0.5 rounded border " + (alvo.includes(c.toLowerCase()) ? "border-nok text-nok bg-nok/10" : "border-edge bg-edge")}>{c}: <b>{n}</b></span>
                        ))}
                      </div>
                    ) : <span className="text-muted">Nada detectado.</span>
                  )}
                  {kind === "edge" && <p className="text-[11px] text-accent-2 mt-1">⚡ Edge: inferência local, {res.latency_ms}ms, device MPS — sem nuvem, sem token. KPI: CLD_Inference_Latency_ms / Edge_Uptime.</p>}
                </div>
              ) : <span className="text-muted">Rode a simulação.</span>}
            </Stage>
            <Stage n={4} tag="DECIDE" title="Regra" badge="threshold">
              {res ? <span className={fail ? "text-nok" : "text-ok"}>{resultado}{kind === "detect" && hits.length ? ` — alvo: ${hits.map(([c, n]) => `${n}× ${c}`).join(", ")}` : ""}</span>
                : <span className="text-muted">Resultado → PLC/MES.</span>}
            </Stage>
            <Stage n={5} tag="ACT" title="Atuação" badge="L2/L3">
              {res ? (fail ? <span>WhatsApp + Gravação + evento MES{kind === "detect" ? " · PLC reject bit (piloto: n/c)" : ""}.</span> : <span className="text-muted">Sem ação.</span>) : <span className="text-muted">PASS/FAIL → fieldbus; payload → MES.</span>}
            </Stage>
          </div>
        ) : isAnom ? (
          <div className="space-y-2">
            <Stage n={1} tag="CAPTURE" title="Aquisição" badge="L0">
              {shot ? <img src={shot} className="rounded-card border border-edge max-h-48" alt="frame" /> : <span className="text-muted">Frame de {src ? src.label : "—"}.</span>}
            </Stage>
            <Stage n={3} tag="INFER" title="Anomalia (PatchCore-lite)" badge="3.4 · embeddings YOLO">
              {anom ? (
                anom.fitted ? (
                  <div className="space-y-1">
                    <p>Score <b className={anom.anomalo ? "text-nok" : "text-ok"}>{anom.anomaly_score}</b> · dist {anom.distance} · τ {anom.tau} · refs {anom.n_ref}</p>
                    <p className={anom.anomalo ? "text-nok" : "text-ok"}>{anom.anomalo ? "ANOMALIA — desvio do normal aprendido" : "NORMAL — dentro da distribuição"}</p>
                    <p className="text-[10px] text-muted">Sem rótulos de defeito: distância (1−cos) ao banco de normais, calibrada por τ=μ+3σ.</p>
                  </div>
                ) : <p className="text-warn">{anom.message || "Perfil não treinado"} — clique <b>📚 Treinar normais</b> com a cena nominal e rode de novo.</p>
              ) : <span className="text-muted">Treine os normais 1×, depois rode p/ pontuar desvios.</span>}
            </Stage>
            <Stage n={4} tag="DECIDE" title="Threshold adaptativo" badge="τ=μ+3σ">
              {anom?.fitted ? <span className={fail ? "text-nok" : "text-ok"}>{resultado} (dist {anom.anomalo ? ">" : "≤"} τ)</span> : <span className="text-muted">dist &gt; τ → reject + flag p/ revisão humana.</span>}
            </Stage>
            <Stage n={5} tag="ACT" title="Human-in-the-loop" badge="L3">
              <span className="text-muted">Anomalia → flag p/ revisão (primeiras semanas) + gravação; vira rótulo p/ supervisionar depois.</span>
            </Stage>
          </div>
        ) : isClassify ? (
          <div className="space-y-2">
            <Stage n={1} tag="CAPTURE" title="Aquisição" badge="L0">
              {shot ? <img src={shot} className="rounded-card border border-edge max-h-48" alt="frame" /> : <span className="text-muted">Frame de {src ? src.label : "—"}.</span>}
            </Stage>
            <Stage n={3} tag="INFER" title={techId === "vit" ? "ViT-B/16 (transformer)" : "CNN (MobileNetV3)"} badge={techId === "vit" ? "3.3 · ViT" : "3.1 · CNN"}>
              {clf ? (
                clf.supported ? (
                  <div className="space-y-1">
                    <div className="text-xs text-muted">{clf.backbone} · local (edge) · {clf.latency_ms}ms · ImageNet (1000 classes)</div>
                    {(clf.results ?? []).map((r, i) => (
                      <div key={i} className="flex items-center gap-2 text-sm">
                        <span className={"w-28 truncate " + (i === 0 ? "text-text font-semibold" : "text-muted")}>{r.label}</span>
                        <div className="flex-1 h-2 bg-edge rounded overflow-hidden"><div className="h-full bg-accent" style={{ width: `${Math.min(100, r.conf * 100)}%` }} /></div>
                        <span className="text-xs font-mono w-10 text-right">{(r.conf * 100).toFixed(0)}%</span>
                      </div>
                    ))}
                    <p className="text-[10px] text-muted mt-1">Pré-treinado ImageNet (genérico). Em produção: fine-tune do head no defeito-alvo (riscos/trincas/OK-NOK).</p>
                  </div>
                ) : <p className="text-warn">{clf.message}</p>
              ) : <span className="text-muted">Rode p/ classificar o frame (top-5).</span>}
            </Stage>
            <Stage n={4} tag="DECIDE" title="Regra" badge="threshold">
              <span className="text-muted">classe + confiança → threshold → OK/NOK ao PLC (após fine-tune no domínio).</span>
            </Stage>
            <Stage n={5} tag="ACT" title="Atuação" badge="L2/L3">
              <span className="text-muted">Defect_Class + Confidence → MES/Historian; reject bit ao PLC.</span>
            </Stage>
          </div>
        ) : (
          variants.length > 0 && (
            <div>
              <p className="text-xs text-muted mb-2">
                {kind === "augment" ? "📦 Dados sintéticos (§3.7): variações geradas a partir de 1 frame real → expande dataset de treino offline (não toca o runtime)." :
                  "🌈 Imageamento avançado (§3.8): a modalidade troca o sensor no CAPTURE; o restante do pipeline consome o tensor. Aqui, simulação visual do que cada modalidade revela."}
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {shot && <div className="border border-accent rounded-card overflow-hidden"><img src={shot} className="w-full aspect-video object-cover" alt="original" /><div className="px-2 py-1 text-[10px] text-accent">original (RGB)</div></div>}
                {variants.map((v, i) => (
                  <div key={i} className="border border-edge rounded-card overflow-hidden bg-surface">
                    <img src={v.src} className="w-full aspect-video object-cover" alt={v.label} />
                    <div className="px-2 py-1 text-[10px] text-muted truncate">{v.label}</div>
                  </div>
                ))}
              </div>
            </div>
          )
        )}

        {/* Contrato de evento */}
        {res && isInfer && (
          <section className="vd-surface border border-edge rounded-card p-4">
            <h3 className="font-bold text-sm mb-2">📦 GLX_FACT_VISION_EVENT (§6.1)</h3>
            <div className="grid sm:grid-cols-2 gap-x-6 gap-y-1 text-xs font-mono">
              {[
                ["Inspection_ID", res.detection_id],
                ["Timestamp", res.timestamp.slice(0, 19).replace("T", " ")],
                ["Station_ID", src ? src.label : "—"],
                ["Model_Name / Type", `${res.model_name} / ${res.model_type}`],
                ["Result", resultado],
                ["Confidence", res.confidence.toFixed(3)],
                ["Inference_Latency_ms", String(res.latency_ms)],
                ["Tech", `${tech.num} ${tech.nome}`],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between gap-2 border-b border-edge/40 py-0.5">
                  <span className="text-muted">{k}</span><span className="text-text text-right truncate">{v}</span>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* ISA-95 */}
        <section className="vd-surface border border-edge rounded-card p-4">
          <h3 className="font-bold text-sm mb-2">🏗 Mapeamento ISA-95 do piloto</h3>
          <div className="space-y-1">
            {ISA95.map(([lvl, comp, vd]) => (
              <div key={lvl} className="flex gap-2 text-xs items-start py-1 border-b border-edge/40">
                <span className="font-mono font-bold text-accent w-6 shrink-0">{lvl}</span>
                <span className="text-muted w-1/3 shrink-0">{comp}</span>
                <span className="text-text flex-1">{vd}</span>
              </div>
            ))}
          </div>
        </section>

        {/* Relatório & diagnóstico */}
        {runs.length > 0 && (() => {
          const rep = buildReport(runs, src ? src.label : "—");
          const download = () => {
            const blob = new Blob([rep.md], { type: "text/markdown" });
            const a = document.createElement("a"); a.href = URL.createObjectURL(blob);
            a.download = `relatorio-visao-${src?.id?.replace(/[:]/g,"-") ?? "fonte"}.md`; a.click(); URL.revokeObjectURL(a.href);
          };
          return (
            <section className="vd-surface border border-edge rounded-card p-4">
              <div className="flex items-center gap-2 mb-2 flex-wrap">
                <h3 className="font-bold text-sm">📋 Relatório & diagnóstico</h3>
                <span className={"text-[11px] px-2 py-0.5 rounded-full " + (rep.flagged ? "bg-nok/20 text-nok" : "bg-ok/20 text-ok")}>{rep.verdict}</span>
                <span className="ml-auto flex gap-2">
                  <button className="text-xs text-accent hover:underline" onClick={download}>⬇ Baixar .md</button>
                  <button className="text-xs text-muted hover:text-nok" onClick={() => setRuns([])}>limpar</button>
                </span>
              </div>

              <div className="overflow-x-auto mb-3">
                <table className="w-full text-xs">
                  <thead><tr className="text-muted text-left">{["Tech", "Motor", "Pipeline", "Latência", "Resultado", "Hora"].map((h) => <th key={h} className="font-medium pb-1 pr-2">{h}</th>)}</tr></thead>
                  <tbody>
                    {runs.map((r, i) => (
                      <tr key={i} className="border-t border-edge/40">
                        <td className="py-1 pr-2 text-text">{r.num} {r.tech}</td>
                        <td className="py-1 pr-2 text-muted">{r.motor}</td>
                        <td className="py-1 pr-2 text-muted">{r.pipeline ?? "-"}</td>
                        <td className="py-1 pr-2 font-mono">{r.latency != null ? `${r.latency}ms` : "-"}</td>
                        <td className={"py-1 pr-2 " + (/ALERTA|FAIL|ANOMALIA/i.test(r.result) ? "text-nok" : "text-ok")}>{r.result}</td>
                        <td className="py-1 text-muted">{r.ts}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <h4 className="text-xs uppercase tracking-wider text-muted mb-1">Diagnóstico</h4>
              <ul className="text-sm space-y-1 mb-3 list-disc pl-5">
                {rep.findings.map((f, i) => <li key={i} className="text-text">{f}</li>)}
              </ul>
              <h4 className="text-xs uppercase tracking-wider text-muted mb-1">Recomendação (matriz §7)</h4>
              <ul className="text-sm space-y-1 list-disc pl-5">
                {rep.rec.map((r, i) => <li key={i} className="text-muted" dangerouslySetInnerHTML={{ __html: r.replace(/\*\*(.+?)\*\*/g, '<b class="text-text">$1</b>') }} />)}
              </ul>
            </section>
          );
        })()}
      </div>
    </div>
  );
}
