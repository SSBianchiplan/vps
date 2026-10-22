import { useState } from "react";

// Gráficos interativos (Onda 4): SVG leve, sem libs externas (CSP-safe), com hover.
const PALETTE = ["var(--accent)", "#3da9fc", "#19C3B2", "#f0a020", "#e5484d", "#8b5cf6", "#30a46c", "#ec4899"];

export interface Datum { label: string; value: number; color?: string }

export function BarChart({ data, height = 140, unit = "" }: { data: Datum[]; height?: number; unit?: string }) {
  const [hi, setHi] = useState<number | null>(null);
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <div>
      <div className="flex items-end gap-1.5" style={{ height }}>
        {data.map((d, i) => (
          <div key={i} className="flex-1 flex flex-col items-center justify-end h-full"
            onMouseEnter={() => setHi(i)} onMouseLeave={() => setHi(null)}>
            <div className="text-[10px] font-mono text-text mb-0.5 h-3">{hi === i ? `${d.value}${unit}` : ""}</div>
            <div className="w-full rounded-t transition-all" title={`${d.label}: ${d.value}${unit}`}
              style={{ height: `${(d.value / max) * 100}%`, background: d.color || PALETTE[i % PALETTE.length], opacity: hi == null || hi === i ? 1 : 0.45 }} />
          </div>
        ))}
      </div>
      <div className="flex gap-1.5 mt-1">
        {data.map((d, i) => <div key={i} className="flex-1 text-center text-[9px] text-muted truncate">{d.label}</div>)}
      </div>
    </div>
  );
}

export function LineChart({ data, height = 140, color = "var(--accent)", unit = "" }: { data: number[]; height?: number; color?: string; unit?: string }) {
  const max = Math.max(...data, 1), min = Math.min(...data, 0), rng = max - min || 1;
  const pts = data.map((v, i) => [(i / (data.length - 1 || 1)) * 100, 100 - ((v - min) / rng) * 100] as const);
  const d = "M " + pts.map((p) => `${p[0]},${p[1]}`).join(" L ");
  const area = `${d} L 100,100 L 0,100 Z`;
  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" style={{ width: "100%", height }}>
      <defs><linearGradient id="lc-fill" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stopColor={color} stopOpacity="0.35" /><stop offset="100%" stopColor={color} stopOpacity="0" />
      </linearGradient></defs>
      <path d={area} fill="url(#lc-fill)" />
      <path d={d} fill="none" stroke={color} strokeWidth="1.5" vectorEffect="non-scaling-stroke" strokeLinejoin="round" strokeLinecap="round" />
      {pts.map((p, i) => <circle key={i} cx={p[0]} cy={p[1]} r="1.6" fill={color} vectorEffect="non-scaling-stroke"><title>{`${data[i]}${unit}`}</title></circle>)}
    </svg>
  );
}

export function Donut({ data, size = 140, thickness = 18 }: { data: Datum[]; size?: number; thickness?: number }) {
  const [hi, setHi] = useState<number | null>(null);
  const total = data.reduce((s, d) => s + d.value, 0) || 1;
  const r = 50 - thickness / 2, c = 2 * Math.PI * r;
  let off = 0;
  const center = hi != null ? data[hi] : null;
  return (
    <div className="flex items-center gap-3">
      <svg viewBox="0 0 100 100" style={{ width: size, height: size }}>
        <g transform="rotate(-90 50 50)">
          {data.map((d, i) => {
            const frac = d.value / total, len = frac * c;
            const seg = (
              <circle key={i} cx="50" cy="50" r={r} fill="none" stroke={d.color || PALETTE[i % PALETTE.length]}
                strokeWidth={thickness} strokeDasharray={`${len} ${c - len}`} strokeDashoffset={-off}
                opacity={hi == null || hi === i ? 1 : 0.4} onMouseEnter={() => setHi(i)} onMouseLeave={() => setHi(null)}
                style={{ cursor: "pointer", transition: "opacity .15s" }}><title>{`${d.label}: ${d.value}`}</title></circle>
            );
            off += len;
            return seg;
          })}
        </g>
        <text x="50" y="47" textAnchor="middle" className="fill-text" style={{ fontSize: 11, fontWeight: 700 }}>{center ? center.value : total}</text>
        <text x="50" y="60" textAnchor="middle" className="fill-muted" style={{ fontSize: 6 }}>{center ? center.label : "total"}</text>
      </svg>
      <div className="space-y-1 text-xs">
        {data.map((d, i) => (
          <div key={i} className="flex items-center gap-1.5" onMouseEnter={() => setHi(i)} onMouseLeave={() => setHi(null)}>
            <span className="w-2.5 h-2.5 rounded-sm" style={{ background: d.color || PALETTE[i % PALETTE.length] }} />
            <span className={hi === i ? "text-text" : "text-muted"}>{d.label}</span>
            <span className="text-muted ml-auto font-mono">{Math.round((d.value / total) * 100)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}
