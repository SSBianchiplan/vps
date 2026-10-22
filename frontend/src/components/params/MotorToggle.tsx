import { useStore } from "../../store/useStore";

/**
 * Seletor de motor de inferência para DESCREVER/ANALISAR:
 *  - IA (VLM/Claude): mais rico, exige ANTHROPIC_API_KEY.
 *  - Local (edge/YOLO): roda sem token, grátis e offline.
 * Quando não há token, o backend já cai no local automaticamente.
 */
export function MotorToggle({ mode }: { mode: "DESCREVER" | "ANALISAR" }) {
  const preferEdge = useStore((s) => s.params[mode].prefer_edge);
  const setParams = useStore((s) => s.setParams);
  const caps = useStore((s) => s.capabilities);

  const vlmOn = caps?.vlm ?? false;
  const edgeOn = caps?.edge_detector ?? false;
  // Sem token, o motor efetivo é sempre o local.
  const effectiveEdge = preferEdge || !vlmOn;

  const opt = (edge: boolean, label: string, hint: string, enabled: boolean) => (
    <button
      type="button"
      disabled={!enabled}
      onClick={() => setParams(mode, { prefer_edge: edge })}
      className={
        "flex-1 px-2 py-1.5 rounded text-xs font-medium border transition-colors text-left " +
        (effectiveEdge === edge
          ? "border-accent bg-accent/15 text-text"
          : "border-edge bg-edge hover:border-accent text-muted") +
        (!enabled ? " opacity-40 cursor-not-allowed" : "")
      }
    >
      <span className="block font-semibold">{label}</span>
      <span className="block text-[10px] text-muted">{hint}</span>
    </button>
  );

  return (
    <div>
      <label className="block text-xs font-medium text-muted mb-1">Motor de inferência</label>
      <div className="flex gap-2">
        {opt(false, "🧠 IA (VLM)", vlmOn ? "Claude · mais rico" : "sem token", vlmOn)}
        {opt(true, "⚡ Local (edge)", edgeOn ? "YOLO · sem token" : "edge indisponível", edgeOn)}
      </div>
      {!vlmOn && (
        <p className="text-[10px] text-warn mt-1">Sem ANTHROPIC_API_KEY — usando motor local.</p>
      )}
    </div>
  );
}
