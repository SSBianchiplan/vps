import { useCallback, useEffect, useState } from "react";
import { useStore } from "../../store/useStore";
import {
  otAck, otAlarms, otEvents, otSimulate, otStatus, otVisionInspect,
  type OtAlarm, type OtEvent, type OtStatus,
} from "../../api/automation";
import { btnCls, btnPrimaryCls } from "../../lib/ui";
import { SupervisorioEditor } from "./SupervisorioEditor";
import { QrLabelModal } from "./QrLabelModal";

function latest(events: OtEvent[], asset: string, action: string): string | null {
  const e = events.find((x) => x.asset_id === asset && x.action === action);
  return e ? e.value : null;
}
const ASSET_LABEL: Record<string, { name: string; path: string; icon: string }> = {
  "M-301": { name: "M-301 · Transportador (SINAMICS)", path: "OPC UA · PROFIdrive", icon: "⚙" },
  "RIO-L1": { name: "RIO-L1 · Remota I/O (ET 200SP)", path: "PROFINET · diagnóstico", icon: "🔌" },
  "TK-12": { name: "TK-12 · Nível de Tanque", path: "analógico · OPC UA", icon: "🛢" },
  "INJ-07": { name: "INJ-07 · Injetora (PackML)", path: "OPC UA companion", icon: "🏭" },
  "PR-22": { name: "PR-22 · Prensa (Comfort Panel)", path: "caminho B · VISÃO", icon: "👁" },
};
const ORDER = ["M-301", "RIO-L1", "TK-12", "INJ-07", "PR-22"];
const RUN = new Set(["RUN", "EXECUTE", "AUTO"]);
const SEV = (a: string) => (a === "ALARM_RAISED" || a === "IO_FAULT" ? "text-nok" : a === "MACHINE_STATE" ? "text-accent" : "text-muted");

