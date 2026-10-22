import { useStore } from "../../store/useStore";
import { inputCls, labelCls, linesToList, selectCls } from "../../lib/ui";
import { MotorToggle } from "./MotorToggle";

export function AnalyzeParamsForm() {
  const p = useStore((s) => s.params.ANALISAR);
  const setParams = useStore((s) => s.setParams);

  return (
    <div className="space-y-3">
      <MotorToggle mode="ANALISAR" />
      <div>
        <label className={labelCls}>Critérios de inspeção (um por linha)</label>
        {p.prefer_edge && (
          <p className="text-[10px] text-muted mb-1">
            Motor local entende presença/ausência e contagem (ex.: “pessoa”, “sem cachorro”,
            “pelo menos 2 caixas”). Critérios subjetivos exigem o motor IA.
          </p>
        )}
        <textarea
          className={inputCls + " h-24 resize-y"}
          placeholder={"etiqueta presente no canto superior\nparafusos completos\nsem amassados"}
          defaultValue={p.criterios.join("\n")}
          onBlur={(e) => setParams("ANALISAR", { criterios: linesToList(e.target.value) })}
        />
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className={labelCls}>Rótulo OK</label>
          <input
            className={inputCls}
            value={p.rotulo_ok}
            onChange={(e) => setParams("ANALISAR", { rotulo_ok: e.target.value })}
          />
        </div>
        <div>
          <label className={labelCls}>Rótulo NOK</label>
          <input
            className={inputCls}
            value={p.rotulo_nok}
            onChange={(e) => setParams("ANALISAR", { rotulo_nok: e.target.value })}
          />
        </div>
      </div>
      <div>
        <label className={labelCls}>Rubrica (opcional)</label>
        <textarea
          className={inputCls + " h-16 resize-y"}
          value={p.rubrica ?? ""}
          onChange={(e) => setParams("ANALISAR", { rubrica: e.target.value || null })}
        />
      </div>
      <div>
        <label className={labelCls}>Ação ao reprovar (NOK)</label>
        <select
          className={selectCls}
          value={p.acao_nok}
          onChange={(e) =>
            setParams("ANALISAR", {
              acao_nok: e.target.value as "nenhuma" | "alerta" | "mqtt",
            })
          }
        >
          <option value="nenhuma">Nenhuma</option>
          <option value="alerta">Alerta visual</option>
          <option value="mqtt">Publicar em MQTT</option>
        </select>
      </div>
      <label className="flex items-center gap-2 text-sm text-text">
        <input
          type="checkbox"
          checked={p.crop_roi}
          onChange={(e) => setParams("ANALISAR", { crop_roi: e.target.checked })}
        />
        Recortar ROI antes do VLM (foco + economia de tokens)
      </label>
    </div>
  );
}
