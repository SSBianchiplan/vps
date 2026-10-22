import { useEffect, useState } from "react";
import { eventsSummary } from "../api/events";
import type { Mode } from "../types";

const MODES: Mode[] = ["LER", "CONTAR", "DETECTAR", "RASTREAR", "DESCREVER", "ANALISAR"];
const LABELS: Record<Mode, string> = { LER: "LER", CONTAR: "CONT", DETECTAR: "DETEC", RASTREAR: "TRACK", DESCREVER: "DESC", ANALISAR: "ANAL" };

/**
 * Gráfico de barras "detecções por modo". Lê o agregado SQL (/events/summary)
 * em vez de baixar centenas de eventos — leitura rápida. Consome as CSS vars do
 * tema de gráfico (--chart-bg/--chart-grid/--chart-axis) e a paleta (--chart-cN).
 */
export function MiniChart() {
  const [counts, setCounts] = useState<number[]>([0, 0, 0, 0, 0]);

  useEffect(() => {
    let on = true;
    const load = () =>
      eventsSummary()
        .then((s) => { if (on) setCounts(MODES.map((m) => s.by_mode[m] ?? 0)); })
        .catch(() => undefined);
    load();
    const id = window.setInterval(load, 15000);
    return () => { on = false; window.clearInterval(id); };
  }, []);

  const max = Math.max(1, ...counts);

  return (
    <div
      className="rounded-card border border-edge p-3"
      style={{ background: "var(--chart-bg)" }}
    >
      <p className="text-xs uppercase tracking-wider mb-2" style={{ color: "var(--chart-axis)" }}>
        Detecções por modo
      </p>
      <div className="flex items-end gap-2 h-24">
        {counts.map((c, i) => (
          <div key={MODES[i]} className="flex-1 flex flex-col items-center justify-end h-full">
            <span className="text-[10px] mb-0.5" style={{ color: "var(--chart-axis)" }}>{c}</span>
            <div
              className="w-full rounded-t transition-all"
              style={{ height: `${(c / max) * 100}%`, minHeight: 3, background: `var(--chart-c${i + 1})` }}
              title={`${MODES[i]}: ${c}`}
            />
          </div>
        ))}
      </div>
      <div className="flex gap-2 mt-1 border-t" style={{ borderColor: "var(--chart-grid)" }}>
        {MODES.map((m) => (
          <span key={m} className="flex-1 text-center text-[9px] pt-1" style={{ color: "var(--chart-axis)" }}>
            {LABELS[m]}
          </span>
        ))}
      </div>
    </div>
  );
}