export function AutomacaoView() {
  const connected = useStore((s) => s.connected);
  const [tab, setTab] = useState<"sup" | "ctrl" | "scada">("sup");
  const [ev, setEv] = useState<OtEvent[]>([]);
  const [st, setSt] = useState<OtStatus | null>(null);
  const [alarms, setAlarms] = useState<OtAlarm[]>([]);
  const [busy, setBusy] = useState(false);
  const [auto, setAuto] = useState(false);
  const [hz, setHz] = useState(2500);
  const [qr, setQr] = useState<string | null | undefined>(undefined);
  const [vmsg, setVmsg] = useState("");

  const load = useCallback(() => {
    otEvents().then(setEv).catch(() => undefined);
    otStatus().then(setSt).catch(() => undefined);
    otAlarms().then(setAlarms).catch(() => undefined);
  }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!auto) return;
    const id = window.setInterval(async () => { await otSimulate(); load(); }, hz);
    return () => window.clearInterval(id);
  }, [auto, hz, load]);

  const sim = async (asset?: string) => { setBusy(true); try { await otSimulate(asset); load(); } finally { setBusy(false); } };
  const ack = async (asset: string) => { await otAck(asset); load(); };
  const vision = async (asset?: string) => { const r = await otVisionInspect(asset); load(); setVmsg(`👁 ${r.result}${r.defect ? ": " + r.defect : ""}`); window.setTimeout(() => setVmsg(""), 3000); };

  const stateOf = (id: string) => latest(ev, id, "MACHINE_STATE");
  const alarmOf = (id: string) => alarms.find((a) => a.asset_id === id && a.active);
  const activeAlarms = alarms.filter((a) => a.active);

  // ── Faceplate (Supervisão) ──
  const faceplate = (id: string) => {
    const m = ASSET_LABEL[id]; const state = stateOf(id);
    const counter = latest(ev, id, "COUNTER_READ"); const pv = latest(ev, id, "PROCESS_VALUE_READ");
    const al = alarmOf(id); const fault = state === "FAULT" || !!al;
    return (
      <div key={id} className={"rounded-card border p-3 " + (fault ? "border-nok/50 bg-nok/5" : "border-edge bg-edge/30")}>
        <div className="flex items-center gap-2 mb-1">
          <span>{m.icon}</span><span className="text-sm font-semibold text-text flex-1 truncate">{m.name}</span>
          {state && <span className={"text-[10px] px-1.5 py-0.5 rounded-full " + (fault ? "bg-nok/20 text-nok" : RUN.has(state) ? "bg-ok/20 text-ok" : "bg-edge text-muted")}>● {state}</span>}
        </div>
        <div className="text-[11px] text-muted flex flex-wrap gap-x-3 font-mono">
          {counter != null && <span>cont: <b className="text-text">{counter}</b></span>}
          {pv != null && <span>valor: <b className="text-text">{pv}</b></span>}
          {al && <span className="text-nok">⚠ {al.value}</span>}
        </div>
        <div className="flex items-center justify-between mt-1.5">
          <span className="text-[9px] text-muted">{m.path}</span>
          <button className="text-[10px] text-accent hover:underline" onClick={() => sim(id)}>ler ↻</button>
        </div>
      </div>
    );
  };

  // ── Tile grande (Controladora / mímico) ──
  const tile = (id: string) => {
    const m = ASSET_LABEL[id]; const state = stateOf(id) || "—";
    const al = alarmOf(id); const fault = state === "FAULT" || !!al;
    const key = latest(ev, id, "COUNTER_READ") ?? latest(ev, id, "PROCESS_VALUE_READ");
    const dot = fault ? "bg-nok animate-pulse" : RUN.has(state) ? "bg-ok" : state === "—" ? "bg-muted" : "bg-warn";
    return (
      <button key={id} onClick={() => sim(id)} title="ler ativo (read-only)"
        className={"text-left rounded-card border p-3 transition-all hover:border-accent " + (fault ? "border-nok/60 bg-nok/10" : "border-edge bg-edge/40")}>
        <div className="flex items-center gap-2">
          <span className={"w-3 h-3 rounded-full shrink-0 " + dot} />
          <span className="text-lg">{m.icon}</span>
          <span className="text-xs font-mono text-muted ml-auto">{id}</span>
        </div>
        <div className="text-sm font-bold mt-1.5">{state}</div>
        {key != null && <div className="text-[11px] text-muted font-mono">{key}</div>}
        {al && <div className="text-[10px] text-nok truncate mt-0.5">⚠ {al.value}</div>}
      </button>
    );
  };

  const Gauge = ({ label, v, unit = "%" }: { label: string; v: number | null; unit?: string }) => (
    <div className="flex-1 min-w-[90px]">
      <div className="flex justify-between text-[10px] text-muted uppercase"><span>{label}</span><span className="font-bold text-text">{v ?? "—"}{v != null ? unit : ""}</span></div>
      <div className="h-2 bg-edge rounded overflow-hidden mt-0.5"><div className="h-full bg-accent" style={{ width: `${Math.min(100, v ?? 0)}%` }} /></div>
    </div>
  );

  return (
    <div className="flex flex-col gap-3 min-h-full lg:h-full lg:min-h-0">
      <div className="flex items-center gap-2 flex-wrap shrink-0">
        <h2 className="text-lg font-bold">🏭 Automação Industrial</h2>
        <div className="flex rounded-card border border-edge overflow-hidden">
          {([["sup", "📊 Supervisão"], ["ctrl", "🎛 Controladora"], ["scada", "🖥 Supervisório"]] as const).map(([k, l]) => (
            <button key={k} onClick={() => setTab(k)}
              className={"px-3 py-1.5 text-sm font-semibold transition-colors " + (tab === k ? "bg-accent text-onaccent" : "bg-edge text-muted hover:text-text")}>{l}</button>
          ))}
        </div>
        <span className="ml-auto flex items-center gap-2">
          <button className={btnCls} onClick={() => setAuto((v) => !v)}>{auto ? "⏸ Auto" : "▶ Auto"}</button>
          <button className={btnPrimaryCls} onClick={() => sim()} disabled={busy}>{busy ? "…" : "▶ Ler tudo"}</button>
        </span>
      </div>

      {tab === "scada" ? (
        <div className="flex-1 min-h-0"><SupervisorioEditor /></div>
      ) : tab === "sup" ? (
        <div className="flex-1 grid grid-cols-1 lg:grid-cols-[1fr_330px] gap-4 min-h-0">
          <section className="bg-panel rounded-card border border-edge p-4 overflow-y-auto scroll-thin space-y-4">
            <div>
              <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Componentes (telas industriais · §14)</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">{ORDER.map(faceplate)}</div>
            </div>
            <div>
              <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Eventos OT (timestamp da fonte)</h3>
              <div className="space-y-0.5 max-h-[40vh] overflow-y-auto scroll-thin">
                {ev.length === 0 ? <p className="text-xs text-muted">Rode a leitura para gerar eventos.</p> : ev.slice(0, 60).map((e, i) => (
                  <div key={i} className="text-[11px] flex items-center gap-2 border-b border-edge/40 py-0.5">
                    <span className="text-muted whitespace-nowrap">{new Date(e.source_ts).toLocaleTimeString()}</span>
                    <span className="font-mono text-text">{e.asset_id}</span>
                    <span className={"font-semibold " + SEV(e.action)}>{e.action}</span>
                    <span className="text-muted truncate">= {e.value}</span>
                    <span className={"ml-auto text-[9px] px-1 rounded " + (e.source === "SCREEN" ? "bg-warn/20 text-warn" : "bg-accent-2/20 text-accent-2")}>{e.source}</span>
                  </div>
                ))}
              </div>
            </div>
          </section>
          <aside className="bg-panel rounded-card border border-edge p-4 overflow-y-auto scroll-thin space-y-4">
            {st && <KpiPanel st={st} />}
          </aside>
        </div>
      ) : (
        // ── CONTROLADORA (console supervisório) ──
        <div className="flex-1 grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-4 min-h-0">
          <section className="bg-panel rounded-card border border-edge p-4 overflow-y-auto scroll-thin space-y-4">
            {/* barra de estado do sistema */}
            <div className="flex items-center gap-3 flex-wrap rounded-card border border-edge bg-edge/30 px-3 py-2">
              <span className={"flex items-center gap-1.5 text-xs " + (connected ? "text-ok" : "text-nok")}><span className={"w-2 h-2 rounded-full " + (connected ? "bg-ok" : "bg-nok")} />{connected ? "sistema online" : "offline"}</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded-full border border-ok/40 text-ok">🔒 read-only</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded-full border border-edge text-muted">Purdue {st?.purdue_zone}</span>
              <span className={"text-[10px] px-1.5 py-0.5 rounded-full border " + (st?.opcua_available ? "border-ok/40 text-ok" : "border-edge text-muted")}>OPC UA {st?.opcua_available ? "✓" : "lib ausente"}</span>
              {activeAlarms.length > 0 && <span className="ml-auto text-[11px] text-nok font-bold animate-pulse">🚨 {activeAlarms.length} alarme(s) ativo(s)</span>}
            </div>
            {/* mímico */}
            <div>
              <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Mímico do chão (clique = ler · observador)</h3>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">{ORDER.map(tile)}</div>
            </div>
            {/* alarmes ativos + ack */}
            <div>
              <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Alarmes ativos</h3>
              {activeAlarms.length === 0 ? <p className="text-xs text-muted">Sem alarmes ativos.</p> : (
                <div className="space-y-1">
                  {activeAlarms.map((a, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs border border-nok/30 bg-nok/5 rounded-card px-2 py-1.5">
                      <span className="text-nok font-bold">🚨 {a.asset_id}</span>
                      <span className="text-text truncate flex-1">{a.action} · {a.value}</span>
                      <span className="text-[10px] text-muted whitespace-nowrap">{new Date(a.source_ts).toLocaleTimeString()}</span>
                      <button className="text-[10px] px-2 py-0.5 rounded border border-edge hover:border-accent" onClick={() => setQr(a.asset_id)}>🏷 QR</button>
                      <button className="text-[10px] px-2 py-0.5 rounded border border-edge hover:border-accent" onClick={() => ack(a.asset_id)}>reconhecer</button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>
          {/* painel de controle supervisório */}
          <aside className="bg-panel rounded-card border border-edge p-4 overflow-y-auto scroll-thin space-y-4">
            <section className="border-b border-edge pb-3">
              <h3 className="text-xs uppercase tracking-wider text-muted mb-2">OEE ao vivo</h3>
              {st && <div className="flex gap-2 flex-wrap"><Gauge label="OEE" v={st.CLD_OEE} /><Gauge label="Disponib." v={st.CLD_Machine_Availability} /></div>}
              {st && <p className="text-[11px] text-muted mt-2 font-mono">produção {st.CLD_Production_Count} · ciclo {st.CLD_Cycle_Time_Observed ?? "—"}s · IO faults {st.CLD_IO_Fault_Rate}</p>}
            </section>
            <section className="border-b border-edge pb-3">
              <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Controles (supervisório)</h3>
              <button className={btnPrimaryCls + " w-full"} onClick={() => sim()} disabled={busy}>▶ Ler tudo agora</button>
              <button className={btnCls + " w-full mt-2"} onClick={() => vision()}>👁 Inspeção de visão (caminho B)</button>
              {vmsg && <p className="text-[11px] text-accent mt-1">{vmsg}</p>}
              <label className="flex items-center gap-2 mt-2 text-sm text-text cursor-pointer">
                <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} /> Auto-poll ({(hz / 1000).toFixed(1)}s)
              </label>
              <input type="range" min={1000} max={8000} step={500} value={hz} onChange={(e) => setHz(Number(e.target.value))} className="w-full accent-accent mt-1" />
              <p className="text-[10px] text-muted mt-2">⚠ Console <b>observador</b>: lê, reconhece alarmes e amostra — <b>nunca escreve no PLC</b> (regra de ouro OT). Escrita/comando exigiria autorização + análise de risco.</p>
            </section>
            <section>
              <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Estados</h3>
              <div className="space-y-1">
                {ORDER.map((id) => { const s = stateOf(id) || "—"; const f = s === "FAULT" || !!alarmOf(id);
                  return <div key={id} className="flex items-center gap-2 text-xs"><span className={"w-2 h-2 rounded-full " + (f ? "bg-nok" : RUN.has(s) ? "bg-ok" : "bg-muted")} /><span className="font-mono text-muted">{id}</span><span className="ml-auto text-text">{s}</span></div>; })}
              </div>
            </section>
          </aside>
        </div>
      )}
      {qr !== undefined && <QrLabelModal assetId={qr} onClose={() => setQr(undefined)} />}
    </div>
  );
}

function KpiPanel({ st }: { st: OtStatus }) {
  return (
    <>
      <section className="border-b border-edge pb-3">
        <h3 className="text-xs uppercase tracking-wider text-muted mb-2">OEE &amp; KPIs (CLD_)</h3>
        <div className="grid grid-cols-2 gap-1.5 text-sm">
          <div className="rounded border border-edge bg-edge/40 px-2 py-1"><div className="text-[10px] text-muted uppercase">OEE</div><div className="font-bold text-accent">{st.CLD_OEE}%</div></div>
          <div className="rounded border border-edge bg-edge/40 px-2 py-1"><div className="text-[10px] text-muted uppercase">Disponib.</div><div className="font-bold">{st.CLD_Machine_Availability}%</div></div>
          <div className="rounded border border-edge bg-edge/40 px-2 py-1"><div className="text-[10px] text-muted uppercase">Produção</div><div className="font-bold">{st.CLD_Production_Count}</div></div>
          <div className="rounded border border-edge bg-edge/40 px-2 py-1"><div className="text-[10px] text-muted uppercase">Ciclo obs.</div><div className="font-bold">{st.CLD_Cycle_Time_Observed ?? "—"}s</div></div>
          <div className="rounded border border-edge bg-edge/40 px-2 py-1"><div className="text-[10px] text-muted uppercase">IO faults</div><div className={"font-bold " + (st.CLD_IO_Fault_Rate ? "text-warn" : "")}>{st.CLD_IO_Fault_Rate}</div></div>
          <div className="rounded border border-edge bg-edge/40 px-2 py-1"><div className="text-[10px] text-muted uppercase">Amostras</div><div className="font-bold">{st.samples}</div></div>
        </div>
        <p className="text-[10px] text-muted mt-1">Reconciliação: {st.CLD_Count_Reconciliation}</p>
      </section>
      <section>
        <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Segurança OT</h3>
        <div className="flex flex-wrap gap-1">
          <span className="text-[10px] px-1.5 py-0.5 rounded-full border border-ok/40 text-ok">🔒 read-only</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded-full border border-edge text-muted">Purdue: {st.purdue_zone}</span>
          <span className={"text-[10px] px-1.5 py-0.5 rounded-full border " + (st.opcua_available ? "border-ok/40 text-ok" : "border-edge text-muted")}>OPC UA {st.opcua_available ? "✓" : "lib ausente"}</span>
        </div>
        <p className="text-[11px] text-muted mt-2">Observador: lê estado/contador/alarme/processo → eventos sob Tag-ID → OEE, ocorrências, APS, reconciliação. <b>Nunca escreve no PLC.</b></p>
      </section>
    </>
  );
}
