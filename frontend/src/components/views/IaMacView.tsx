import { useCallback, useEffect, useRef, useState } from "react";
import {
  iaAsk, iaEval, iaFeedback, iaInsights, iaReindex, iaSetModel, iaStatus,
  type AskResult, type IaStatus, type Insight,
} from "../../api/iamac";
import { btnCls, btnPrimaryCls, inputCls, selectCls } from "../../lib/ui";

interface Turn { q: string; a: AskResult; vote?: number }

export function IaMacView() {
  const [q, setQ] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<IaStatus | null>(null);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [msg, setMsg] = useState("");
  const endRef = useRef<HTMLDivElement | null>(null);

  const refresh = useCallback(() => { iaStatus().then(setStatus).catch(() => undefined); }, []);
  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [turns]);

  const ask = async () => {
    const question = q.trim(); if (!question || busy) return;
    setBusy(true); setQ("");
    try { const a = await iaAsk(question); setTurns((t) => [...t, { q: question, a }]); refresh(); }
    catch (e) { setMsg(String((e as Error)?.message ?? e)); }
    finally { setBusy(false); }
  };
  const vote = async (i: number, v: number) => {
    const t = turns[i]; if (!t) return;
    await iaFeedback(t.a.id, v);
    setTurns((arr) => arr.map((x, j) => (j === i ? { ...x, vote: v } : x))); refresh();
  };
  const pickModel = async (id: string) => { const r = await iaSetModel(id); setMsg(r.ok ? `modelo: ${id}` : (r.message || "falhou")); refresh(); };
  const runEval = async () => { const r = await iaEval(); setMsg(`eval: ${r.score}% acerto · ${r.grounding}% grounding (${r.passed}/${r.total})`); refresh(); };
  const reindex = async () => { const r = await iaReindex(); setMsg(`reindexado: ${r.chunks} chunks`); refresh(); };
  const ganhos = async () => { setInsights(await iaInsights()); };

  const SUG = ["O que é o Fio Dourado (Tag-ID)?", "Como a IA fica mais inteligente (flywheel)?", "Como funciona a termografia preditiva?", "Estado atual do sistema?"];

  return (
    <div className="flex flex-col gap-3 min-h-full lg:h-full lg:min-h-0">
      <div className="flex items-center gap-2 flex-wrap shrink-0">
        <h2 className="text-lg font-bold">🧠 iaMAC — IA &amp; Motor de Aprendizado</h2>
        <span className="text-xs text-muted">copiloto do VPS · RAG com citações (grounding) · flywheel + eval · Mac/MLX</span>
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-[1fr_340px] gap-4 min-h-0">
        {/* Copiloto */}
        <section className="bg-panel rounded-card border border-edge p-4 overflow-hidden flex flex-col min-h-[50vh] lg:min-h-0">
          <div className="flex-1 overflow-y-auto scroll-thin space-y-3 pr-1">
            {turns.length === 0 ? (
              <div className="h-full min-h-[200px] flex flex-col items-center justify-center gap-2 text-center">
                <span className="text-3xl">🧠</span>
                <p className="text-sm text-muted max-w-md">Pergunte sobre o sistema, specs, vínculos ou ganhos. Toda resposta é <b>lastreada em fonte</b> (specs + estado ao vivo). Só leio/recomendo — não altero o passado.</p>
                <div className="flex flex-wrap gap-1.5 justify-center mt-1">
                  {SUG.map((s) => <button key={s} className="text-[11px] px-2 py-1 rounded-full border border-edge text-muted hover:text-text" onClick={() => setQ(s)}>{s}</button>)}
                </div>
              </div>
            ) : turns.map((t, i) => (
              <div key={i} className="space-y-1.5">
                <div className="flex justify-end"><span className="bg-accent/15 text-text rounded-card px-3 py-1.5 text-sm max-w-[80%]">{t.q}</span></div>
                <div className="bg-edge/40 rounded-card px-3 py-2 text-sm">
                  <p className="text-text whitespace-pre-wrap">{t.a.answer}</p>
                  {t.a.citations.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {t.a.citations.map((c, k) => (
                        <span key={k} className="text-[10px] px-1.5 py-0.5 rounded border border-accent/40 text-accent" title={c.title}>📎 {c.source} › {c.title}</span>
                      ))}
                    </div>
                  )}
                  <div className="flex items-center gap-2 mt-1.5 text-[11px] text-muted">
                    <span className={t.a.grounded ? "text-ok" : "text-warn"}>{t.a.grounded ? "✓ lastreado" : "⚠ sem fonte"}</span>
                    <span>· {t.a.engine}</span>
                    <button className={"ml-auto " + (t.vote === 1 ? "text-ok" : "hover:text-ok")} onClick={() => vote(i, 1)}>👍</button>
                    <button className={(t.vote === -1 ? "text-nok" : "hover:text-nok")} onClick={() => vote(i, -1)}>👎</button>
                  </div>
                </div>
              </div>
            ))}
            <div ref={endRef} />
          </div>
          <div className="flex gap-2 mt-3 shrink-0">
            <input className={inputCls} placeholder="Pergunte ao copiloto…" value={q}
              onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && ask()} />
            <button className={btnPrimaryCls} onClick={ask} disabled={busy}>{busy ? "…" : "Perguntar"}</button>
          </div>
          {msg && <p className="text-[11px] text-muted mt-1">{msg}</p>}
        </section>

        {/* Status / flywheel / Mac */}
        <aside className="bg-panel rounded-card border border-edge p-4 overflow-y-auto scroll-thin space-y-4">
          {status && (
            <>
              <section className="border-b border-edge pb-3">
                <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Modelo (fundação)</h3>
                <select className={selectCls} value={status.current_model} onChange={(e) => pickModel(e.target.value)}>
                  {status.models.map((m) => (
                    <option key={m.id} value={m.id} disabled={!m.available}>
                      {m.label}{m.available ? "" : " — indisponível"}{m.loaded ? " ●" : ""}
                    </option>
                  ))}
                </select>
                {(() => { const cur = status.models.find((m) => m.id === status.current_model); return cur ? <p className="text-[10px] text-muted mt-1">{cur.note}</p> : null; })()}
                <div className="flex flex-wrap gap-1 mt-2">
                  <span className={"text-[10px] px-1.5 py-0.5 rounded-full border " + (status.apple_silicon ? "border-ok/40 text-ok" : "border-edge text-muted")}>{status.apple_silicon ? "🍎 Apple Silicon" : "não-Apple"}</span>
                  <span className={"text-[10px] px-1.5 py-0.5 rounded-full border " + (status.mlx_available ? "border-ok/40 text-ok" : "border-edge text-muted")}>MLX {status.mlx_available ? "✓" : "✗"}</span>
                  <span className={"text-[10px] px-1.5 py-0.5 rounded-full border " + (status.lmstudio_available ? "border-ok/40 text-ok" : "border-edge text-muted")}>LM Studio {status.lmstudio_available ? "✓" : "off"}</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded-full border border-edge text-muted">{status.knowledge_chunks} chunks</span>
                </div>
                <p className="text-[10px] text-muted mt-1">Soberano: {status.foundation}. Dados não saem da sua infra.</p>
                <p className="text-[10px] text-muted">📁 modelos: {status.models_dir}</p>
              </section>

              <section className="border-b border-edge pb-3">
                <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Flywheel (verificar ganho)</h3>
                <div className="grid grid-cols-2 gap-1.5 text-sm">
                  <div className="rounded border border-edge bg-edge/40 px-2 py-1"><div className="text-[10px] text-muted uppercase">Interações</div><div className="font-bold">{status.flywheel.interactions}</div></div>
                  <div className="rounded border border-edge bg-edge/40 px-2 py-1"><div className="text-[10px] text-muted uppercase">👍 / 👎</div><div className="font-bold">{status.flywheel.feedback_pos} / {status.flywheel.feedback_neg}</div></div>
                  <div className="rounded border border-edge bg-edge/40 px-2 py-1"><div className="text-[10px] text-muted uppercase">Eval score</div><div className="font-bold">{status.last_eval ? `${status.last_eval.score}%` : "—"}</div></div>
                  <div className="rounded border border-edge bg-edge/40 px-2 py-1"><div className="text-[10px] text-muted uppercase">Grounding</div><div className="font-bold">{status.last_eval ? `${status.last_eval.grounding}%` : "—"}</div></div>
                </div>
                <div className="flex gap-2 mt-2">
                  <button className={btnCls} onClick={runEval}>▶ Rodar eval</button>
                  <button className={btnCls} onClick={reindex}>↻ Reindexar</button>
                </div>
              </section>

              <section className="border-b border-edge pb-3">
                <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Análise de ganhos (agente)</h3>
                <button className={btnCls + " w-full"} onClick={ganhos}>🔎 Verificar ganhos/gargalos</button>
                {insights.length > 0 && (
                  <ul className="mt-2 space-y-1">
                    {insights.map((i, k) => (
                      <li key={k} className="text-xs text-text border-b border-edge/40 py-1">
                        <span className="text-[9px] uppercase text-accent">{i.kind}</span> {i.text} <span className="text-muted">— {i.evidence}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              <section>
                <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Lab no Mac (Apple §10)</h3>
                <ul className="space-y-1">
                  {status.frameworks.map((f) => (
                    <li key={f.name} className="text-[11px] flex items-start gap-1.5">
                      <span className={f.ready ? "text-ok" : "text-muted"}>{f.ready ? "●" : "○"}</span>
                      <span><b className="text-text">{f.name}</b> <span className="text-muted">— {f.role}</span></span>
                    </li>
                  ))}
                </ul>
                <p className="text-[10px] text-muted mt-2">Guardrails: {status.guardrails.join(" · ")}.</p>
              </section>
            </>
          )}
        </aside>
      </div>
    </div>
  );
}
