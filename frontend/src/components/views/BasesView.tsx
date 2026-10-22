import { useEffect, useState } from "react";
import { getDatabases, getTesteInventory, type DbBase, type DbStatus, type TesteInventory } from "../../api/databases";
import { importTeste } from "../../api/vps";
import { useStore } from "../../store/useStore";

const REL_LABEL: Record<string, string> = {
  por_tipo: "Tag-IDs por tipo", por_estado: "Estados", linhagem: "Vínculos (linhagem)",
  reconciliacao: "Reconciliação", eventos_top: "Eventos (top)",
};

// Painel do projeto Teste Sistema (PostgreSQL) — bases vinculadas + relacionamentos.
function TesteSistemaPanel() {
  const setView = useStore((s) => s.setView);
  const [inv, setInv] = useState<TesteInventory | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [applying, setApplying] = useState(false);
  const [msg, setMsg] = useState("");
  useEffect(() => { getTesteInventory().then(setInv).catch(() => undefined); }, []);
  const apply = async () => {
    setApplying(true);
    try { const r = await importTeste(); setMsg(`Aplicado: ${r.tags} tags · ${r.events} eventos · ${r.lineage} vínculos. Abrindo cockpit…`); setTimeout(() => setView("vps"), 900); }
    catch (e) { setMsg("Falha: " + (e as Error).message); }
    finally { setApplying(false); }
  };
  if (!inv) return null;
  if (!inv.available) return <p className="text-xs text-warn">⚠ Teste Sistema: {inv.message}</p>;
  const t = inv.totals!;
  return (
    <section className="bg-panel border border-accent/40 rounded-card p-4 space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        <h2 className="text-base font-bold">🧵 VPS · Projeto <span className="text-accent">Teste Sistema</span></h2>
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-edge text-muted">PostgreSQL · {inv.db}</span>
        <span className="text-[11px] text-muted">{t.ops} OPs · {t.schemas} bases · {t.tables} tabelas · {t.rows} linhas</span>
        <button onClick={apply} disabled={applying} className="ml-auto text-xs px-3 py-1.5 rounded-card border border-accent text-accent hover:bg-accent/10 disabled:opacity-50">
          {applying ? "aplicando…" : "⬇ Aplicar ao cockpit"}
        </button>
      </div>
      {msg && <p className="text-[11px] text-accent">{msg}</p>}

      {/* relacionamentos (bases vinculadas) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
        {Object.entries(inv.relationships ?? {}).map(([k, rows]) => (
          <div key={k} className="bg-surface border border-edge rounded-card p-2.5">
            <p className="text-[10px] uppercase tracking-wider text-muted mb-1">{REL_LABEL[k] ?? k}</p>
            <div className="flex flex-wrap gap-1">
              {rows.map((r) => (
                <span key={r.k} className="text-[10px] px-1.5 py-0.5 rounded bg-edge border border-edge">{r.k} <b className="text-text">{r.n}</b></span>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* schemas (1 base por domínio) → tabelas */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {Object.entries(inv.schemas ?? {}).map(([sch, s]) => (
          <div key={sch} className="bg-surface border border-edge rounded-card overflow-hidden">
            <button onClick={() => setOpen(open === sch ? null : sch)} className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-edge/40">
              <span className="font-mono text-xs font-bold text-accent">{sch}</span>
              <span className="text-[10px] text-muted flex-1 truncate">{s.desc}</span>
              <span className="text-[10px] text-muted">{s.tables.length} tab · {s.tables.reduce((a, x) => a + x.rows, 0)} ln</span>
              <span className="text-muted">{open === sch ? "▾" : "▸"}</span>
            </button>
            {open === sch && (
              <div className="px-3 pb-2 space-y-0.5">
                {s.tables.map((tb) => (
                  <div key={tb.name} className="flex items-center justify-between text-[11px] border-t border-edge/40 py-1">
                    <span className="font-mono text-muted truncate">{tb.name}</span>
                    <span className="text-text font-semibold">{tb.rows}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
      <p className="text-[10px] text-muted">Event Store (verdade física, append-only) → linhagem → projeções/recon/APS → Gold. Bases vinculadas pelo Tag-ID (Fio Dourado). DDL: <code>app/db/vps_postgres.sql</code> · seed: <code>scripts/seed_teste_sistema.py</code>.</p>
    </section>
  );
}

const ICON: Record<string, string> = {
  primary: "🗄", timescale: "⏱", objstore: "🪣", mqtt: "📡", mediamtx: "🎬",
  whatsapp: "🟢", cameras: "📷", anomaly: "❓",
};
const DOT: Record<string, string> = { ok: "bg-ok", warn: "bg-warn", off: "bg-muted" };
const PILL: Record<string, string> = { ok: "bg-ok/20 text-ok", warn: "bg-warn/20 text-warn", off: "bg-edge text-muted" };
const LBL: Record<string, string> = { ok: "operacional", warn: "atenção", off: "desativado" };

function Card({ b }: { b: DbBase }) {
  return (
    <div className="bg-panel border border-edge rounded-card p-4">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-lg">{ICON[b.key] ?? "🗃"}</span>
        <span className="font-semibold text-sm flex-1 truncate" title={b.name}>{b.name}</span>
        <span className={"w-2 h-2 rounded-full " + (DOT[b.status] ?? "bg-muted")} />
      </div>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-edge text-muted">{b.kind}</span>
        <span className={"text-[10px] px-2 py-0.5 rounded-full " + (PILL[b.status] ?? "")}>{LBL[b.status] ?? b.status}</span>
      </div>
      <p className="text-[11px] text-muted font-mono break-all mb-2">{b.detail}</p>
      <div className="flex flex-wrap gap-1.5">
        {Object.entries(b.metrics).map(([k, v]) => (
          <span key={k} className="text-[11px] px-2 py-0.5 rounded bg-edge border border-edge">
            {k}: <b className="text-text">{v === null ? "—" : typeof v === "boolean" ? (v ? "sim" : "não") : v}</b>
          </span>
        ))}
      </div>
    </div>
  );
}

export function BasesView() {
  const [data, setData] = useState<DbStatus | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const load = () => getDatabases().then(setData).catch((e) => setErr(String(e?.message ?? e)));
  useEffect(() => { load(); const id = window.setInterval(load, 10000); return () => window.clearInterval(id); }, []);

  return (
    <div className="h-full overflow-y-auto scroll-thin pr-1">
      <div className="max-w-4xl mx-auto space-y-4 pb-8">
        <div className="flex items-center gap-2 flex-wrap">
          <h1 className="text-2xl font-bold">🗄 Bases de Dados</h1>
          {data && <span className="text-[11px] px-2 py-0.5 rounded-full bg-ok/15 text-ok">{data.resumo.ok}/{data.resumo.total} operacionais</span>}
          <button className="ml-auto text-xs text-accent hover:underline" onClick={load}>↻ Atualizar</button>
        </div>
        <p className="text-sm text-muted">
          Todas as bases conectadas ao VisionDesk + VPS, por categoria: <b>runtime SQLite</b> (Visão CV,
          Fio Dourado, trilha de auditoria), <b>PostgreSQL</b> (auditoria durável + projeto Teste Sistema),
          <b> infraestrutura</b> (séries temporais, object store, broker, media server) e <b>stores de config</b>.
        </p>
        {err && <p className="text-xs text-nok">⚠ {err}</p>}
        <TesteSistemaPanel />
        {!data ? <p className="text-sm text-muted">Carregando…</p> : (() => {
          const visiveis = data.bases.filter((b) => !b.key.startsWith("ts_") && b.key !== "vps_teste");
          const groups = data.groups ?? Array.from(new Set(visiveis.map((b) => b.group || "Outras")));
          return (
            <div className="space-y-4">
              {groups.map((g) => {
                const items = visiveis.filter((b) => (b.group || "Outras") === g);
                if (!items.length) return null;
                const okN = items.filter((b) => b.status === "ok").length;
                return (
                  <div key={g}>
                    <div className="flex items-center gap-2 mb-2">
                      <h3 className="text-xs uppercase tracking-wider text-muted font-semibold">{g}</h3>
                      <span className="text-[10px] text-muted">{okN}/{items.length}</span>
                      <span className="flex-1 h-px bg-edge" />
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {items.map((b) => <Card key={b.key} b={b} />)}
                    </div>
                  </div>
                );
              })}
            </div>
          );
        })()}
      </div>
    </div>
  );
}
