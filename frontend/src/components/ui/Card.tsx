import type { ReactNode } from "react";

// Cartão (Onda 4): contêiner que agrupa mídia, título, texto e ações sobre um objeto.
export function Card({ title, subtitle, media, actions, footer, accent, onClick, children }: {
  title?: ReactNode; subtitle?: ReactNode; media?: ReactNode; actions?: ReactNode;
  footer?: ReactNode; accent?: boolean; onClick?: () => void; children?: ReactNode;
}) {
  return (
    <div onClick={onClick}
      className={"vd-surface border rounded-card overflow-hidden flex flex-col " + (accent ? "border-accent/50 " : "border-edge ") + (onClick ? "cursor-pointer hover:border-accent transition-colors" : "")}>
      {media != null && <div className="h-24 bg-edge flex items-center justify-center overflow-hidden text-4xl">{media}</div>}
      <div className="p-3 flex-1 flex flex-col gap-1">
        {title != null && <div className="font-semibold text-sm text-text leading-tight">{title}</div>}
        {subtitle != null && <div className="text-xs text-muted">{subtitle}</div>}
        {children != null && <div className="text-sm text-text mt-1">{children}</div>}
        {actions != null && <div className="flex gap-2 mt-auto pt-2">{actions}</div>}
      </div>
      {footer != null && <div className="px-3 py-2 border-t border-edge text-xs text-muted">{footer}</div>}
    </div>
  );
}
