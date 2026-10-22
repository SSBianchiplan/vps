// Seletor de período (Onda 6): data início + fim com validação e duração.
export function DateRange({ start, end, onChange }: { start: string; end: string; onChange: (start: string, end: string) => void }) {
  const days = start && end ? Math.round((new Date(end).getTime() - new Date(start).getTime()) / 86400000) + 1 : null;
  const invalid = start && end && end < start;
  const inp = "bg-edge border border-edge rounded px-2 py-1.5 text-sm text-text focus:outline-none focus:border-accent";
  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2">
        <input type="date" value={start} max={end || undefined} onChange={(e) => onChange(e.target.value, end)} className={inp} />
        <span className="text-muted text-xs">até</span>
        <input type="date" value={end} min={start || undefined} onChange={(e) => onChange(start, e.target.value)} className={inp} />
      </div>
      {invalid ? <p className="text-[11px] text-nok">fim antes do início</p>
        : days != null && <p className="text-[11px] text-muted">{days} dia(s) no período</p>}
    </div>
  );
}
