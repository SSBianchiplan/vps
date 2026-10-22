import { useStore } from "../store/useStore";

export function HealthBar() {
  const health = useStore((s) => s.health);
  const connected = useStore((s) => s.connected);
  const caps = useStore((s) => s.capabilities);

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted px-1 py-2">
      <span className="flex items-center gap-1.5">
        <span
          className={"w-2 h-2 rounded-full " + (connected ? "bg-ok" : "bg-nok")}
        />
        {connected ? "Conectado" : "Desconectado"}
      </span>
      <span>FPS: <b className="text-text">{health?.fps?.toFixed(0) ?? "—"}</b></span>
      <span>
        Latência: <b className="text-text">{health ? `${Math.round(health.avg_latency_ms)} ms` : "—"}</b>
      </span>
      <span>Pipeline: <b className="text-text">{health?.pipeline ?? "—"}</b></span>
      <span>Modelo: <b className="text-text">{health?.model_active ?? "—"}</b></span>
      {caps && (
        <span className="ml-auto">
          edge {caps.edge_detector || caps.edge_ocr ? "✓" : "✗"} · vlm {caps.vlm ? "✓" : "✗"}
        </span>
      )}
    </div>
  );
}
