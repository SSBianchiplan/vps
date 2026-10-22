// Esqueleto de carregamento (Onda 8): blocos cinza que imitam o layout antes dos dados.
export function Skeleton({ lines = 3, avatar = false }: { lines?: number; avatar?: boolean }) {
  return (
    <div className="flex gap-3 animate-pulse">
      {avatar && <div className="w-10 h-10 rounded-full bg-edge shrink-0" />}
      <div className="flex-1 space-y-2">
        {Array.from({ length: lines }, (_, i) => (
          <div key={i} className="h-3 rounded bg-edge" style={{ width: `${90 - i * 12}%` }} />
        ))}
      </div>
    </div>
  );
}

export function SkeletonCard() {
  return (
    <div className="vd-surface border border-edge rounded-card p-3 animate-pulse">
      <div className="h-20 rounded bg-edge mb-2" />
      <div className="h-3 rounded bg-edge w-3/4 mb-1.5" />
      <div className="h-3 rounded bg-edge w-1/2" />
    </div>
  );
}
