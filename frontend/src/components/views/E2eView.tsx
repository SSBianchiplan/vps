import { useCallback, useEffect, useRef, useState } from "react";
import { runE2e, type E2eResult, type E2eStep } from "../../api/vps";

// Linhagem (esqueleto) — acende conforme os vínculos se formam (igual VPS_Demo_Simulacao).
const NODES = [
  { id: "so", ind: "", lab: "SO", nid: "PV-2026-7781" },
  { id: "proj", ind: "└ ", lab: "PROJ", nid: "PRJ-2026-118" },
  { id: "op", ind: " └ ", lab: "OP", nid: "OP-2026-04412" },
  { id: "pick", ind: "  ├ ", lab: "PICK", nid: "PK-04412-01" },
  { id: "item", ind: "  │ └", lab: "ITEM", nid: "RES-22K ⇄ PO-2026-5512" },
  { id: "occ", ind: "  ├ ", lab: "OCC", nid: "OC-04412-7" },
  { id: "meas", ind: "  ├ ", lab: "MEAS", nid: "MD-04412" },
  { id: "ship", ind: "  └ ", lab: "SHIP", nid: "SH-04412" },
  { id: "inv", ind: "     └", lab: "INV", nid: "NF-2026-3321" },
];
const CAT: Record<string, { l: string; bg: string; fg: string }> = {
  cadastro: { l: "CADASTRO", bg: "#9fb6cc", fg: "#10243a" },
  genese: { l: "GÊNESE", bg: "#e6c34a", fg: "#1c1407" },
  evento: { l: "EVENTO", bg: "#cdbfa6", fg: "#241c10" },
  correcao: { l: "CORREÇÃO", bg: "var(--nok)", fg: "#fff" },
  resolvido: { l: "RESOLVIDO", bg: "var(--ok)", fg: "#fff" },
  vinculo: { l: "VÍNCULO", bg: "#dca93a", fg: "#1c1407" },
  reconc: { l: "RECONCIL.", bg: "var(--ok)", fg: "#fff" },
  fim: { l: "DONE", bg: "var(--ok)", fg: "#fff" },
};
const PILL: Record<string, string> = { ok: "bg-ok/15 text-ok border-ok/50", warn: "bg-nok/15 text-nok border-nok/50", proc: "bg-accent/15 text-accent border-accent/40" };

