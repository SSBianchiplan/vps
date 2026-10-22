import type { ReactNode } from "react";

// Banner do sistema (Onda 8): alerta global fixo (ex.: "licença expira em 3 dias").
export type BannerKind = "info" | "ok" | "warn" | "nok";
const CLS: Record<BannerKind, string> = {
  info: "bg-accent/10 border-accent/30 text-text", ok: "bg-ok/10 border-ok/40 text-text",
  warn: "bg-warn/10 border-warn/40 text-text", nok: "bg-nok/10 border-nok/40 text-text",
};
const ICO: Record<BannerKind, string> = { info: "ℹ️", ok: "✓", warn: "⚠", nok: "⛔" };

export function SystemBanner({ message, kind = "info", action, onClose }: {
  message: ReactNode; kind?: BannerKind; action?: { label: string; onClick: () => void }; onClose?: () => void;
}) {
  return (
    <div className={"flex items-center gap-2 px-3 py-2 text-sm border rounded-card " + CLS[kind]}>
      <span>{ICO[kind]}</span>
      <span className="flex-1">{message}</span>
      {action && <button onClick={action.onClick} className="text-accent font-medium hover:underline whitespace-nowrap">{action.label}</button>}
      {onClose && <button onClick={onClose} className="text-muted hover:text-text">✕</button>}
    </div>
  );
}
