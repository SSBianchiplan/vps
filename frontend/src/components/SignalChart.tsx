// Gráfico de transmissão (vazão Mbps no tempo) — estilo DJI: verde estável / vermelho instável.
// Compartilhado por Visão Aérea (drone) e Vídeo Osmo (RTMP).
export function SignalChart({ samples, stable, mbps }: { samples: number[]; stable: boolean; mbps: number }) {
  const W = 100, H = 36;
  const max = Math.max(2, ...samples) * 1.15;
  const color = stable ? "#34d399" : "#ef4444";
  const pts = samples.map((v, i) => {
    const x = samples.length <= 1 ? 0 : (i / (samples.length - 1)) * W;
    const y = H - Math.min(H, (v / max) * H);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  return (
    <div className="bg-black/60 border border-edge rounded-card p-2">
      <div className="flex items-center justify-between text-[10px] text-muted mb-1">
        <span>Transmissão (vazão)</span>
        <span className="font-mono" style={{ color }}>{mbps.toFixed(1)} Mbps</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="w-full h-16">
        {[0.25, 0.5, 0.75].map((g) => (
          <line key={g} x1={0} x2={W} y1={H * g} y2={H * g} stroke="#ffffff14" strokeWidth={0.3} />
        ))}
        {samples.length > 1 && (
          <polyline points={pts} fill="none" stroke={color} strokeWidth={1.2} vectorEffect="non-scaling-stroke" />
        )}
      </svg>
      <div className="flex items-center justify-between text-[9px] mt-1">
        <span className="flex items-center gap-1 text-muted"><span className="w-3 h-0.5 inline-block" style={{ background: "#34d399" }} />Estável</span>
        <span className="flex items-center gap-1 text-muted"><span className="w-3 h-0.5 inline-block" style={{ background: "#ef4444" }} />Instável</span>
        <span className="text-muted">~0–{max.toFixed(0)} Mbps</span>
      </div>
    </div>
  );
}
