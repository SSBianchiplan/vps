import { useStore } from "../../store/useStore";
import { csvToList, inputCls, labelCls } from "../../lib/ui";

export function DetectParamsForm() {
  const p = useStore((s) => s.params.DETECTAR);
  const setParams = useStore((s) => s.setParams);

  return (
    <div className="space-y-3">
      <div>
        <label className={labelCls}>Classes-alvo (vírgula; vazio = todas COCO)</label>
        <input
          className={inputCls}
          placeholder="person, car, dog"
          defaultValue={p.classes_alvo.join(", ")}
          onBlur={(e) => setParams("DETECTAR", { classes_alvo: csvToList(e.target.value) })}
        />
      </div>
      <div>
        <label className={labelCls}>Confiança mínima: {p.conf_threshold.toFixed(2)}</label>
        <input
          type="range" min={0.05} max={0.9} step={0.05} value={p.conf_threshold}
          onChange={(e) => setParams("DETECTAR", { conf_threshold: Number(e.target.value) })}
          className="w-full accent-accent"
        />
      </div>
      <div>
        <label className={labelCls}>Máx. de detecções: {p.max_det}</label>
        <input
          type="range" min={5} max={100} step={5} value={p.max_det}
          onChange={(e) => setParams("DETECTAR", { max_det: Number(e.target.value) })}
          className="w-full accent-accent"
        />
      </div>

      <div className="border-t border-edge pt-2">
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input
            type="checkbox" checked={p.notificar}
            onChange={(e) => setParams("DETECTAR", { notificar: e.target.checked })}
          />
          🔔 Notificar ao detectar (WhatsApp)
        </label>
        {p.notificar && (
          <div className="mt-2">
            <label className={labelCls}>Notificar apenas estas classes (vazio = qualquer)</label>
            <input
              className={inputCls}
              placeholder="person"
              defaultValue={p.notificar_classes.join(", ")}
              onBlur={(e) => setParams("DETECTAR", { notificar_classes: csvToList(e.target.value) })}
            />
            <p className="text-[11px] text-muted mt-1">
              Configure o WhatsApp em <b>Ações → Notificações</b>. Cooldown de 60s por classe.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
