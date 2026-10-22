import type { ReactNode } from "react";

// Painel lateral gaveta (Onda 5): desliza das laterais (off-canvas).
export function Drawer({ open, onClose, side = "right", title, children, width = 340 }: {
  open: boolean; onClose: () => void; side?: "left" | "right"; title?: ReactNode; children?: ReactNode; width?: number;
}) {
  const hidden = side === "right" ? "translateX(100%)" : "translateX(-100%)";
  return (
    <div className={"fixed inset-0 z-[120] " + (open ? "" : "pointer-events-none")}>
      <div className={"absolute inset-0 bg-black/50 transition-opacity duration-200 " + (open ? "opacity-100" : "opacity-0")} onClick={onClose} />
      <div className="absolute top-0 bottom-0 vd-surface shadow-2xl transition-transform duration-200 flex flex-col"
        style={{ width, right: side === "right" ? 0 : undefined, left: side === "left" ? 0 : undefined,
          borderLeft: side === "right" ? "1px solid var(--glass-border)" : undefined,
          borderRight: side === "left" ? "1px solid var(--glass-border)" : undefined,
          transform: open ? "translateX(0)" : hidden }}>
        <div className="flex items-center gap-2 px-4 py-3 border-b border-edge"><h3 className="font-bold flex-1">{title}</h3><button onClick={onClose} className="text-muted hover:text-text text-lg">✕</button></div>
        <div className="p-4 overflow-y-auto scroll-thin flex-1">{children}</div>
      </div>
    </div>
  );
}
