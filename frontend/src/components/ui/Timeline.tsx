import type { ReactNode } from "react";

// Linha do tempo (Onda 5): exibição cronológica vertical de eventos.
export interface TimelineItem { time?: string; title: ReactNode; desc?: ReactNode; color?: string }

export function Timeline({ items }: { items: TimelineItem[] }) {
  return (
    <ol className="relative border-l-2 border-edge ml-2 space-y-4">
      {items.map((it, i) => (
        <li key={i} className="ml-4">
          <span className="absolute -left-[7px] mt-1 w-3 h-3 rounded-full border-2 border-panel" style={{ background: it.color || "var(--accent)" }} />
          {it.time && <div className="text-[10px] uppercase tracking-wider text-muted">{it.time}</div>}
          <div className="text-sm font-medium text-text">{it.title}</div>
          {it.desc && <div className="text-xs text-muted">{it.desc}</div>}
        </li>
      ))}
    </ol>
  );
}
