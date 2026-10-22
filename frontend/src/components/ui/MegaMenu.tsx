import { useState } from "react";

// Megamenu (Onda 8): painel de navegação grande com colunas.
export interface MegaCol { title: string; links: { label: string; icon?: string; onClick?: () => void }[] }

export function MegaMenu({ label, columns }: { label: string; columns: MegaCol[] }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative" onMouseLeave={() => setOpen(false)}>
      <button onClick={() => setOpen((o) => !o)} onMouseEnter={() => setOpen(true)}
        className="px-3 py-1.5 rounded-card border border-edge bg-edge text-sm hover:border-accent flex items-center gap-1">
        {label}<span className="text-[10px] text-muted">▾</span>
      </button>
      {open && (
        <div className="absolute z-40 mt-1 vd-surface border border-edge rounded-card p-3 shadow-xl grid gap-4 grid-cols-2 sm:grid-cols-3 min-w-[300px]">
          {columns.map((col, i) => (
            <div key={i}>
              <div className="text-[10px] uppercase tracking-wider text-muted mb-1">{col.title}</div>
              <ul className="space-y-0.5">
                {col.links.map((l, k) => (
                  <li key={k}><button onClick={() => { l.onClick?.(); setOpen(false); }} className="flex items-center gap-1.5 text-sm text-text hover:text-accent">{l.icon && <span>{l.icon}</span>}{l.label}</button></li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
