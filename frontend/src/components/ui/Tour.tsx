import { useState } from "react";

// Passo a passo guiado / Tour (Onda 8): balões sequenciais que ensinam a usar a plataforma.
export interface TourStep { title: string; body: string }

export function Tour({ steps, open, onClose }: { steps: TourStep[]; open: boolean; onClose: () => void }) {
  const [i, setI] = useState(0);
  if (!open) return null;
  const s = steps[i], last = i === steps.length - 1;
  const close = () => { setI(0); onClose(); };
  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center p-4 bg-black/60" onClick={close}>
      <div className="vd-surface border border-accent/50 rounded-card w-full max-w-sm p-4 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2 mb-1">
          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-accent/15 text-accent">{i + 1}/{steps.length}</span>
          <h3 className="font-bold flex-1">{s.title}</h3>
          <button onClick={close} className="text-muted hover:text-text">✕</button>
        </div>
        <p className="text-sm text-muted">{s.body}</p>
        <div className="flex items-center gap-1.5 mt-3">
          {steps.map((_, k) => <span key={k} className={"w-1.5 h-1.5 rounded-full " + (k === i ? "bg-accent" : "bg-edge")} />)}
          <div className="ml-auto flex gap-2">
            <button onClick={close} className="text-xs text-muted hover:text-text">Pular</button>
            {i > 0 && <button onClick={() => setI(i - 1)} className="text-xs px-2 py-1 rounded border border-edge">Voltar</button>}
            <button onClick={() => (last ? close() : setI(i + 1))} className="text-xs px-2 py-1 rounded bg-accent text-onaccent font-medium">{last ? "Concluir" : "Próximo"}</button>
          </div>
        </div>
      </div>
    </div>
  );
}
