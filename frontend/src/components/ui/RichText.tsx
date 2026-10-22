import { useEffect, useRef } from "react";

// Editor de texto rico (Onda 7): negrito/itálico/sublinhado/lista/título/link via contentEditable.
export function RichText({ value, onChange }: { value: string; onChange: (html: string) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { if (ref.current && ref.current.innerHTML !== value) ref.current.innerHTML = value; }, []); // init 1x
  const cmd = (c: string, v?: string) => { document.execCommand(c, false, v); if (ref.current) onChange(ref.current.innerHTML); };
  const Btn = ({ c, ic, arg }: { c: string; ic: string; arg?: string }) => (
    <button type="button" title={c} onMouseDown={(e) => { e.preventDefault(); cmd(c, arg); }}
      className="w-7 h-7 rounded border border-edge bg-edge hover:border-accent text-sm">{ic}</button>
  );
  return (
    <div className="border border-edge rounded-card overflow-hidden">
      <div className="flex flex-wrap gap-1 p-1 border-b border-edge bg-panel">
        <Btn c="bold" ic="𝐁" /><Btn c="italic" ic="𝑰" /><Btn c="underline" ic="U̲" />
        <Btn c="insertUnorderedList" ic="•" /><Btn c="formatBlock" ic="H" arg="<h3>" />
        <button type="button" title="link" onMouseDown={(e) => { e.preventDefault(); const u = window.prompt("URL:"); if (u) cmd("createLink", u); }}
          className="w-7 h-7 rounded border border-edge bg-edge hover:border-accent text-sm">🔗</button>
      </div>
      <div ref={ref} contentEditable suppressContentEditableWarning
        onInput={(e) => onChange((e.target as HTMLDivElement).innerHTML)}
        className="p-2 min-h-[96px] text-sm text-text focus:outline-none [&_h3]:font-bold [&_h3]:text-base [&_ul]:list-disc [&_ul]:pl-5 [&_a]:text-accent [&_a]:underline" />
    </div>
  );
}
