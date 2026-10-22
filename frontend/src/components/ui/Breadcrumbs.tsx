// Caminho de rato / Breadcrumbs (Onda 7): rastro hierárquico da localização.
export interface Crumb { label: string; onClick?: () => void }

export function Breadcrumbs({ items, sep = "›" }: { items: Crumb[]; sep?: string }) {
  return (
    <nav className="flex items-center gap-1.5 text-xs flex-wrap">
      {items.map((c, i) => {
        const last = i === items.length - 1;
        return (
          <span key={i} className="flex items-center gap-1.5">
            {i > 0 && <span className="text-muted">{sep}</span>}
            {c.onClick && !last
              ? <button onClick={c.onClick} className="text-accent hover:underline">{c.label}</button>
              : <span className={last ? "text-text font-medium" : "text-muted"}>{c.label}</span>}
          </span>
        );
      })}
    </nav>
  );
}
