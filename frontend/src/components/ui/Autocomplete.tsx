import { useState } from "react";

// Preenchimento automático / Combobox (Onda 6): filtra opções enquanto digita.
export function Autocomplete({ options, value, onChange, placeholder, max = 8 }: {
  options: string[]; value: string; onChange: (v: string) => void; placeholder?: string; max?: number;
}) {
  const [open, setOpen] = useState(false);
  const [hi, setHi] = useState(0);
  const matches = options.filter((o) => o.toLowerCase().includes(value.toLowerCase()) && o !== value).slice(0, max);

  const pick = (v: string) => { onChange(v); setOpen(false); };
  return (
    <div className="relative">
      <input value={value} placeholder={placeholder}
        onChange={(e) => { onChange(e.target.value); setOpen(true); setHi(0); }}
        onFocus={() => setOpen(true)} onBlur={() => window.setTimeout(() => setOpen(false), 120)}
        onKeyDown={(e) => {
          if (!open || !matches.length) return;
          if (e.key === "ArrowDown") { e.preventDefault(); setHi((h) => Math.min(h + 1, matches.length - 1)); }
          else if (e.key === "ArrowUp") { e.preventDefault(); setHi((h) => Math.max(h - 1, 0)); }
          else if (e.key === "Enter") { e.preventDefault(); pick(matches[hi]); }
          else if (e.key === "Escape") setOpen(false);
        }}
        className="w-full bg-edge border border-edge rounded px-2 py-1.5 text-sm text-text focus:outline-none focus:border-accent" />
      {open && matches.length > 0 && (
        <ul className="absolute z-30 mt-1 w-full vd-surface border border-edge rounded-card max-h-48 overflow-y-auto scroll-thin shadow-lg">
          {matches.map((o, i) => (
            <li key={o} onMouseDown={() => pick(o)} onMouseEnter={() => setHi(i)}
              className={"px-2 py-1.5 text-sm cursor-pointer " + (i === hi ? "bg-accent text-onaccent" : "hover:bg-edge")}>{o}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
