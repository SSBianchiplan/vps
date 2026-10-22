import { useCallback, useEffect, useState } from "react";
import {
  listEvents,
  listEventCategories,
  listEventSources,
  syncAuditPg,
  type AuditEvent,
  type Category,
  type EventCategory,
  type EventSource,
  type Severity,
} from "../../api/events";
import { btnCls } from "../../lib/ui";
import { MiniChart } from "../MiniChart";

const SEV_STYLE: Record<Severity, { dot: string; chip: string; label: string }> = {
  ok: { dot: "bg-ok", chip: "text-ok border-ok/40", label: "OK" },
  nok: { dot: "bg-nok", chip: "text-nok border-nok/40", label: "NOK" },
  alerta: { dot: "bg-warn", chip: "text-warn border-warn/40", label: "Alerta" },
  warn: { dot: "bg-warn", chip: "text-warn border-warn/40", label: "Aviso" },
  info: { dot: "bg-accent-2", chip: "text-accent-2 border-accent-2/40", label: "Info" },
};

const SEVERITIES: { v: Severity | ""; label: string }[] = [
  { v: "", label: "Toda severidade" },
  { v: "alerta", label: "Alerta" },
  { v: "nok", label: "NOK" },
  { v: "ok", label: "OK" },
  { v: "info", label: "Info" },
];

