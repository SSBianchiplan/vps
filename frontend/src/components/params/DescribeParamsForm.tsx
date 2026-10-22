import { useStore } from "../../store/useStore";
import { inputCls, labelCls, selectCls } from "../../lib/ui";
import { MotorToggle } from "./MotorToggle";

export function DescribeParamsForm() {
  const p = useStore((s) => s.params.DESCREVER);
  const setParams = useStore((s) => s.setParams);

  return (
    <div className="space-y-3">
      <MotorToggle mode="DESCREVER" />
      <div>
        <label className={labelCls}>Foco da descrição</label>
        <input
          className={inputCls}
          placeholder="ex. estado da esteira e das caixas"
          value={p.foco ?? ""}
          onChange={(e) => setParams("DESCREVER", { foco: e.target.value || null })}
        />
      </div>
      <div>
        <label className={labelCls}>Nível de detalhe</label>
        <select
          className={selectCls}
          value={p.nivel_detalhe}
          onChange={(e) =>
            setParams("DESCREVER", {
              nivel_detalhe: e.target.value as "baixo" | "medio" | "alto",
            })
          }
        >
          <option value="baixo">Baixo</option>
          <option value="medio">Médio</option>
          <option value="alto">Alto</option>
        </select>
      </div>
      <p className="text-xs text-muted">
        Motor IA descreve em linguagem natural; o local sintetiza a cena a partir
        das detecções (YOLO). Use “Snapshot” para economizar custo no modo IA.
      </p>
    </div>
  );
}
