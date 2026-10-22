import { useState } from "react";

// Menu flutuante de ação / FAB (Onda 8): botão circular que flutua sobre a interface.
export interface FabAction { icon: string; label: string; onClick: () => void }

export function Fab({ actions = [], icon = "+", fixed = true }: { actions?: FabAction[]; icon?: string; fixed?: boolean }) {
  const [open, setOpen] = useState(false);
  const pos = fixed ? "fixed bottom-5 right-5" : "absolute bottom-3 right-3";
  return (
    <div className={pos + " z-[150] flex flex-col items-end gap-2"}>
      {open && actions.map((a, i) => (
        <button key={i} onClick={() => { a.onClick(); setOpen(false); }}
          className="flex items-center gap-2 bg-panel border border-edge rounded-full pl-3 pr-1 py-1 shadow-lg text-sm hover:border-accent">
          <span className="text-xs text-muted">{a.label}</span>
          <span className="w-7 h-7 rounded-full bg-edge flex items-center justify-center">{a.icon}</span>
        </button>
      ))}
      <button onClick={() => (actions.length ? setOpen((o) => !o) : undefined)}
        className="w-12 h-12 rounded-full bg-accent text-onaccent text-2xl shadow-xl hover:brightness-110 flex items-center justify-center transition-transform"
        style={{ transform: open ? "rotate(45deg)" : "none" }}>{icon}</button>
    </div>
  );
}
