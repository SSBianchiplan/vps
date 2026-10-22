import type { ReactNode } from "react";
import type { CameraDevice } from "../hooks/useCamera";
import { useStore, CAPTURE_PRESETS } from "../store/useStore";
import { inputCls, labelCls } from "../lib/ui";
import { SourceSelector } from "./SourceSelector";
import { ModeSelector } from "./ModeSelector";
import { ReadParamsForm } from "./params/ReadParamsForm";
import { CountParamsForm } from "./params/CountParamsForm";
import { DetectParamsForm } from "./params/DetectParamsForm";
import { TrackParamsForm } from "./params/TrackParamsForm";
import { DescribeParamsForm } from "./params/DescribeParamsForm";
import { AnalyzeParamsForm } from "./params/AnalyzeParamsForm";

interface Props {
  devices: CameraDevice[];
  deviceId: string | null;
  active: boolean;
  error: string | null;
  onStart: (id?: string | null) => void;
  onStop: () => void;
  onSelectDevice: (id: string) => void;
  onScreenCapture: () => void;
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="border-b border-edge pb-4">
      <h3 className="text-xs uppercase tracking-wider text-muted mb-2">{title}</h3>
      {children}
    </section>
  );
}

export function ConfigPanel(props: Props) {
  const mode = useStore((s) => s.mode);
  const prompt = useStore((s) => s.prompt);
  const setPrompt = useStore((s) => s.setPrompt);
  const draw = useStore((s) => s.draw);
  const setDraw = useStore((s) => s.setDraw);
  const roi = useStore((s) => s.roi);
  const setRoi = useStore((s) => s.setRoi);
  const captureWidth = useStore((s) => s.captureWidth);
  const setCaptureWidth = useStore((s) => s.setCaptureWidth);

  const showPrompt = mode === "DESCREVER" || mode === "ANALISAR" || mode === "DETECTAR";

  return (
    <div className="space-y-4">
      <Section title="Fonte">
        <SourceSelector {...props} />
      </Section>

      <Section title="Captura (resolução)">
        <label className={labelCls}>Resolução de captura/inferência</label>
        <select
          className={inputCls}
          value={captureWidth}
          onChange={(e) => setCaptureWidth(Number(e.target.value))}
        >
          {CAPTURE_PRESETS.map((p) => (
            <option key={p.w} value={p.w}>{p.label}</option>
          ))}
        </select>
        <p className="text-[11px] text-muted mt-1">
          Menor = mais rápido (menos banda/CPU); maior = mais detalhe. Vale p/ dispositivo, câmera IP e preview.
        </p>
      </Section>

      <Section title="Modo">
        <ModeSelector />
      </Section>

      <Section title="Parâmetros">
        {mode === "LER" && <ReadParamsForm />}
        {mode === "CONTAR" && <CountParamsForm />}
        {mode === "DETECTAR" && <DetectParamsForm />}
        {mode === "RASTREAR" && <TrackParamsForm />}
        {mode === "DESCREVER" && <DescribeParamsForm />}
        {mode === "ANALISAR" && <AnalyzeParamsForm />}
      </Section>

      {showPrompt && (
        <Section title="Instrução livre (prompt)">
          <textarea
            className={inputCls + " h-20 resize-y"}
            placeholder="Contexto/instrução adicional para o VLM"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
          />
        </Section>
      )}

      <Section title="Região de interesse (ROI)">
        <label className={labelCls}>
          Desenhe sobre o vídeo. Usada para foco (ANALISAR/DESCREVER) e filtro (LER).
        </label>
        <div className="flex flex-wrap gap-2">
          {(["rect", "line", "zone"] as const).map((shape) => (
            <button
              key={shape}
              onClick={() => setDraw({ shape, target: "roi" })}
              className={
                "px-3 py-1.5 rounded text-sm border bg-edge transition-colors " +
                (draw?.target === "roi" && draw.shape === shape
                  ? "border-accent"
                  : "border-edge hover:border-accent")
              }
            >
              {shape === "rect" ? "Retângulo" : shape === "line" ? "Linha" : "Zona"}
            </button>
          ))}
          <button
            className="px-3 py-1.5 rounded text-sm border border-edge bg-edge hover:border-accent"
            onClick={() => {
              setRoi(null);
              setDraw(null);
            }}
          >
            Limpar
          </button>
        </div>
        {roi && (
          <p className="text-xs text-muted mt-1">
            ROI: {roi.shape} ({roi.points.length} ponto(s))
          </p>
        )}
        {draw && (
          <p className="text-xs text-accent mt-1">
            Desenhando {draw.shape} → {draw.target === "roi" ? "ROI" : "contagem"}
            {draw.shape === "zone" ? " (clique pontos; duplo-clique finaliza)" : " (arraste no vídeo)"}
          </p>
        )}
      </Section>
    </div>
  );
}
