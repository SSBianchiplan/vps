import { useCallback, useEffect, useMemo, useState } from "react";
import {
  addCard, addDep, baselineProject, createProject, getApsResources, getCriticalPath,
  getOperators, getPlanVsActual, getProject, getProjects, releaseCard, scheduleProject, seedPlanning,
  type CpmCard, type Operator, type ProjectDetail, type PvaRow, type Resource,
} from "../../api/vps";

const fmt = (s: string | null) => (s ? new Date(s).toLocaleString([], { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "—");
const ms = (s: string | null) => (s ? new Date(s).getTime() : 0);
const STATE_BADGE: Record<string, string> = {
  PLANNED: "bg-edge text-muted", SCHEDULED: "bg-accent/15 text-accent", RELEASED: "bg-accent/15 text-accent",
  IN_EXECUTION: "bg-accent/15 text-accent", BLOCKED: "bg-nok/15 text-nok", DONE: "bg-ok/15 text-ok",
};
const KPI = [
  { k: "CLD_Project_Pct_Complete", l: "Avanço físico", s: "%" },
  { k: "CLD_Project_SPI", l: "SPI", s: "" },
  { k: "CLD_Cards_Done", l: "Cards done", s: "" },
  { k: "CLD_Cards_OnTime", l: "No prazo", s: "" },
  { k: "CLD_Baseline_Adherence", l: "Aderência baseline", s: "%" },
];

// Gantt simples dos cards (barra = janela planejada; vermelho = caminho crítico).
function Gantt({ cards, crit }: { cards: PvaRow[]; crit: Record<string, CpmCard> }) {
  const withDates = cards.filter((c) => c.planned_start && c.planned_end);
  if (!withDates.length) return <p className="text-xs text-muted">Sem datas — clique <b>Agendar</b>.</p>;
  const t0 = Math.min(...withDates.map((c) => ms(c.planned_start)));
  const t1 = Math.max(...withDates.map((c) => ms(c.planned_end)));
  const span = Math.max(1, t1 - t0);
  return (
    <div className="rounded-card border border-edge p-3" style={{ background: "var(--chart-bg)" }}>
      <div className="flex justify-between text-[10px] text-muted mb-2"><span>{fmt(new Date(t0).toISOString())}</span><span>{fmt(new Date(t1).toISOString())}</span></div>
      <div className="space-y-1.5">
        {withDates.map((c) => {
          const left = ((ms(c.planned_start) - t0) / span) * 100;
          const w = Math.max(1.5, ((ms(c.planned_end) - ms(c.planned_start)) / span) * 100);
          const isCrit = crit[c.card_id]?.critical;
          return (
            <div key={c.card_id} className="flex items-center gap-2">
              <span className="w-28 shrink-0 text-[10px] truncate" style={{ color: "var(--chart-axis)" }} title={c.title}>{c.code} {c.title}</span>
              <div className="relative flex-1 h-5 rounded" style={{ background: "var(--chart-grid)" }}>
                <div className="absolute top-0.5 h-4 rounded-sm" style={{ left: `${left}%`, width: `${w}%`, background: isCrit ? "var(--nok)" : "var(--accent)" }} title={`${fmt(c.planned_start)} → ${fmt(c.planned_end)}`}>
                  <div className="h-full rounded-sm bg-white/30" style={{ width: `${c.pct}%` }} />
                </div>
              </div>
            </div>
          );
        })}
      </div>
      <p className="text-[10px] text-muted mt-2">Barra = janela planejada · preenchimento = avanço físico observado · vermelho = caminho crítico (slack 0).</p>
    </div>
  );
}

export function PlanejamentoView() {
  const [projects, setProjects] = useState<{ project_id: string; code: string; name: string; state: string; cards?: number }[]>([]);
  const [pid, setPid] = useState<string>("");
  const [proj, setProj] = useState<ProjectDetail | null>(null);
  const [pva, setPva] = useState<{ cards: PvaRow[]; kpis: Record<string, number | null> } | null>(null);
  const [crit, setCrit] = useState<Record<string, CpmCard>>({});
  const [ops, setOps] = useState<Operator[]>([]);
  const [res, setRes] = useState<Resource[]>([]);
  const [busy, setBusy] = useState(false);
  const [nc, setNc] = useState({ code: "", title: "", effort: "8", resource: "", operator: "" });
  const [dep, setDep] = useState({ pred: "", succ: "" });

  const loadProjects = useCallback(() => getProjects().then((d) => { setProjects(d.projects); if (!pid && d.projects[0]) setPid(d.projects[0].project_id); }).catch(() => undefined), [pid]);
  useEffect(() => { loadProjects(); }, [loadProjects]);
  useEffect(() => { getOperators("ativo").then((d) => setOps(d.operators)).catch(() => undefined); getApsResources().then((d) => setRes(d.resources)).catch(() => undefined); }, []);

  const load = useCallback(() => {
    if (!pid) return;
    getProject(pid).then(setProj).catch(() => undefined);
    getPlanVsActual(pid).then(setPva).catch(() => undefined);
    getCriticalPath(pid).then((d) => setCrit(Object.fromEntries(d.cards.map((c) => [c.card_id, c])))).catch(() => undefined);
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  const newProject = async () => {
    const code = window.prompt("Código do projeto (ex.: PRJ-2026-118):"); if (!code) return;
    const p = await createProject({ code, name: window.prompt("Nome:") || code, segment: "PANEL" });
    await loadProjects(); setPid(p.project_id);
  };
  const act = async (fn: () => Promise<unknown>) => { setBusy(true); try { await fn(); load(); await loadProjects(); } finally { setBusy(false); } };
  const doAddCard = () => { if (nc.code.trim()) act(() => addCard(pid, { code: nc.code.trim(), title: nc.title || nc.code, planned_effort: Number(nc.effort) || 8, resource_key: nc.resource || undefined, assigned_operator: nc.operator || undefined })).then(() => setNc({ code: "", title: "", effort: "8", resource: "", operator: "" })); };
  const doAddDep = () => { if (dep.pred && dep.succ && dep.pred !== dep.succ) act(() => addDep(pid, dep.pred, dep.succ)).then(() => setDep({ pred: "", succ: "" })); };

  const cards = pva?.cards ?? [];
  const codeOf = useMemo(() => Object.fromEntries((proj?.cards ?? []).map((c) => [c.card_id, c.code])), [proj]);

  return (
    <div className="flex flex-col gap-3 min-h-full">
      <div className="flex items-center gap-3 flex-wrap border-b border-edge pb-2">
        <h2 className="text-base font-bold flex items-center gap-2">🗂 Planejamento
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent/15 text-accent">o projeto rege · card → Tag-ID</span>
        </h2>
        <select value={pid} onChange={(e) => setPid(e.target.value)} className="bg-edge border border-edge rounded px-2 py-1 text-xs ml-1">
          {projects.length === 0 && <option value="">— sem projetos —</option>}
          {projects.map((p) => <option key={p.project_id} value={p.project_id}>{p.code} · {p.name} ({p.cards ?? 0})</option>)}
        </select>
        <button onClick={newProject} className="text-xs px-3 py-1.5 rounded-card border border-accent text-accent hover:bg-accent/10">+ Novo projeto</button>
        <button onClick={() => act(seedPlanning)} className="text-xs px-3 py-1.5 rounded-card border border-edge text-muted hover:border-accent">demo</button>
      </div>

      {!proj ? <p className="text-sm text-muted">Crie um projeto (o projeto habilita planejar os cards) ou use <b>demo</b>.</p> : (
        <div className="flex-1 space-y-4 pr-1">
          {/* toolbar */}
          <div className="flex items-center gap-2 flex-wrap text-xs">
            <span className={"px-2 py-0.5 rounded-full " + (STATE_BADGE[proj.state] ?? "bg-edge text-muted")}>{proj.state}</span>
            <span className="text-muted">baseline v{proj.baseline_version} · {proj.segment} · {proj.resource_pool ?? "—"}</span>
            <button onClick={() => act(() => scheduleProject(pid))} disabled={busy} className="ml-auto px-3 py-1.5 rounded-card border border-accent text-accent hover:bg-accent/10 disabled:opacity-50">▶ Agendar (CPM+finito)</button>
            <button onClick={() => act(() => baselineProject(pid))} disabled={busy} className="px-3 py-1.5 rounded-card border border-edge text-muted hover:border-accent disabled:opacity-50">📌 Baseline</button>
            <button onClick={load} className="px-3 py-1.5 rounded-card border border-edge text-muted hover:border-accent">↻</button>
          </div>

          {/* KPIs */}
          <div className="grid grid-cols-3 sm:grid-cols-5 gap-2">
            {KPI.map((d) => { const v = pva?.kpis[d.k]; return (
              <div key={d.k} className="bg-panel border border-edge rounded-card p-2.5">
                <p className="text-[10px] uppercase tracking-wider text-muted truncate">{d.l}</p>
                <p className="text-lg font-extrabold" style={{ color: "var(--accent)" }}>{v == null ? "—" : `${v}${d.s}`}</p>
              </div>); })}
          </div>

          <Gantt cards={cards} crit={crit} />

          {/* cards: plano × real + ações */}
          <section>
            <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Cards · plano × real (avanço observado)</h3>
            <div className="bg-panel border border-edge rounded-card overflow-x-auto scroll-thin">
              <table className="w-full text-xs">
                <thead><tr className="text-left text-muted border-b border-edge">
                  {["Card", "Tipo", "Estado", "Recurso", "Operador", "Plano fim", "Baseline", "Real fim", "%", "Slack", ""].map((h, i) => <th key={i} className="py-1.5 px-2 font-semibold uppercase tracking-wider text-[10px]">{h}</th>)}
                </tr></thead>
                <tbody>
                  {cards.map((c) => { const cp = crit[c.card_id]; return (
                    <tr key={c.card_id} className="border-b border-edge/40 last:border-0">
                      <td className="py-1.5 px-2 font-medium text-text">{c.code} · {c.title}{c.tag_id && <span className="ml-1 text-[9px] text-accent">🧵</span>}</td>
                      <td className="py-1.5 px-2 text-muted">{proj.cards.find((x) => x.card_id === c.card_id)?.card_type ?? "—"}</td>
                      <td className="py-1.5 px-2"><span className={"px-1.5 py-0.5 rounded " + (STATE_BADGE[c.state] ?? "")}>{c.state}</span></td>
                      <td className="py-1.5 px-2 text-muted">{c.resource_key?.replace("res_", "") ?? "—"}</td>
                      <td className="py-1.5 px-2 text-muted">{c.operator ?? "—"}</td>
                      <td className="py-1.5 px-2 text-muted">{fmt(c.planned_end)}</td>
                      <td className="py-1.5 px-2 text-muted">{fmt(c.baseline_end)}</td>
                      <td className="py-1.5 px-2 text-muted">{c.actual_end ? fmt(c.actual_end) : c.actual_start ? "em curso" : "—"}</td>
                      <td className="py-1.5 px-2"><div className="w-12 h-1.5 rounded bg-edge overflow-hidden"><div className="h-full rounded bg-accent" style={{ width: `${c.pct}%` }} /></div></td>
                      <td className={"py-1.5 px-2 " + (cp?.critical ? "text-nok font-semibold" : "text-muted")}>{cp ? `${cp.slack}h` : "—"}</td>
                      <td className="py-1.5 px-2 whitespace-nowrap">
                        {!c.tag_id && <button onClick={() => act(() => releaseCard(c.card_id))} title="liberar → gera Tag-ID (gênese)" className="text-[10px] px-1.5 py-0.5 rounded border border-accent/50 text-accent hover:bg-accent/10">▶ liberar</button>}
                      </td>
                    </tr>); })}
                  {cards.length === 0 && <tr><td colSpan={11} className="py-4 px-2 text-center text-muted">Sem cards. Adicione abaixo.</td></tr>}
                </tbody>
              </table>
            </div>
          </section>

          {/* add card */}
          <section className="bg-panel border border-edge rounded-card p-3">
            <h3 className="text-xs uppercase tracking-wider text-muted mb-2">+ Novo card</h3>
            <div className="grid grid-cols-2 sm:grid-cols-6 gap-2 text-xs">
              <input value={nc.code} onChange={(e) => setNc({ ...nc, code: e.target.value })} placeholder="código" className="bg-edge border border-edge rounded px-2 py-1.5" />
              <input value={nc.title} onChange={(e) => setNc({ ...nc, title: e.target.value })} placeholder="título" className="bg-edge border border-edge rounded px-2 py-1.5 col-span-2" />
              <input value={nc.effort} onChange={(e) => setNc({ ...nc, effort: e.target.value })} placeholder="esforço(h)" className="bg-edge border border-edge rounded px-2 py-1.5" />
              <select value={nc.resource} onChange={(e) => setNc({ ...nc, resource: e.target.value })} className="bg-edge border border-edge rounded px-2 py-1.5"><option value="">recurso…</option>{res.map((r) => <option key={r.resource_key} value={r.resource_key}>{r.name}</option>)}</select>
              <select value={nc.operator} onChange={(e) => setNc({ ...nc, operator: e.target.value })} className="bg-edge border border-edge rounded px-2 py-1.5"><option value="">operador…</option>{ops.map((o) => <option key={o.operator_id} value={o.operator_id}>{o.name}</option>)}</select>
            </div>
            <button onClick={doAddCard} disabled={!nc.code.trim()} className="mt-2 text-xs px-3 py-1.5 rounded-card border border-accent text-accent hover:bg-accent/10 disabled:opacity-50">Adicionar card</button>
          </section>

          {/* dependencies */}
          <section className="bg-panel border border-edge rounded-card p-3">
            <div className="flex items-center gap-2 mb-2 flex-wrap">
              <h3 className="text-xs uppercase tracking-wider text-muted">Dependências (rede de precedência)</h3>
              <select value={dep.pred} onChange={(e) => setDep({ ...dep, pred: e.target.value })} className="bg-edge border border-edge rounded px-2 py-1 text-xs ml-auto"><option value="">predecessor…</option>{proj.cards.map((c) => <option key={c.card_id} value={c.card_id}>{c.code}</option>)}</select>
              <span className="text-muted">→</span>
              <select value={dep.succ} onChange={(e) => setDep({ ...dep, succ: e.target.value })} className="bg-edge border border-edge rounded px-2 py-1 text-xs"><option value="">sucessor…</option>{proj.cards.map((c) => <option key={c.card_id} value={c.card_id}>{c.code}</option>)}</select>
              <button onClick={doAddDep} className="text-xs px-2.5 py-1 rounded-card border border-edge text-muted hover:border-accent">+ FS</button>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {proj.deps.map((d) => <span key={d.dep_id} className="text-[10px] px-2 py-0.5 rounded bg-edge border border-edge font-mono">{codeOf[d.pred_card_id]} →{d.dep_type} {codeOf[d.succ_card_id]}</span>)}
              {proj.deps.length === 0 && <span className="text-[10px] text-muted">nenhuma dependência</span>}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
