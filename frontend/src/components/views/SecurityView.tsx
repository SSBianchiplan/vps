import { useCallback, useEffect, useState } from "react";
import { secIntegrity, secOverview, type Integrity, type Overview, type Status } from "../../api/security";
import { btnPrimaryCls } from "../../lib/ui";

const ST: Record<Status, string> = {
  aplicado: "bg-ok/20 text-ok", parcial: "bg-warn/20 text-warn", planejado: "bg-edge text-muted", "em curso": "bg-accent/20 text-accent",
};
const chip = (s: Status) => <span className={"text-[10px] px-1.5 py-0.5 rounded-full whitespace-nowrap " + (ST[s] || "bg-edge text-muted")}>{s}</span>;

function Ring({ v }: { v: number }) {
  const c = 2 * Math.PI * 26, col = v >= 80 ? "#3ddca0" : v >= 60 ? "#2ec2b3" : v >= 40 ? "#f0a020" : "#f0556a";
  return (
    <svg viewBox="0 0 64 64" className="w-16 h-16">
      <circle cx="32" cy="32" r="26" fill="none" stroke="var(--edge,#474d52)" strokeWidth="6" opacity={0.3} />
      <circle cx="32" cy="32" r="26" fill="none" stroke={col} strokeWidth="6" strokeLinecap="round"
        strokeDasharray={`${(v / 100) * c} ${c}`} transform="rotate(-90 32 32)" />
      <text x="32" y="36" textAnchor="middle" fontSize="15" fontWeight="800" fill="currentColor">{v}</text>
    </svg>
  );
}

