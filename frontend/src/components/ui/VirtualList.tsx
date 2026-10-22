import { useState, type ReactNode } from "react";

// Lista virtual (Onda 5): renderiza só as linhas visíveis — milhares de itens sem perder desempenho.
export function VirtualList<T>({ items, rowHeight = 34, height = 260, render, overscan = 4 }: {
  items: T[]; rowHeight?: number; height?: number; render: (item: T, index: number) => ReactNode; overscan?: number;
}) {
  const [scroll, setScroll] = useState(0);
  const total = items.length * rowHeight;
  const start = Math.max(0, Math.floor(scroll / rowHeight) - overscan);
  const count = Math.ceil(height / rowHeight) + overscan * 2;
  const slice = items.slice(start, start + count);
  return (
    <div style={{ height, overflow: "auto" }} className="scroll-thin rounded-card border border-edge"
      onScroll={(e) => setScroll(e.currentTarget.scrollTop)}>
      <div style={{ height: total, position: "relative" }}>
        {slice.map((it, k) => (
          <div key={start + k} style={{ position: "absolute", top: (start + k) * rowHeight, left: 0, right: 0, height: rowHeight }}
            className="flex items-center px-3 text-xs border-b border-edge/40">
            {render(it, start + k)}
          </div>
        ))}
      </div>
    </div>
  );
}
