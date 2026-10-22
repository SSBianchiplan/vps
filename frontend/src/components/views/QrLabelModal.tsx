import { useEffect, useState } from "react";
import { otAlarmQr, type AlarmQr } from "../../api/automation";
import { btnCls, btnPrimaryCls } from "../../lib/ui";

export function QrLabelModal({ assetId, onClose }: { assetId?: string | null; onClose: () => void }) {
  const [d, setD] = useState<AlarmQr | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { otAlarmQr(assetId || undefined).then(setD).catch(() => setErr("falha ao gerar QR")); }, [assetId]);

  const print = () => {
    if (!d) return;
    const w = window.open("", "_blank", "width=440,height=600"); if (!w) return;
    w.document.write(`<html><head><title>${d.work_order}</title><style>
      body{font-family:system-ui,Segoe UI,sans-serif;margin:0;padding:18px;color:#0b1220;background:#fff}
      .lbl{border:2px solid #0b1220;border-radius:12px;padding:16px;width:320px}
      .h{font-weight:800;letter-spacing:1px;font-size:11px;color:#0b7a6e}
      .os{font-size:22px;font-weight:800;margin:6px 0}
      .r{font-size:12px;margin:3px 0}.r b{display:inline-block;min-width:64px}
      .qr{display:flex;justify-content:center;margin:10px 0}.qr svg{width:210px;height:210px}
      small{word-break:break-all;color:#666;font-size:9px}</style></head><body><div class="lbl">
      <div class="h">VISIONDESK · RASTREABILIDADE OT</div><div class="os">${d.work_order}</div>
      <div class="r"><b>Ativo:</b> ${d.asset_id}</div>
      <div class="r"><b>Alarme:</b> ${d.alarm ? d.alarm.action + " · " + d.alarm.value : "—"}</div>
      <div class="r"><b>Status:</b> ${d.active ? "🔴 ATIVO" : "histórico / reconhecido"}</div>
      <div class="r"><b>Gerado:</b> ${new Date(d.generated_at).toLocaleString()}</div>
      <div class="qr">${d.svg}</div><small>${d.payload}</small></div>
      <script>window.onload=function(){window.print()}</script></body></html>`);
    w.document.close();
  };

  return (
    <div className="fixed inset-0 z-[130] flex items-center justify-center p-4 bg-black/50" onClick={onClose}>
      <div className="vd-surface border border-edge rounded-card w-full max-w-sm p-4 space-y-3" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2"><h3 className="font-bold">🏷 Etiqueta QR — rastreabilidade</h3><button className="ml-auto text-muted hover:text-text" onClick={onClose}>✕</button></div>
        {err && <p className="text-xs text-nok">{err}</p>}
        {!d && !err && <p className="text-xs text-muted">gerando…</p>}
        {d && (
          <>
            <div className="rounded-card border-2 border-text/80 bg-white text-[#0b1220] p-3">
              <div className="text-[10px] font-extrabold tracking-wider text-[#0b7a6e]">VISIONDESK · OT</div>
              <div className="text-xl font-extrabold">{d.work_order}</div>
              <div className="text-[11px] mt-1 space-y-0.5">
                <div><b>Ativo:</b> {d.asset_id}</div>
                <div><b>Alarme:</b> {d.alarm ? `${d.alarm.action} · ${d.alarm.value}` : "—"}</div>
                <div><b>Status:</b> {d.active ? "🔴 ATIVO" : "histórico"}</div>
              </div>
              <div className="flex justify-center my-2 [&_svg]:w-44 [&_svg]:h-44" dangerouslySetInnerHTML={{ __html: d.svg }} />
              <p className="text-[8px] text-[#666] break-all">{d.payload}</p>
            </div>
            <div className="flex gap-2">
              <button className={btnPrimaryCls} onClick={print}>🖨 Imprimir</button>
              <button className={btnCls} onClick={onClose}>Fechar</button>
            </div>
            <p className="text-[10px] text-muted">QR codifica ativo·tipo·valor·timestamp·OS → leitura em campo abre a ordem de serviço / rastreabilidade.</p>
          </>
        )}
      </div>
    </div>
  );
}