export function EventsView() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [cats, setCats] = useState<EventCategory[]>([]);
  const [sources, setSources] = useState<EventSource[]>([]);
  const [category, setCategory] = useState<Category | "">("");
  const [severity, setSeverity] = useState<Severity | "">("");
  const [sourceId, setSourceId] = useState<string>("");
  const [q, setQ] = useState<string>("");
  const [auto, setAuto] = useState(true);
  const [loading, setLoading] = useState(false);
  const [syncMsg, setSyncMsg] = useState<string>("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const list = await listEvents({
        category: category || undefined,
        severity: severity || undefined,
        sourceId: sourceId || undefined,
        q: q || undefined,
        limit: 400,
      });
      setEvents(list);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, [category, severity, sourceId, q]);

  const refreshMeta = useCallback(() => {
    listEventCategories().then(setCats).catch(() => undefined);
    listEventSources().then(setSources).catch(() => undefined);
  }, []);

  useEffect(() => { refreshMeta(); }, [refreshMeta]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!auto) return;
    const id = window.setInterval(() => { load(); refreshMeta(); }, 8000);
    return () => window.clearInterval(id);
  }, [auto, load, refreshMeta]);

  const total = cats.reduce((a, c) => a + c.count, 0);

  const doSync = async () => {
    setSyncMsg("sincronizando…");
    try {
      const r = await syncAuditPg();
      setSyncMsg(r.ok ? `✓ ${r.synced} novo(s) · PG total ${r.pg_total}` : `✗ ${r.error}`);
    } catch {
      setSyncMsg("✗ falha ao sincronizar");
    }
    window.setTimeout(() => setSyncMsg(""), 6000);
  };

  return (
    <div className="h-full flex flex-col gap-3 overflow-hidden">
      <div className="flex items-center gap-3 flex-wrap">
        <h2 className="text-lg font-bold">Eventos — rastreabilidade total</h2>
        <span className="text-xs text-muted">{events.length} de {total} registro(s)</span>

        <div className="ml-auto flex items-center gap-2 flex-wrap">
          <input
            className="bg-edge border border-edge rounded-card px-2 py-1.5 text-sm text-text w-40"
            placeholder="buscar…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <select
            className="bg-edge border border-edge rounded-card px-2 py-1.5 text-sm text-text"
            value={severity}
            onChange={(e) => setSeverity(e.target.value as Severity | "")}
          >
            {SEVERITIES.map((s) => <option key={s.v} value={s.v}>{s.label}</option>)}
          </select>
          <select
            className="bg-edge border border-edge rounded-card px-2 py-1.5 text-sm text-text max-w-[180px]"
            value={sourceId}
            onChange={(e) => setSourceId(e.target.value)}
          >
            <option value="">Todas as fontes</option>
            {sources.map((s) => (
              <option key={s.source_id} value={s.source_id}>{s.descricao || s.source_id}</option>
            ))}
          </select>
          <button className={btnCls} onClick={doSync} title="Sincronizar trilha → PostgreSQL">⇪ PG</button>
          <button className={btnCls} onClick={() => setAuto((v) => !v)}>{auto ? "⏸ Auto" : "▶ Auto"}</button>
          <button className={btnCls} onClick={load} disabled={loading}>{loading ? "…" : "↻"}</button>
        </div>
      </div>

      {/* filtro por categoria (chips com contagem) */}
      <div className="flex items-center gap-1.5 flex-wrap">
        <button
          onClick={() => setCategory("")}
          className={"text-xs px-2.5 py-1 rounded-full border transition-colors " +
            (category === "" ? "bg-accent text-onaccent border-accent" : "border-edge text-muted hover:text-text")}
        >
          Tudo <span className="opacity-60">{total}</span>
        </button>
        {cats.map((c) => (
          <button
            key={c.key}
            onClick={() => setCategory(category === c.key ? "" : c.key)}
            className={"text-xs px-2.5 py-1 rounded-full border transition-colors flex items-center gap-1 " +
              (category === c.key ? "bg-accent text-onaccent border-accent" : "border-edge text-muted hover:text-text")}
          >
            <span>{c.icon}</span>{c.label} <span className="opacity-60">{c.count}</span>
          </button>
        ))}
      </div>

      {syncMsg && <div className="text-xs text-muted">{syncMsg}</div>}

      <MiniChart />

      <div className="flex-1 overflow-y-auto scroll-thin">
        {events.length === 0 ? (
          <div className="h-full min-h-[240px] flex items-center justify-center text-muted text-sm">
            Nenhum evento para o filtro — toda ação do sistema (leitura, contagem, detecção, análise,
            alteração de dado, câmera, VPS) aparece aqui.
          </div>
        ) : (
          <ol className="relative border-l border-edge ml-3 space-y-1">
            {events.map((e) => {
              const sev = SEV_STYLE[e.severity] ?? SEV_STYLE.info;
              return (
                <li key={e.event_id} className="ml-4 py-2">
                  <span className={"absolute -left-[7px] mt-1.5 w-3 h-3 rounded-full border-2 border-panel " + sev.dot} />
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-base">{e.icone}</span>
                    <span className="text-sm font-medium text-text">{e.source_label}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded border border-accent/40 text-accent font-mono">
                      {e.action}
                    </span>
                    <span className={"text-[10px] px-1.5 py-0.5 rounded border " + sev.chip}>{sev.label}</span>
                    {e.actor && <span className="text-[10px] text-muted">por {e.actor}</span>}
                    <span className="ml-auto text-xs text-muted whitespace-nowrap">
                      {new Date(e.timestamp).toLocaleString()}
                    </span>
                  </div>
                  <p className="text-sm text-text mt-0.5">{e.summary}</p>
                  <div className="text-[11px] text-muted mt-0.5 flex gap-3 flex-wrap">
                    {e.entity_type && <span>{e.entity_type}{e.entity_id ? `: ${e.entity_id}` : ""}</span>}
                    {e.pipeline && <span>pipeline: {e.pipeline}</span>}
                    {e.latency_ms != null && <span>{e.latency_ms} ms</span>}
                    {e.confidence != null && <span>conf: {(e.confidence * 100).toFixed(0)}%</span>}
                    {e.correlation_id && e.correlation_id !== e.event_id && (
                      <span className="font-mono opacity-70">↪ {e.correlation_id}</span>
                    )}
                  </div>
                </li>
              );
            })}
          </ol>
        )}
      </div>
    </div>
  );
}
