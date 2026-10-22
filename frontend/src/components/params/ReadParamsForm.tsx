import { useStore } from "../../store/useStore";
import { csvToList, inputCls, labelCls } from "../../lib/ui";

export function ReadParamsForm() {
  const p = useStore((s) => s.params.LER);
  const setParams = useStore((s) => s.setParams);

  return (
    <div className="space-y-3">
      <div>
        <label className={labelCls}>Idioma</label>
        <input
          className={inputCls}
          value={p.idioma}
          onChange={(e) => setParams("LER", { idioma: e.target.value })}
        />
      </div>
      <div>
        <label className={labelCls}>Padrão esperado (regex de validação)</label>
        <input
          className={inputCls}
          placeholder="ex. OP-\d{4,6}"
          value={p.pattern_regex ?? ""}
          onChange={(e) => setParams("LER", { pattern_regex: e.target.value || null })}
        />
      </div>
      <div>
        <label className={labelCls}>Campos lógicos (separados por vírgula)</label>
        <input
          className={inputCls}
          placeholder="n_op, codigo_peca"
          defaultValue={p.campos_logicos.join(", ")}
          onBlur={(e) => setParams("LER", { campos_logicos: csvToList(e.target.value) })}
        />
      </div>
      <label className="flex items-center gap-2 text-sm text-text">
        <input
          type="checkbox"
          checked={p.prefer_vlm}
          onChange={(e) => setParams("LER", { prefer_vlm: e.target.checked })}
        />
        Forçar VLM (texto irregular/manuscrito)
      </label>
    </div>
  );
}
