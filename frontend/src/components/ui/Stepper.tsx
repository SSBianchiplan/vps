// Passo a passo / Stepper (Onda 7): indicador sequencial de etapas de um processo.
export function Stepper({ steps, current, onStep }: { steps: string[]; current: number; onStep?: (i: number) => void }) {
  return (
    <div className="flex items-center">
      {steps.map((s, i) => {
        const done = i < current, act = i === current;
        return (
          <div key={i} className="flex items-center flex-1 last:flex-none">
            <button type="button" onClick={() => onStep?.(i)} className="flex flex-col items-center" disabled={!onStep}>
              <div className={"w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold " + (done ? "bg-ok text-white" : act ? "bg-accent text-onaccent" : "bg-edge text-muted")}>{done ? "✓" : i + 1}</div>
              <span className={"text-[10px] mt-1 whitespace-nowrap " + (act ? "text-text font-medium" : "text-muted")}>{s}</span>
            </button>
            {i < steps.length - 1 && <div className={"flex-1 h-0.5 mx-1 mb-4 " + (done ? "bg-ok" : "bg-edge")} />}
          </div>
        );
      })}
    </div>
  );
}
