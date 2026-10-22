import { useState } from "react";

// Entrada de tags / Chips (Onda 6): transforma termos digitados em blocos removíveis.
export function TagInput({ value, onChange, placeholder = "adicione e Enter…", suggestions = [] }: {
  value: string[]; onChange: (t: string[]) => void; placeholder?: string; suggestions?: string[];
}) {
  const [draft, setDraft] = useState("");
  const add = (t: string) => { const v = t.trim(); if (v && !value.includes(v)) onChange([...value, v]); setDraft(""); };
  const remove = (t: string) => onChange(value.filter((x) => x !== t));
  const hint = suggestions.filter((s) => !value.includes(s) && s.toLowerCase().includes(draft.toLowerCase()) && draft).slice(0, 6);
  return (
    <div className="relative">
      <div className="flex flex-wrap items-center gap-1 bg-edge border border-edge rounded px-2 py-1.5 focus-within:border-accent">
        {value.map((t) => (
          <span key={t} className="flex items-center gap-1 text-xs bg-accent/15 text-accent rounded-full px-2 py-0.5">
            {t}<button onClick={() => remove(t)} className="hover:text-nok">✕</button>
          </span>
        ))}
        <input value={draft} placeholder={value.length ? "" : placeholder}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === ",") { e.preventDefault(); add(draft); }
            else if (e.key === "Backspace" && !draft && value.length) remove(value[value.length - 1]);
          }}
          className="flex-1 min-w-[80px] bg-transparent text-sm text-text focus:outline-none" />
      </div>
      {hint.length > 0 && (
        <ul className="absolute z-30 mt-1 w-full vd-surface border border-edge rounded-card overflow-hidden shadow-lg">
          {hint.map((s) => <li key={s} onMouseDown={() => add(s)} className="px-2 py-1.5 text-sm cursor-pointer hover:bg-edge">{s}</li>)}
        </ul>
      )}
    </div>
  );
}
