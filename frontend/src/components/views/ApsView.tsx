import { useCallback, useEffect, useMemo, useState } from "react";
import {
  compareAps, ctpAps, expediteOp, generateSchedule, getApsKpis, getApsLoad, getApsResources, getApsRules,
  getSchedule, publishSchedule, upsertResource,
  type CompareRow, type ResLoad, type Resource, type ScheduleRow,
} from "../../api/vps";

const PALETTE = ["#3b82f6", "#22c55e", "#f59e0b", "#ef4444", "#a855f7", "#14b8a6", "#ec4899", "#84cc16"];
const ms = (s: string) => new Date(s).getTime();
const fmt = (s: string) => new Date(s).toLocaleString([], { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });

const KPI = [
  { k: "CLD_Capacity_Utilization", l: "Utilização", suf: "%" },
  { k: "CLD_Makespan_h", l: "Makespan", suf: "h" },
  { k: "CLD_Schedule_Adherence_APS", l: "Aderência", suf: "%" },
  { k: "CLD_Schedule_Variance_min", l: "Variância", suf: "min" },
  { k: "CLD_Changeover_Time_min", l: "Setup total", suf: "min" },
  { k: "CLD_Operations", l: "Operações", suf: "" },
];

function Gantt({ rows, colorOf }: { rows: ScheduleRow[]; colorOf: (tag: string) => string }) {
  const t0 = Math.min(...rows.map((r) => ms(r.planned_start)));
  const t1 = Math.max(...rows.flatMap((r) => [ms(r.planned_end), r.actual_end ? ms(r.actual_end) : 0]));
  const span = Math.max(1, t1 - t0);
  const byRes: Record<string, ScheduleRow[]> = {};
  rows.forEach((r) => (byRes[r.resource_key] ??= []).push(r));
  return (
    <div className="rounded-card border border-edge p-3" style={{ background: "var(--chart-bg)" }}>
      <div className="flex justify-between text-[10px] text-muted mb-2"><span>{fmt(new Date(t0).toISOString())}</span><span>{fmt(new Date(t1).toISOString())}</span></div>
      <div className="space-y-1.5">
        {Object.entries(byRes).map(([rk, ops]) => (
          <div key={rk} className="flex items-center gap-2">
            <span className="w-24 shrink-0 text-[10px] truncate" style={{ color: "var(--chart-axis)" }} title={rk}>{rk.replace("res_", "")}</span>
            <div className="relative flex-1 h-6 rounded" style={{ background: "var(--chart-grid)" }}>
              {ops.map((o) => {
                const left = ((ms(o.planned_start) - t0) / span) * 100;
                const w = Math.max(0.6, ((ms(o.planned_end) - ms(o.planned_start)) / span) * 100);
                const late = o.variance_min != null && o.variance_min > 30;
                return (
                  <div key={o.schedule_id} className="absolute top-0.5 h-5 rounded-sm overflow-hidden text-[8px] text-white/90 px-1 leading-5 whitespace-nowrap"
                    style={{ left: `${left}%`, width: `${w}%`, background: colorOf(o.tag_id), outline: late ? "1.5px solid var(--nok)" : "none" }}
                    title={`${o.tag_id.split(":")[3]} · ${o.operation} · ${fmt(o.planned_start)}→${fmt(o.planned_end)}${o.variance_min != null ? ` · var ${o.variance_min}min` : ""}`}>
                    {o.operation}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
      <p className="text-[10px] text-muted mt-2">Barra = operação planejada (cor por OP) · contorno vermelho = real estourou o plano (variância &gt; 30min, da visão).</p>
    </div>
  );
}

function ResourceCard({ r, onSaved }: { r: Resource; onSaved: () => void }) {
  const [cap, setCap] = useState(String(r.capacity));
  const [skills, setSkills] = useState(r.skills ?? "");
  const save = async (patch: Partial<Resource>) => { await upsertResource({ ...r, capacity: Number(cap), skills, ...patch }); onSaved(); };
  return (
    <div className={"border rounded-card p-2.5 " + (r.status === "ativo" ? "bg-panel border-edge" : "bg-panel/50 border-edge/50 opacity-60")}>
      <p className="text-sm font-medium truncate">{r.name}</p>
      <div className="flex items-center gap-1 mt-1 text-[10px]">
        <span className="text-muted">cap</span>
        <input value={cap} onChange={(e) => setCap(e.target.value)} onBlur={() => save({})} className="w-9 bg-edge border border-edge rounded px-1 py-0.5 text-center" />
        <input value={skills} onChange={(e) => setSkills(e.target.value)} onBlur={() => save({})} placeholder="skills" className="flex-1 min-w-0 bg-edge border border-edge rounded px-1 py-0.5" />
      </div>
      <button onClick={() => save({ status: r.status === "ativo" ? "inativo" : "ativo" })}
        className={"mt-1.5 text-[10px] px-2 py-0.5 rounded border " + (r.status === "ativo" ? "border-edge text-muted hover:border-nok" : "border-ok/50 text-ok")}>
        {r.status === "ativo" ? "inativar" : "ativar"}
      </button>
    </div>
  );
}

export function ApsView() {
  const [scenario, setScenario] = useState("base");
  const [scenarios, setScenarios] = useState<string[]>(["base"]);
  const [rule, setRule] = useState("prioridade");
  const [rules, setRules] = useState<{ key: string; label: string }[]>([]);
  const [rows, setRows] = useState<ScheduleRow[]>([]);
  const [kpis, setKpis] = useState<Record<string, number | string | boolean | null>>({});
  const [load, setLoad] = useState<ResLoad[]>([]);
  const [resources, setResources] = useState<Resource[]>([]);
  const [busy, setBusy] = useState(false);
  const [newRes, setNewRes] = useState("");
  const [cmp, setCmp] = useState<CompareRow[] | null>(null);
  const [ctpQty, setCtpQty] = useState("12");
  const [ctpDue, setCtpDue] = useState("");
  const [ctp, setCtp] = useState<{ ctp_end: string; lead_h: number; on_time: boolean | null } | null>(null);

  const reload = useCallback(() => {
    getSchedule(scenario).then((d) => { setRows(d.rows); setScenarios(d.scenarios.length ? d.scenarios : ["base"]); }).catch(() => undefined);
    getApsKpis(scenario).then(setKpis).catch(() => undefined);
    getApsLoad(scenario).then((d) => setLoad(d.load)).catch(() => undefined);
    getApsResources().then((d) => setResources(d.resources)).catch(() => undefined);
  }, [scenario]);
  useEffect(() => { reload(); }, [reload]);
  useEffect(() => { getApsRules().then((d) => setRules(d.rules)).catch(() => undefined); }, []);

  const gen = async () => { setBusy(true); try { await generateSchedule(scenario, rule); reload(); } finally { setBusy(false); } };
  const pub = async () => { await publishSchedule(scenario); reload(); };
  const addRes = async () => { if (newRes.trim()) { await upsertResource({ name: newRes.trim(), capacity: 1 }); setNewRes(""); reload(); } };
  const doCompare = async () => { setCmp((await compareAps()).comparison); };
  const applyRule = async (rl: string) => { setRule(rl); setScenario("base"); await generateSchedule("base", rl); setCmp(null); reload(); };
  const doCtp = async () => { setCtp(await ctpAps(Number(ctpQty), ctpDue || undefined)); };
  const expedite = async (tag: string) => { setBusy(true); try { await expediteOp(tag); reload(); } finally { setBusy(false); } };

  const tags = useMemo(() => Array.from(new Set(rows.map((r) => r.tag_id))), [rows]);
  const colorOf = (tag: string) => PALETTE[tags.indexOf(tag) % PALETTE.length];
  const published = rows.some((r) => r.published);
  const replan = kpis.CLD_Replan_Suggested === true;

  return (
    <div className="flex flex-col gap-3 min-h-full">
      <div className="flex items-center gap-3 flex-wrap border-b border-edge pb-2">
        <h2 className="text-base font-bold flex items-center gap-2">📅 APS — Planejamento Avançado
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent/15 text-accent">plan → execute → sense → replan</span>
        </h2>
        {published && <span className="text-[11px] px-2 py-0.5 rounded-full bg-ok/15 text-ok">publicado</span>}
        {replan && <span className="text-[11px] px-2 py-0.5 rounded-full bg-nok/15 text-nok">⚠ replano sugerido ({String(kpis.CLD_Breached_Ops)} op. estourou)</span>}
      </div>

      <div className="flex items-center gap-2 flex-wrap text-xs">
        <span className="text-muted uppercase tracking-wider">Cenário</span>
        <input value={scenario} onChange={(e) => setScenario(e.target.value)} list="scn" className="bg-edge border border-edge rounded px-2 py-1 text-xs w-32" />
        <datalist id="scn">{scenarios.map((s) => <option key={s} value={s} />)}</datalist>
        <span className="text-muted uppercase tracking-wider ml-1">Regra</span>
        <select value={rule} onChange={(e) => setRule(e.target.value)} className="bg-edge border border-edge rounded px-2 py-1 text-xs">
          {rules.map((r) => <option key={r.key} value={r.key}>{r.label}</option>)}
        </select>
        <button onClick={gen} disabled={busy} className="px-3 py-1.5 rounded-card border border-accent text-accent hover:bg-accent/10 disabled:opacity-50">{busy ? "…" : "▶ Gerar / replanejar"}</button>
        <button onClick={doCompare} className="px-3 py-1.5 rounded-card border border-edge text-muted hover:border-accent">⚖ Comparar regras</button>
        <button onClick={pub} disabled={!rows.length} className="px-3 py-1.5 rounded-card border border-edge text-muted hover:border-accent disabled:opacity-50">Publicar p/ execução</button>
      </div>

      <div className="flex-1 scroll-thin space-y-4 pr-1">
        {/* KPIs */}
        <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
          {KPI.map((d) => {
            const v = kpis[d.k];
            return (
              <div key={d.k} className="bg-panel border border-edge rounded-card p-2.5">
                <p className="text-[10px] uppercase tracking-wider text-muted truncate">{d.l}</p>
                <p className="text-lg font-extrabold truncate" style={{ color: "var(--accent)" }}>{v == null || v === "" ? "—" : `${v}${d.suf}`}</p>
              </div>
            );
          })}
        </div>

        {/* What-if comparação */}
        {cmp && (
          <div className="rounded-card border border-accent/40 p-3 bg-accent/5">
            <div className="flex items-center gap-2 mb-2"><h3 className="text-xs font-bold flex-1">⚖ What-if — comparação de regras</h3><button onClick={() => setCmp(null)} className="text-muted hover:text-text">✕</button></div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              {cmp.map((c) => (
                <div key={c.rule} className="bg-surface border border-edge rounded-card p-2.5">
                  <p className="text-sm font-semibold">{c.label}</p>
                  <p className="text-[11px] text-muted mt-1">makespan <b>{String(c.kpis.CLD_Makespan_h)}h</b> · util <b>{String(c.kpis.CLD_Capacity_Utilization)}%</b> · setup <b>{String(c.kpis.CLD_Changeover_Time_min)}min</b></p>
                  <button onClick={() => applyRule(c.rule)} className="mt-2 text-[11px] px-2.5 py-1 rounded-card border border-accent text-accent hover:bg-accent/10">aplicar cenário</button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Gantt */}
        {rows.length ? <Gantt rows={rows} colorOf={colorOf} /> : (
          <div className="rounded-card border border-dashed border-edge p-8 text-center text-sm text-muted">Sem cronograma. Clique <b>Gerar</b>.</div>
        )}

        {/* Utilização por recurso + CTP */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          <section className="bg-panel border border-edge rounded-card p-3">
            <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Utilização por recurso (capacidade finita)</h3>
            {load.length === 0 ? <p className="text-xs text-muted">gere o cronograma.</p> : load.map((d) => (
              <div key={d.resource_key} className="flex items-center gap-2 mb-1.5">
                <span className="w-24 shrink-0 text-[10px] truncate" title={d.resource_key}>{d.resource_key.replace("res_", "")}{d.bottleneck && " 🔴"}</span>
                <div className="flex-1 h-3 rounded bg-edge overflow-hidden"><div className="h-full rounded" style={{ width: `${Math.min(100, d.util)}%`, background: d.bottleneck ? "var(--nok)" : "var(--accent)" }} /></div>
                <span className="text-[10px] w-20 text-right text-muted">{d.util}% · {d.ops}op · cap{d.cap}</span>
              </div>
            ))}
          </section>
          <section className="bg-panel border border-edge rounded-card p-3">
            <h3 className="text-xs uppercase tracking-wider text-muted mb-2">CTP / ATP — promessa de prazo</h3>
            <div className="flex items-center gap-2 text-xs flex-wrap">
              <label className="text-muted">Qtd <input value={ctpQty} onChange={(e) => setCtpQty(e.target.value)} className="w-14 bg-edge border border-edge rounded px-2 py-1 ml-1" /></label>
              <label className="text-muted">Prazo <input type="datetime-local" value={ctpDue} onChange={(e) => setCtpDue(e.target.value)} className="bg-edge border border-edge rounded px-2 py-1 ml-1" /></label>
              <button onClick={doCtp} className="px-3 py-1.5 rounded-card border border-accent text-accent hover:bg-accent/10">Calcular</button>
            </div>
            {ctp && (
              <p className="text-xs mt-2">Promessa (CTP): <b>{fmt(ctp.ctp_end)}</b> · lead {ctp.lead_h}h ·{" "}
                {ctp.on_time == null ? <span className="text-muted">sem prazo</span> : ctp.on_time ? <span className="text-ok">✓ no prazo</span> : <span className="text-nok">✗ fora do prazo</span>}</p>
            )}
            <p className="text-[10px] text-muted mt-1.5">Capacidade finita; inicia quando o chão começa a vagar. Promessa = realidade de operação (A04).</p>
          </section>
        </div>

        {/* Recursos editáveis */}
        <section>
          <div className="flex items-center gap-2 mb-2">
            <h3 className="text-xs uppercase tracking-wider text-muted">Recursos (capacidade · skills · status)</h3>
            <input value={newRes} onChange={(e) => setNewRes(e.target.value)} placeholder="novo recurso…" className="ml-auto bg-edge border border-edge rounded px-2 py-1 text-xs w-40" />
            <button onClick={addRes} className="text-xs px-2.5 py-1 rounded-card border border-edge text-muted hover:border-accent">+ add</button>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {resources.map((r) => <ResourceCard key={r.resource_key} r={r} onSaved={reload} />)}
            {resources.length === 0 && <p className="text-xs text-muted col-span-full">"Gerar" cria 3 centros default. Skills (csv) restringem quais fases o recurso executa.</p>}
          </div>
        </section>

        {/* Plano × Real + expedite */}
        {rows.length > 0 && (
          <section>
            <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Plano × Real (realimentação da visão) · ⏫ priorizar (expedite)</h3>
            <div className="bg-panel border border-edge rounded-card overflow-x-auto scroll-thin">
              <table className="w-full text-xs">
                <thead><tr className="text-left text-muted border-b border-edge">
                  {["OP", "Operação", "Recurso", "Plano início", "Plano fim", "Real", "Var (min)", ""].map((h, i) => <th key={i} className="py-1.5 px-2 font-semibold uppercase tracking-wider text-[10px]">{h}</th>)}
                </tr></thead>
                <tbody>
                  {rows.map((r, idx) => {
                    const first = rows.findIndex((x) => x.tag_id === r.tag_id) === idx;
                    return (
                      <tr key={r.schedule_id} className="border-b border-edge/40 last:border-0">
                        <td className="py-1.5 px-2 font-mono"><span className="inline-block w-2 h-2 rounded-full mr-1.5" style={{ background: colorOf(r.tag_id) }} />{r.tag_id.split(":")[3]}</td>
                        <td className="py-1.5 px-2 text-muted">{r.operation}</td>
                        <td className="py-1.5 px-2 text-muted">{r.resource_key.replace("res_", "")}</td>
                        <td className="py-1.5 px-2 text-muted">{fmt(r.planned_start)}</td>
                        <td className="py-1.5 px-2 text-muted">{fmt(r.planned_end)}</td>
                        <td className="py-1.5 px-2 text-muted">{r.actual_start ? "● observado" : "—"}</td>
                        <td className={"py-1.5 px-2 font-semibold " + (r.variance_min == null ? "text-muted" : r.variance_min > 30 ? "text-nok" : "text-ok")}>{r.variance_min ?? "—"}</td>
                        <td className="py-1.5 px-2">{first && <button onClick={() => expedite(r.tag_id)} title="priorizar e replanejar" className="text-[10px] px-1.5 py-0.5 rounded border border-edge text-muted hover:border-accent">⏫</button>}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