export function SecurityView() {
  const [d, setD] = useState<Overview | null>(null);
  const [integ, setInteg] = useState<Integrity | null>(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => { secOverview().then(setD).catch(() => undefined); }, []);
  useEffect(() => { load(); }, [load]);
  const verify = async () => { setBusy(true); try { setInteg(await secIntegrity()); } finally { setBusy(false); } };

  if (!d) return <div className="p-6 text-sm text-muted">Carregando postura de segurança…</div>;
  const p = d.posture;

  return (
    <div className="flex flex-col gap-4 min-h-full">
      <div className="flex items-center gap-3 flex-wrap border-b border-edge pb-2">
        <h2 className="text-lg font-bold flex items-center gap-2">🛡 Cibersegurança</h2>
        <span className="text-xs text-muted">safety-first OT · imutável · IA soberana · privacidade por design</span>
        <div className="ml-auto flex flex-wrap gap-1">{d.frameworks.map((f) => (
          <span key={f.code} title={`${f.dom} · ${f.uso}`} className="text-[10px] px-1.5 py-0.5 rounded-full border border-edge text-muted">{f.code}</span>
        ))}</div>
      </div>

      {/* Postura NIST CSF */}
      <section className="bg-panel border border-edge rounded-card p-4">
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-3"><Ring v={p.overall} /><div><div className="text-xs uppercase tracking-wider text-muted">Postura geral</div><div className="text-sm">NIST CSF · {p.audit_events.toLocaleString()} eventos na trilha</div></div></div>
          <div className="flex-1 grid grid-cols-2 sm:grid-cols-5 gap-2 min-w-[280px]">
            {p.functions.map((f) => (
              <div key={f.key} className="rounded-card border border-edge bg-edge/30 p-2 text-center">
                <div className="text-lg leading-none">{f.icon}</div>
                <div className="text-[10px] uppercase tracking-wider text-muted mt-1">{f.nist}</div>
                <div className="text-lg font-bold" style={{ color: f.score >= 80 ? "var(--ok,#3ddca0)" : f.score >= 50 ? "var(--accent)" : "var(--warn,#f0a020)" }}>{f.score}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-x-6 gap-y-1 mt-4">
          {p.functions.flatMap((f) => f.checks.map((c, i) => (
            <div key={f.key + i} className="flex items-center gap-2 text-[12px] border-b border-edge/40 py-1">
              <span className="text-[9px] text-muted w-[78px] shrink-0 uppercase">{f.nist}</span>
              <span className="flex-1 text-text">{c.l}<span className="text-muted"> · {c.ev}</span></span>
              {chip(c.s)}
            </div>
          )))}
        </div>
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-4">
        <div className="space-y-4">
          {/* Modelo de ameaças */}
          <section className="bg-panel border border-edge rounded-card p-4">
            <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Modelo de ameaças (superfície × mitigação)</h3>
            <div className="overflow-x-auto scroll-thin">
              <table className="w-full text-xs">
                <thead><tr className="text-left text-muted border-b border-edge">{["Superfície", "Ameaça", "Mitigação", ""].map((h) => <th key={h} className="py-1.5 pr-3 font-semibold uppercase text-[10px]">{h}</th>)}</tr></thead>
                <tbody>{d.threats.map((t) => (
                  <tr key={t.surface} className="border-b border-edge/40 align-top">
                    <td className="py-1.5 pr-3 font-medium text-text whitespace-nowrap">{t.surface}</td>
                    <td className="py-1.5 pr-3 text-muted">{t.threat}</td>
                    <td className="py-1.5 pr-3 text-muted">{t.mitig}</td>
                    <td className="py-1.5">{chip(t.status)}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          </section>

          {/* Eventos de segurança (trilha) */}
          <section className="bg-panel border border-edge rounded-card p-4">
            <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Eventos de segurança (trilha · nok/alerta/warn)</h3>
            <div className="space-y-0.5 max-h-64 overflow-y-auto scroll-thin">
              {d.events.length === 0 ? <p className="text-xs text-muted">Sem eventos críticos recentes.</p> : d.events.map((e, i) => (
                <div key={i} className="text-[11px] flex items-center gap-2 border-b border-edge/40 py-0.5">
                  <span className="text-muted whitespace-nowrap">{new Date(e.event_ts).toLocaleString()}</span>
                  <span className="font-mono text-text">{e.category}</span>
                  <span className={"font-semibold " + (e.severity === "nok" || e.severity === "alerta" ? "text-nok" : "text-warn")}>{e.action}</span>
                  <span className="text-muted truncate">{e.summary}</span>
                </div>
              ))}
            </div>
          </section>
        </div>

        <aside className="space-y-4">
          {/* Integridade — cadeia de hash */}
          <section className="bg-panel border border-edge rounded-card p-4">
            <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Integridade da trilha (cadeia de hash)</h3>
            <p className="text-[11px] text-muted">Recomputa um fingerprint encadeado (sha256) sobre a trilha imutável — alterar/remover/reordenar um evento muda o resultado (tamper-evident).</p>
            <button className={btnPrimaryCls + " w-full mt-2"} onClick={verify} disabled={busy}>{busy ? "Verificando…" : "🔒 Verificar agora"}</button>
            {integ && (
              <div className={"mt-2 rounded-card border p-2 text-xs " + (integ.ok ? "border-ok/40 bg-ok/5" : "border-nok/40 bg-nok/5")}>
                <div className={"font-semibold " + (integ.ok ? "text-ok" : "text-nok")}>{integ.ok ? "✓ Cadeia íntegra" : `⚠ ${integ.anomalies.length} anomalia(s)`}</div>
                <div className="text-muted mt-0.5">{integ.count.toLocaleString()} eventos · {integ.algo}</div>
                <div className="font-mono text-[10px] text-text break-all mt-1">head: {integ.head_hash}</div>
                {integ.anomalies.slice(0, 5).map((a, i) => <div key={i} className="text-nok text-[10px] mt-0.5">⚠ {a.event_id}: {a.issue}</div>)}
              </div>
            )}
          </section>

          {/* Frameworks */}
          <section className="bg-panel border border-edge rounded-card p-4">
            <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Frameworks de referência</h3>
            <div className="space-y-1.5">{d.frameworks.map((f) => (
              <div key={f.code} className="text-xs"><b className="text-accent">{f.code}</b> <span className="text-muted">· {f.dom}</span><div className="text-[11px] text-muted">{f.uso}</div></div>
            ))}</div>
          </section>

          {/* Roadmap */}
          <section className="bg-panel border border-edge rounded-card p-4">
            <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Roadmap de segurança</h3>
            <div className="space-y-1.5">{d.roadmap.map((r) => (
              <div key={r.fase} className="flex items-start gap-2 text-[11px]">
                <span className="font-mono text-accent shrink-0">{r.fase}</span>
                <span className="flex-1 text-muted">{r.entrega}</span>
                {chip(r.status)}
              </div>
            ))}</div>
          </section>
        </aside>
      </div>
      <p className="text-[10px] text-muted">Postura viva (NIST CSF) checada contra o sistema · spec VPS_Ciberseguranca_Produto. OT somente-leitura, trilha imutável verificável, IA soberana, privacidade por design (LGPD).</p>
    </div>
  );
}
