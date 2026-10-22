import { useCallback, useEffect, useState } from "react";
import { aerialRecordingUrl, listAerialRecordings, type AerialRecItem } from "../../api/aerial";
import { btnCls } from "../../lib/ui";

const mb = (b: number) => `${(b / 1048576).toFixed(1)} MB`;
const icon = (name: string) => (name.startsWith("drone_") ? "🛸" : name.startsWith("osmo_") ? "📷" : "📹");

export function DownloadsView() {
  const [items, setItems] = useState<AerialRecItem[]>([]);
  const [err, setErr] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setItems(await listAerialRecordings("all"));  // drone + osmo + câmeras IP
  }, []);
  useEffect(() => { refresh(); const iv = window.setInterval(refresh, 5000); return () => window.clearInterval(iv); }, [refresh]);

  const download = useCallback(async (name: string) => {
    try {
      const res = await fetch(aerialRecordingUrl(name));
      if (!res.ok) throw new Error(String(res.status));
      const url = URL.createObjectURL(await res.blob());
      const a = document.createElement("a"); a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 8000);
    } catch (e) { setErr(`download falhou: ${String((e as Error)?.message ?? e)}`); }
  }, []);

  const total = items.reduce((s, i) => s + i.size, 0);

  return (
    <div className="flex flex-col gap-4 min-h-full">
      <div className="flex items-center gap-3 flex-wrap">
        <h2 className="text-lg font-bold">⬇ Downloads</h2>
        <span className="text-xs text-muted">{items.length} arquivo(s) · {mb(total)}</span>
        <button className={btnCls + " ml-auto"} onClick={refresh}>↻ Atualizar</button>
      </div>
      {err && <p className="text-xs text-nok">⚠ {err}</p>}

      {items.length === 0 ? (
        <div className="flex-1 min-h-[240px] flex flex-col items-center justify-center gap-3 border border-dashed border-edge rounded-card text-center px-4">
          <span className="text-4xl">📁</span>
          <p className="text-muted text-sm max-w-sm">Nenhuma gravação ainda. Grave (⏺) na Visão Aérea ou Vídeo Osmo — os arquivos .mp4 aparecem aqui.</p>
        </div>
      ) : (
        <div className="flex-1 scroll-thin">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {items.map((i) => (
              <button key={i.name} onClick={() => download(i.name)} title="Baixar .mp4"
                className="flex items-center gap-3 bg-panel border border-edge rounded-card p-3 hover:border-accent text-left">
                <span className="text-2xl shrink-0">{icon(i.name)}</span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-mono text-text truncate">{i.name}</p>
                  <p className="text-[11px] text-muted">{new Date(i.ts * 1000).toLocaleString()} · {mb(i.size)}</p>
                </div>
                <span className="text-accent text-lg shrink-0">⬇</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
