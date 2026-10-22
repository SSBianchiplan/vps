import type { ReactNode } from "react";

// Janela modal (Onda 5): overlay que bloqueia a interface até resposta.
export function Modal({ open, onClose, title, children, footer, size = "md" }: {
  open: boolean; onClose: () => void; title?: ReactNode; children?: ReactNode; footer?: ReactNode;
  size?: "sm" | "md" | "lg";
}) {
  if (!open) return null;
  const max = size === "sm" ? "max-w-sm" : size === "lg" ? "max-w-2xl" : "max-w-md";
  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center p-4 bg-black/50" onClick={onClose}>
      <div className={"vd-surface border border-edge rounded-card w-full max-h-[90vh] flex flex-col " + max} onClick={(e) => e.stopPropagation()}>
        {title != null && <div className="flex items-center gap-2 px-4 py-3 border-b border-edge"><h3 className="font-bold flex-1">{title}</h3><button className="text-muted hover:text-text text-lg" onClick={onClose}>✕</button></div>}
        <div className="p-4 overflow-y-auto scroll-thin">{children}</div>
        {footer != null && <div className="px-4 py-3 border-t border-edge flex gap-2 justify-end">{footer}</div>}
      </div>
    </div>
  );
}
