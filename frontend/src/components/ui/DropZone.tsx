import { useRef, useState } from "react";

// Área de soltar arquivos (Onda 7): drag-and-drop + clique p/ selecionar.
export function DropZone({ onFiles, accept, multiple = true, hint }: {
  onFiles: (files: File[]) => void; accept?: string; multiple?: boolean; hint?: string;
}) {
  const [over, setOver] = useState(false);
  const inp = useRef<HTMLInputElement>(null);
  const take = (fl: FileList | null) => { if (fl && fl.length) onFiles(Array.from(fl)); };
  return (
    <div onClick={() => inp.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); take(e.dataTransfer.files); }}
      className={"border-2 border-dashed rounded-card p-5 text-center cursor-pointer transition-colors " + (over ? "border-accent bg-accent/10" : "border-edge hover:border-accent/60")}>
      <div className="text-2xl">⬇️</div>
      <p className="text-sm text-text mt-1">Arraste arquivos aqui ou clique</p>
      {hint && <p className="text-[11px] text-muted mt-0.5">{hint}</p>}
      <input ref={inp} type="file" accept={accept} multiple={multiple} className="hidden" onChange={(e) => { take(e.target.files); e.target.value = ""; }} />
    </div>
  );
}
