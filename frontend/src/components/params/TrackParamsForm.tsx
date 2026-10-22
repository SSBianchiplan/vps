import { useStore } from "../../store/useStore";
import { btnCls, csvToList, inputCls, labelCls, selectCls } from "../../lib/ui";

export function TrackParamsForm() {
  const p = useStore((s) => s.params.RASTREAR);
  const setParams = useStore((s) => s.setParams);
  const setDraw = useStore((s) => s.setDraw);
  const setCountingRoi = useStore((s) => s.setCountingRoi);
  const draw = useStore((s) => s.draw);

  return (
    <div className="space-y-3">
      <div>
        <label className={labelCls}>Classes-alvo (vírgula; vazio = todas)</label>
        <input className={inputCls} placeholder="caixa, palete, pessoa, empilhadeira"
          defaultValue={p.classes_alvo.join(", ")}
          onBlur={(e) => setParams("RASTREAR", { classes_alvo: csvToList(e.target.value) })} />
      </div>

      <div>
        <label className={labelCls}>Confiança mínima: {p.conf_threshold.toFixed(2)}</label>
        <input type="range" min={0.05} max={0.9} step={0.05} value={p.conf_threshold}
          onChange={(e) => setParams("RASTREAR", { conf_threshold: Number(e.target.value) })}
          className="w-full accent-accent" />
      </div>

      <div>
        <label className={labelCls}>Algoritmo (tracking-by-detection)</label>
        <select className={selectCls} value={p.algorithm}
          onChange={(e) => setParams("RASTREAR", { algorithm: e.target.value as "bytetrack" | "botsort" })}>
          <option value="bytetrack">ByteTrack (associa baixa confiança)</option>
          <option value="botsort">BoT-SORT (movimento robusto)</option>
        </select>
      </div>

      <div>
        <label className={labelCls}>Geometria — linha (sentido) ou zona (dwell)</label>
        <div className="flex flex-wrap gap-2">
          <button className={btnCls + (draw?.target === "counting" && draw.shape === "line" ? " border-accent" : "")}
            onClick={() => setDraw({ shape: "line", target: "counting" })}>Linha (IN/OUT)</button>
          <button className={btnCls + (draw?.target === "counting" && draw.shape === "zone" ? " border-accent" : "")}
            onClick={() => setDraw({ shape: "zone", target: "counting" })}>Zona (dwell)</button>
          <button className={btnCls} onClick={() => { setCountingRoi(null); setDraw(null); }}>Limpar</button>
        </div>
        {p.counting_roi && (
          <p className="text-xs text-muted mt-1">{p.counting_roi.shape} · {p.counting_roi.points.length} ponto(s)</p>
        )}
      </div>

      <div>
        <label className={labelCls}>SLA de permanência (dwell) — alerta se exceder</label>
        <div className="flex items-center gap-2">
          <input type="number" min={0} className={inputCls + " w-28"} placeholder="ex.: 480"
            value={p.dwell_sla_s ?? ""}
            onChange={(e) => setParams("RASTREAR", { dwell_sla_s: e.target.value ? Number(e.target.value) : null })} />
          <span className="text-xs text-muted">segundos (0/vazio = sem SLA)</span>
        </div>
      </div>

      <label className="flex items-center gap-2 text-sm text-text cursor-pointer">
        <input type="checkbox" checked={p.anonymize_persons}
          onChange={(e) => setParams("RASTREAR", { anonymize_persons: e.target.checked })} />
        🔒 Anonimizar pessoas (LGPD — conta fluxo, não exibe bbox)
      </label>

      <p className="text-[11px] text-muted">
        Identidade no tempo: trajetória, cruzamento com sentido, dwell (cycle time) e contagem por ID único.
        Eventos semânticos (LINE_CROSSED / ZONE_ENTERED / DWELL_EXCEEDED) vão para os Eventos.
      </p>
    </div>
  );
}
