import { useEffect, useRef, useState } from "react";

// Barra de gravação: conta o tempo desde que monta (= início da gravação) + tamanho.
const pad = (n: number) => String(n).padStart(2, "0");
const fmt = (s: number) => {
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = Math.floor(s % 60);
  return h > 0 ? `${h}:${pad(m)}:${pad(sec)}` : `${pad(m)}:${pad(sec)}`;
};

export function RecTimer({ size }: { size: number }) {
  const start = useRef(performance.now());
  const [el, setEl] = useState(0);
  useEffect(() => {
    const iv = window.setInterval(() => setEl((performance.now() - start.current) / 1000), 500);
    return () => window.clearInterval(iv);
  }, []);
  return (
    <div className="flex items-center gap-2 bg-nok/15 border border-nok/40 rounded-card px-2.5 py-1.5 mb-2 text-xs">
      <span className="w-2 h-2 rounded-full bg-nok animate-pulse shrink-0" />
      <span className="font-semibold text-nok">REC</span>
      <span className="font-mono text-text tabular-nums text-sm">{fmt(el)}</span>
      <span className="text-muted ml-auto tabular-nums">{(size / 1048576).toFixed(1)} MB</span>
    </div>
  );
}
