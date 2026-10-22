import { useState, type ReactNode } from "react";

// Painel retrátil / Accordion (Onda 7): seções que expandem e colapsam.
export interface AccItem { title: ReactNode; content: ReactNode }

export function Accordion({ items, multi = false, initial = [0] }: { items: AccItem[]; multi?: boolean; initial?: number[] }) {
  const [open, setOpen] = useState<number[]>(initial);
  const toggle = (i: number) => setOpen((o) => (o.includes(i) ? o.filter((x) => x !== i) : multi ? [...o, i] : [i]));
  return (
    <div className="space-y-1">
      {items.map((it, i) => {
        const on = open.includes(i);
        return (
          <div key={i} className="border border-edge rounded-card overflow-hidden">
            <button onClick={() => toggle(i)} className="w-full flex items-center gap-2 px-3 py-2 text-sm font-medium text-left hover:bg-edge/40">
              <span className="text-muted text-xs">{on ? "▼" : "▶"}</span><span className="flex-1">{it.title}</span>
            </button>
            {on && <div className="px-3 py-2 text-sm text-muted border-t border-edge">{it.content}</div>}
          </div>
        );
      })}
    </div>
  );
}