export function E2eView() {
  const [res, setRes] = useState<E2eResult | null>(null);
  const [shown, setShown] = useState(0);
  const [running, setRunning] = useState(false);
  const timer = useRef<number | undefined>(undefined);

  const stopTimer = () => window.clearInterval(timer.current);
  useEffect(() => () => stopTimer(), []);

  const play = useCallback(async () => {
    stopTimer(); setShown(0); setRunning(true);
    const r = await runE2e().catch(() => null);
    if (!r) { setRunning(false); return; }
    setRes(r);
    let i = 0;
    timer.current = window.setInterval(() => {
      i += 1; setShown(i);
      if (i >= r.steps.length) { stopTimer(); setRunning(false); }
    }, 650);
  }, []);
  const skip = () => { stopTimer(); if (res) setShown(res.steps.length); setRunning(false); };
  const reset = () => { stopTimer(); setRes(null); setShown(0); setRunning(false); };

  const steps: E2eStep[] = res?.steps ?? [];
  const visible = steps.slice(0, shown);
  const opState = [...visible].reverse().find((s) => s.op)?.op ?? "—";
  const nodeOn = (id: string) => visible.some((s) => s.node === id);
  const nodePill = (id: string) => [...visible].reverse().find((s) => s.node === id && s.pill)?.pill;
  const done = res && shown >= steps.length;

  return (
    <div className="flex flex-col gap-3 min-h-full">
      <div className="flex items-center gap-3 flex-wrap border-b border-edge pb-2">
        <h2 className="text-base font-bold flex items-center gap-2">🧪 Teste Ponta a Ponta
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent/15 text-accent">do cadastro ao DONE · real</span>
        </h2>
        <div className="ml-auto flex items-center gap-2 text-xs">
          <button onClick={play} disabled={running} className="px-3 py-1.5 rounded-card border border-accent text-accent hover:bg-accent/10 disabled:opacity-50">▶ {running ? "executando…" : "Gerar demo"}</button>
          <button onClick={skip} disabled={!res || !!done} className="px-3 py-1.5 rounded-card border border-edge text-muted hover:border-accent disabled:opacity-40">Pular p/ fim</button>
          <button onClick={reset} disabled={!res} className="px-3 py-1.5 rounded-card border border-edge text-muted hover:border-accent disabled:opacity-40">Reiniciar</button>
          <span className="text-muted font-mono ml-1">OP: <b className="text-accent">{opState}</b></span>
        </div>
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-[1.3fr_.9fr] gap-4 min-h-0">
        {/* Fio Dourado — eventos */}
        <div className="bg-panel border border-edge rounded-card p-4 flex flex-col min-h-0">
          <h3 className="text-[11px] uppercase tracking-wider text-muted mb-2">Fio Dourado — eventos</h3>
          <div className="flex-1 overflow-y-auto scroll-thin relative pl-3" style={{ borderLeft: "2px solid var(--chart-c2, #e6c34a)" }}>
            {visible.length === 0 && <p className="text-xs text-muted">Clique <b>Gerar demo</b> — executa o roteiro real (20 passos) e transmite os eventos.</p>}
            {visible.map((s) => {
              const c = CAT[s.cat] ?? CAT.evento;
              return (
                <div key={s.seq} className="py-2 border-b border-dashed border-edge/40">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[10px] font-mono text-muted">#{String(s.seq).padStart(2, "0")}</span>
                    <span className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded" style={{ background: c.bg, color: c.fg }}>{c.l}</span>
                    <span className={s.ok ? "text-ok text-xs" : "text-nok text-xs"}>{s.ok ? "✓" : "✗"}</span>
                  </div>
                  <p className="text-xs text-text mt-1">{s.txt}</p>
                  {s.id && <p className="text-[10px] font-mono text-accent mt-0.5 break-all">{s.id}</p>}
                  {s.detail && <p className="text-[10px] text-muted">{s.detail}</p>}
                </div>
              );
            })}
          </div>
        </div>

        {/* Linhagem + Resultado */}
        <div className="overflow-y-auto scroll-thin space-y-4 pr-1">
          <div className="bg-panel border border-edge rounded-card p-4">
            <h3 className="text-[11px] uppercase tracking-wider text-muted mb-2">Linhagem — vínculos</h3>
            <div className="space-y-1">
              {NODES.map((n) => {
                const on = nodeOn(n.id); const p = nodePill(n.id);
                return (
                  <div key={n.id} className={"flex items-center gap-2 py-1 rounded transition-opacity " + (on ? "opacity-100" : "opacity-30")}>
                    <span className="font-mono text-[11px] whitespace-pre" style={{ color: "var(--accent)" }}>{n.ind}</span>
                    <span className="text-xs font-bold">{n.lab}</span>
                    <span className="text-[10px] font-mono text-muted">{n.nid}</span>
                    {p && <span className={"ml-auto text-[9px] font-mono font-bold px-2 py-0.5 rounded-full border " + (PILL[p[0]] ?? "")}>{p[1]}</span>}
                  </div>
                );
              })}
            </div>
          </div>

          {done && res && (
            <div className="bg-panel border border-edge rounded-card p-4">
              <h3 className="text-[11px] uppercase tracking-wider text-muted mb-2">Resultado</h3>
              <div className={"flex items-center gap-3 rounded-card p-3 mb-3 border " + (res.passed ? "bg-ok/10 border-ok/50" : "bg-nok/10 border-nok/50")}>
                <span className="text-xl font-extrabold" style={{ color: res.passed ? "var(--ok)" : "var(--nok)" }}>{res.passed ? "DONE ✓" : "FALHOU ✗"}</span>
                <span className="text-[11px] text-muted">instância concluída, reconciliada e auditável</span>
              </div>
              <div className="grid grid-cols-2 gap-2">
                {Object.entries(res.kpis).map(([k, v]) => (
                  <div key={k} className="bg-surface border border-edge rounded-card p-2">
                    <p className="text-[9px] uppercase tracking-wider text-muted">{k.replace(/_/g, " ")}</p>
                    <p className="text-xs font-mono font-bold text-text mt-0.5">{String(v)}</p>
                  </div>
                ))}
              </div>
              <div className="mt-3 grid grid-cols-2 gap-1">
                {Object.entries(res.acceptance).map(([k, v]) => (
                  <span key={k} className={"text-[10px] flex items-center gap-1 " + (v ? "text-ok" : "text-nok")}>{v ? "✓" : "✗"} {k.replace(/_/g, " ")}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
