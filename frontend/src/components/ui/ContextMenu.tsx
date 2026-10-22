import { useEffect, useState, type ReactNode } from "react";

// Menu de contexto (Onda 8): opções no clique com o botão direito.
export interface MenuItem { label: string; icon?: string; danger?: boolean; onClick?: () => void }

export function ContextMenu({ items, children }: { items: MenuItem[]; children: ReactNode }) {
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);
  useEffect(() => {
    if (!pos) return;
    const close = () => setPos(null);
    window.addEventListener("click", close);
    window.addEventListener("scroll", close, true);
    return () => { window.removeEventListener("click", close); window.removeEventListener("scroll", close, true); };
  }, [pos]);
  return (
    <>
      <div onContextMenu={(e) => { e.preventDefault(); setPos({ x: e.clientX, y: e.clientY }); }}>{children}</div>
      {pos && (
        <ul className="fixed z-[200] vd-surface border border-edge rounded-card py-1 shadow-xl min-w-[160px]" style={{ left: pos.x, top: pos.y }}>
          {items.map((it, i) => (
            <li key={i}>
              <button onClick={() => { it.onClick?.(); setPos(null); }}
                className={"w-full flex items-center gap-2 px-3 py-1.5 text-sm text-left hover:bg-edge " + (it.danger ? "text-nok" : "text-text")}>
                {it.icon && <span>{it.icon}</span>}{it.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
