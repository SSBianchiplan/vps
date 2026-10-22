import { useStore } from "../../store/useStore";
import { btnCls, csvToList, inputCls, labelCls, selectCls } from "../../lib/ui";

export function CountParamsForm() {
  const p = useStore((s) => s.params.CONTAR);
  const setParams = useStore((s) => s.setParams);
  const setDraw = useStore((s) => s.setDraw);
  const setCountingRoi = useStore((s) => s.setCountingRoi);
  const draw = useStore((s) => s.draw);

  return (
    <div className="space-y-3">
      <div>
        <label className={labelCls}>Classes-alvo (vírgula; vazio = todas)</label>
        <input
          className={inputCls}
          placeholder="person, box"
          defaultValue={p.classes_alvo.join(", ")}
          onBlur={(e) => setParams("CONTAR", { classes_alvo: csvToList(e.target.value) })}
        />
      </div>
      <div>
        <label className={labelCls}>
          Confiança mínima: {p.conf_threshold.toFixed(2)}
        </label>
        <input
          type="range"
          min={0.05}
          max={0.9}
          step={0.05}
          value={p.conf_threshold}
          onChange={(e) => setParams("CONTAR", { conf_threshold: Number(e.target.value) })}
          className="w-full accent-accent"
        />
      </div>
      <div>
        <label className={labelCls}>Modo de contagem</label>
        <select
          className={selectCls}
          value={p.counting}
          onChange={(e) =>
            setParams("CONTAR", { counting: e.target.value as "instant" | "accumulated" })
          }
        >
          <option value="instant">Instantâneo</option>
          <option value="accumulated">Acumulado (cruzamentos)</option>
        </select>
      </div>
      <div>
        <label className={labelCls}>Linha / zona de contagem</label>
        <div className="flex flex-wrap gap-2">
          <button
            className={btnCls + (draw?.target === "counting" && draw.shape === "line" ? " border-accent" : "")}
            onClick={() => setDraw({ shape: "line", target: "counting" })}
          >
            Desenhar linha
          </button>
          <button
            className={btnCls + (draw?.target === "counting" && draw.shape === "zone" ? " border-accent" : "")}
            onClick={() => setDraw({ shape: "zone", target: "counting" })}
          >
            Desenhar zona
          </button>
          <button
            className={btnCls}
            onClick={() => {
              setCountingRoi(null);
              setDraw(null);
            }}
          >
            Limpar
          </button>
        </div>
        {p.counting_roi && (
          <p className="text-xs text-muted mt-1">
            {p.counting_roi.shape} com {p.counting_roi.points.length} ponto(s)
          </p>
        )}
      </div>
    </div>
  );
}
