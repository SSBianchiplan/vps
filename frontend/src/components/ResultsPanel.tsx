import type { ReactNode } from "react";
import { useStore } from "../store/useStore";
import { exportUrl } from "../api/client";
import { btnCls } from "../lib/ui";
import type { InferenceResult } from "../types";

function Chip({ children }: { children: ReactNode }) {
  return (
    <span className="inline-block text-xs px-2 py-0.5 rounded bg-edge border border-edge">
      {children}
    </span>
  );
}

function CurrentResult({ res }: { res: InferenceResult }) {
  const rotuloOk = useStore((s) => s.params.ANALISAR.rotulo_ok);
  const r = res.result;

  if (res.mode === "DESCREVER") {
    return (
      <div className="space-y-2">
        <p className="text-sm text-text">{r.descricao}</p>
        {!!r.objetos?.length && (
          <div className="flex flex-wrap gap-1">
            {r.objetos.map((o: string, i: number) => (
              <Chip key={i}>{o}</Chip>
            ))}
          </div>
        )}
        {!!r.alertas?.length && (
          <ul className="text-xs text-nok list-disc pl-4">
            {r.alertas.map((a: string, i: number) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        )}
      </div>
    );
  }

  if (res.mode === "ANALISAR") {
    const ok = r.veredito === rotuloOk;
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-3">
          <span
            className={
              "text-lg font-bold px-3 py-1 rounded " +
              (ok ? "bg-ok/20 text-ok" : "bg-nok/20 text-nok")
            }
          >
            {r.veredito}
          </span>
          <span className="text-xs text-muted">
            confiança {(r.confianca * 100).toFixed(0)}%
          </span>
        </div>
        <p className="text-sm text-text">{r.resumo}</p>
        <ul className="space-y-1">
          {(r.itens_verificados ?? []).map((it: any, i: number) => (
            <li key={i} className="text-xs flex gap-2">
              <span className={it.atende ? "text-ok" : "text-nok"}>{it.atende ? "✓" : "✗"}</span>
              <span className="text-text">
                <b>{it.criterio}</b>
                {it.observacao ? ` — ${it.observacao}` : ""}
              </span>
            </li>
          ))}
        </ul>
      </div>
    );
  }

  if (res.mode === "CONTAR") {
    const c = r.contagens ?? {};
    return (
      <div className="space-y-2">
        <div className="text-3xl font-bold text-accent">{r.total}</div>
        <div className="text-xs text-muted">
          tracks ativos: {r.tracks_ativos ?? 0} · cruzamentos: {r.cruzamentos_linha ?? 0}
        </div>
        <div className="flex flex-wrap gap-1">
          {Object.entries(c).map(([k, v]) => (
            <Chip key={k}>
              {k}: {v as number}
            </Chip>
          ))}
        </div>
      </div>
    );
  }

  if (res.mode === "DETECTAR") {
    const c = r.contagens ?? {};
    return (
      <div className="space-y-2">
        <div className="text-3xl font-bold text-accent">{r.total ?? 0} <span className="text-sm text-muted">objeto(s)</span></div>
        <div className="flex flex-wrap gap-1">
          {Object.entries(c).map(([k, v]) => (
            <Chip key={k}>{k}: {v as number}</Chip>
          ))}
          {!Object.keys(c).length && <span className="text-xs text-muted">nada detectado</span>}
        </div>
      </div>
    );
  }

  if (res.mode === "RASTREAR") {
    const k = r.kpis ?? {};
    const evs = (r.events ?? []) as Array<{ action: string; track_id: number; object_class?: string; direction?: string; dwell_s?: number }>;
    const Cell = ({ label, value, alert }: { label: string; value: ReactNode; alert?: boolean }) => (
      <div className={"rounded-card border px-2 py-1.5 " + (alert ? "border-nok/40 bg-nok/5" : "border-edge bg-edge/40")}>
        <div className="text-[10px] uppercase tracking-wider text-muted">{label}</div>
        <div className={"text-lg font-bold " + (alert ? "text-nok" : "text-text")}>{value}</div>
      </div>
    );
    return (
      <div className="space-y-2">
        <div className="grid grid-cols-3 gap-1.5">
          <Cell label="Tracks" value={r.active ?? 0} />
          <Cell label="Únicos" value={r.unique_total ?? 0} />
          <Cell label="WIP zona" value={r.wip ?? 0} />
          <Cell label="IN" value={r.line_in ?? 0} />
          <Cell label="OUT" value={r.line_out ?? 0} alert={(r.line_out ?? 0) > 0} />
          <Cell label="Dwell méd" value={`${r.dwell_avg_s ?? 0}s`} />
        </div>
        <div className="text-xs text-muted flex flex-wrap gap-x-3 gap-y-0.5">
          {k.CLD_Throughput != null && <span>Throughput: <b className="text-text">{k.CLD_Throughput}/h</b></span>}
          {r.dwell_max_s != null && <span>dwell máx: {r.dwell_max_s}s</span>}
          {(r.dwell_exceeded ?? 0) > 0 && <span className="text-nok">SLA estourado: {r.dwell_exceeded}</span>}
          {Object.entries(r.contagens ?? {}).map(([c, n]) => <Chip key={c}>{c}: {n as number}</Chip>)}
        </div>
        {!!evs.length && (
          <div>
            <div className="text-[10px] uppercase tracking-wider text-accent mb-0.5">Eventos do frame</div>
            <ul className="space-y-0.5">
              {evs.slice(0, 6).map((e, i) => (
                <li key={i} className={"text-xs flex gap-2 " + (e.action === "DWELL_EXCEEDED" ? "text-nok" : "text-muted")}>
                  <span className="font-mono">T-{e.track_id}</span>
                  <span className="text-text">{e.action}{e.direction ? ` ${e.direction}` : ""}</span>
                  {e.dwell_s != null && <span>· {e.dwell_s}s</span>}
                  {e.object_class && <span className="ml-auto">{e.object_class}</span>}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    );
  }

  // LER
  return (
    <ul className="space-y-1">
      {(r.leituras ?? []).map((l: any, i: number) => (
        <li key={i} className="text-sm flex items-center gap-2">
          <span className="font-mono text-text">{l.texto}</span>
          {l.campo && <Chip>{l.campo}</Chip>}
          {l.valido === false && <span className="text-nok text-xs">inválido</span>}
          {l.valido === true && <span className="text-ok text-xs">✓</span>}
        </li>
      ))}
      {!(r.leituras ?? []).length && <li className="text-xs text-muted">nenhuma leitura</li>}
    </ul>
  );
}

export function ResultsPanel() {
  const last = useStore((s) => s.lastResult);
  const log = useStore((s) => s.log);
  const clearLog = useStore((s) => s.clearLog);
  const taskId = last?.task_id ?? null;

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="border-b border-edge pb-3 mb-3 shrink-0 max-h-[40%] overflow-y-auto scroll-thin">
        <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Resultado atual</h3>
        {last ? <CurrentResult res={last} /> : <p className="text-sm text-muted">Aguardando…</p>}
      </div>

      <div className="flex gap-2 mb-3 shrink-0 flex-wrap">
        <a className={btnCls} href={exportUrl(taskId, "csv")} target="_blank" rel="noreferrer">
          Exportar CSV
        </a>
        <a className={btnCls} href={exportUrl(taskId, "json")} target="_blank" rel="noreferrer">
          JSON
        </a>
        <button
          className={btnCls}
          onClick={() => last && navigator.clipboard.writeText(JSON.stringify(last, null, 2))}
        >
          Copiar
        </button>
        <button className={btnCls} onClick={clearLog}>
          Limpar
        </button>
      </div>

      <h3 className="text-xs uppercase tracking-wider text-muted mb-2 shrink-0">Log de eventos <span className="text-muted/60 normal-case">({log.length})</span></h3>
      <div className="flex-1 min-h-0 overflow-y-auto scroll-thin space-y-1 pr-1">
        {log.map((e) => (
          <div key={e.detection_id} className="text-xs text-muted border-b border-edge/50 py-1">
            <span className="text-muted">{new Date(e.timestamp).toLocaleTimeString()}</span>{" "}
            <span className="text-text">{e.mode}</span> · {e.pipeline} · {e.latency_ms}ms
          </div>
        ))}
        {!log.length && <p className="text-xs text-muted">sem eventos</p>}
      </div>
    </div>
  );
}
