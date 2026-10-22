import { useMemo, useState, type ReactNode } from "react";

// Tabela dinâmica (Onda 4 · dados de alta densidade): busca global, ordenação por
// coluna, paginação. Genérica e reutilizável em qualquer view.
export interface Column<T> {
  key: string;
  header: string;
  align?: "left" | "right" | "center";
  sortable?: boolean;                      // default: true
  sortValue?: (row: T) => string | number; // valor custom p/ ordenar
  render?: (row: T) => ReactNode;          // render custom da célula
  className?: string;
}

export function DataTable<T>({
  columns, rows, pageSize = 10, searchable = true, dense = false, empty = "sem dados", getKey,
}: {
  columns: Column<T>[];
  rows: T[];
  pageSize?: number;
  searchable?: boolean;
  dense?: boolean;
  empty?: string;
  getKey?: (row: T, i: number) => string | number;
}) {
  const [q, setQ] = useState("");
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [dir, setDir] = useState<"asc" | "desc">("asc");
  const [page, setPage] = useState(0);

  const cell = (r: T, k: string) => (r as Record<string, unknown>)[k];
  const filtered = useMemo(() => {
    const t = q.trim().toLowerCase();
    if (!t) return rows;
    return rows.filter((r) => columns.some((c) => String(cell(r, c.key) ?? "").toLowerCase().includes(t)));
  }, [rows, q, columns]);

  const sorted = useMemo(() => {
    if (!sortKey) return filtered;
    const col = columns.find((c) => c.key === sortKey);
    const val = (r: T) => (col?.sortValue ? col.sortValue(r) : (cell(r, sortKey) as string | number));
    const arr = [...filtered].sort((a, b) => {
      const av = val(a), bv = val(b);
      if (av == null) return 1;
      if (bv == null) return -1;
      if (typeof av === "number" && typeof bv === "number") return av - bv;
      return String(av).localeCompare(String(bv), "pt", { numeric: true });
    });
    return dir === "asc" ? arr : arr.reverse();
  }, [filtered, sortKey, dir, columns]);

  const pages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const pg = Math.min(page, pages - 1);
  const slice = sorted.slice(pg * pageSize, pg * pageSize + pageSize);
  const pad = dense ? "py-1 px-2" : "py-2 px-3";
  const alignCls = (a?: string) => (a === "right" ? "text-right" : a === "center" ? "text-center" : "text-left");

  const toggleSort = (c: Column<T>) => {
    if (c.sortable === false) return;
    if (sortKey === c.key) setDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(c.key); setDir("asc"); }
    setPage(0);
  };

  return (
    <div className="space-y-2">
      {searchable && (
        <div className="flex items-center gap-2">
          <input value={q} onChange={(e) => { setQ(e.target.value); setPage(0); }} placeholder="buscar…"
            className="w-full max-w-xs bg-edge border border-edge rounded px-2 py-1.5 text-sm text-text focus:outline-none focus:border-accent" />
          <span className="text-[11px] text-muted ml-auto">{sorted.length} registro(s)</span>
        </div>
      )}
      <div className="overflow-x-auto rounded-card border border-edge scroll-thin">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-muted bg-panel border-b border-edge">
              {columns.map((c) => {
                const active = sortKey === c.key;
                return (
                  <th key={c.key} onClick={() => toggleSort(c)}
                    className={`${pad} ${alignCls(c.align)} font-semibold uppercase tracking-wider text-[10px] ` + (c.sortable === false ? "" : "cursor-pointer select-none hover:text-text")}>
                    {c.header}{active && <span className="ml-1 text-accent">{dir === "asc" ? "▲" : "▼"}</span>}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {slice.map((r, i) => (
              <tr key={getKey ? getKey(r, i) : i} className="border-b border-edge/40 last:border-0 hover:bg-edge/40">
                {columns.map((c) => (
                  <td key={c.key} className={`${pad} ${alignCls(c.align)} ${c.className ?? "text-muted"}`}>
                    {c.render ? c.render(r) : String(cell(r, c.key) ?? "—")}
                  </td>
                ))}
              </tr>
            ))}
            {slice.length === 0 && <tr><td colSpan={columns.length} className={`${pad} text-center text-muted`}>{empty}</td></tr>}
          </tbody>
        </table>
      </div>
      {pages > 1 && (
        <div className="flex items-center gap-2 justify-end text-xs">
          <button disabled={pg === 0} onClick={() => setPage(pg - 1)} className="px-2 py-1 rounded border border-edge disabled:opacity-30 hover:border-accent">‹</button>
          <span className="text-muted">{pg + 1}/{pages}</span>
          <button disabled={pg >= pages - 1} onClick={() => setPage(pg + 1)} className="px-2 py-1 rounded border border-edge disabled:opacity-30 hover:border-accent">›</button>
        </div>
      )}
    </div>
  );
}
