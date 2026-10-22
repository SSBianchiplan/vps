import { MODE_LABELS, type Mode } from "../types";
import { useStore } from "../store/useStore";

const MODES: Mode[] = ["LER", "CONTAR", "DETECTAR", "RASTREAR", "DESCREVER", "ANALISAR"];

export function ModeSelector() {
  const mode = useStore((s) => s.mode);
  const setMode = useStore((s) => s.setMode);

  return (
    <div className="grid grid-cols-2 gap-2">
      {MODES.map((m) => (
        <button
          key={m}
          onClick={() => setMode(m)}
          className={
            "py-2 rounded text-sm font-semibold border transition-colors " +
            (mode === m
              ? "bg-accent text-onaccent border-accent"
              : "bg-edge border-edge hover:border-accent")
          }
        >
          {MODE_LABELS[m]}
        </button>
      ))}
    </div>
  );
}
