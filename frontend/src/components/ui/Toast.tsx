import { useState } from "react";

// Toast / Snackbar (Onda 5): alerta flutuante que some sozinho.
export type ToastKind = "info" | "ok" | "nok" | "warn";
export interface ToastItem { id: number; msg: string; kind: ToastKind }

export function useToast(ttl = 3000) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const dismiss = (id: number) => setItems((x) => x.filter((t) => t.id !== id));
  const push = (msg: string, kind: ToastKind = "info") => {
    const id = performance.now();
    setItems((x) => [...x, { id, msg, kind }]);
    window.setTimeout(() => dismiss(id), ttl);
  };
  return { items, push, dismiss };
}

const KCLS: Record<ToastKind, string> = {
  info: "border-edge", ok: "border-ok/50", nok: "border-nok/50", warn: "border-warn/50",
};
const KICO: Record<ToastKind, string> = { info: "ℹ️", ok: "✓", nok: "⚠", warn: "⚠" };

export function ToastHost({ items, dismiss }: { items: ToastItem[]; dismiss: (id: number) => void }) {
  return (
    <div className="fixed bottom-4 right-4 z-[200] space-y-2 w-72 max-w-[90vw]">
      {items.map((t) => (
        <div key={t.id} onClick={() => dismiss(t.id)}
          className={"vd-surface border rounded-card px-3 py-2 text-sm shadow-lg flex items-start gap-2 cursor-pointer animate-[fadein_.15s] " + KCLS[t.kind]}>
          <span>{KICO[t.kind]}</span><span className="flex-1 text-text">{t.msg}</span>
        </div>
      ))}
    </div>
  );
}
