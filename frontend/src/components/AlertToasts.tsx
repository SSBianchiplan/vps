import { useEffect } from "react";
import { useStore } from "../store/useStore";

export function AlertToasts() {
  const toasts = useStore((s) => s.toasts);
  const dismiss = useStore((s) => s.dismissToast);

  useEffect(() => {
    if (toasts.length === 0) return;
    const last = toasts[toasts.length - 1];
    const t = window.setTimeout(() => dismiss(last.id), 6000);
    return () => window.clearTimeout(t);
  }, [toasts, dismiss]);

  if (toasts.length === 0) return null;
  return (
    <div className="fixed bottom-4 right-4 z-[60] flex flex-col gap-2 max-w-sm">
      {toasts.map((t) => (
        <div key={t.id} className="vd-surface border border-accent rounded-card p-3 shadow-lg flex items-start gap-2">
          <span className="text-lg">{t.action_type === "clipboard" ? "📋" : "🚨"}</span>
          <div className="min-w-0 flex-1">
            <p className="text-sm text-text">{t.message || "Ação disparada"}</p>
            <p className="text-[10px] text-muted truncate">regra: {t.rule}{t.action_type === "clipboard" ? " · copiado" : ""}</p>
          </div>
          <button className="vd-keep text-muted hover:text-text" onClick={() => dismiss(t.id)}>✕</button>
        </div>
      ))}
    </div>
  );
}
