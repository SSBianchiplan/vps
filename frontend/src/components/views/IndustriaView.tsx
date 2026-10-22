import { useState } from "react";
import { DECISAO, STATUS_LABEL, TECHS } from "../../lib/industriaSpec";
import { useStore } from "../../store/useStore";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-muted mb-0.5">{label}</div>
      <div className="text-sm text-text">{children}</div>
    </div>
  );
}

export function IndustriaView() {
  const [sel, setSel] = useState(TECHS[1].id); // YOLO (núcleo do sistema)
  const setView = useStore((s) => s.setView);
  const t = TECHS.find((x) => x.id === sel)!;

  return (
    <div className="h-full overflow-y-auto scroll-thin pr-1">
      <div className="max-w-4xl mx-auto space-y-4 pb-8">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-2xl font-bold">🏭 Visão Computacional Industrial</h1>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent/15 text-accent">spec_tecnologia · v0.1</span>
          </div>
          <p className="text-sm text-muted mt-1">
            Catálogo de modelos por tipo de tecnologia (Manufatura / Industry 4.0 / ISA-95). Cada aba traz
            aplicação, quando usar, requisitos, I/O, latência, integração e KPI — e como o VisionDesk implementa.
          </p>
        </div>

        {/* Pipeline canônico */}
        <div className="vd-surface border border-edge rounded-card p-3 overflow-x-auto">
          <div className="flex items-center gap-2 text-xs font-mono whitespace-nowrap text-text">
            {["CAPTURE", "PREPROCESS", "INFER", "DECIDE", "ACT"].map((s, i, a) => (
              <span key={s} className="flex items-center gap-2">
                <span className="px-2 py-1 rounded bg-edge border border-edge">{s}</span>
                {i < a.length - 1 && <span className="text-muted">→</span>}
              </span>
            ))}
            <span className="text-muted ml-2">&lt; 200 ms / peça</span>
          </div>
        </div>

        {/* Abas das tecnologias */}
        <div className="flex flex-wrap gap-1.5">
          {TECHS.map((x) => (
            <button key={x.id} onClick={() => setSel(x.id)}
              className={"px-2.5 py-1.5 rounded-card text-xs font-medium border transition-colors flex items-center gap-1.5 " +
                (sel === x.id ? "bg-accent text-onaccent border-accent" : "bg-edge border-edge hover:border-accent text-text")}>
              <span>{x.icon}</span><span>{x.num} {x.nome}</span>
            </button>
          ))}
        </div>

        {/* Conteúdo da tecnologia */}
        <section className="vd-surface border border-edge rounded-card p-4 space-y-3">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-2xl">{t.icon}</span>
            <h2 className="font-bold text-lg">{t.num} · {t.nome}</h2>
            {t.camada && <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent-2/15 text-accent-2">{t.camada}</span>}
            <span className={"ml-auto text-[10px] px-2 py-0.5 rounded-full " + STATUS_LABEL[t.vdStatus].cls}>{STATUS_LABEL[t.vdStatus].txt}</span>
          </div>

          <Field label="Aplicação">{t.aplicacao}</Field>
          <div className="grid sm:grid-cols-2 gap-3">
            <Field label="✅ Quando usar"><span className="text-ok/90">{t.quandoUsar}</span></Field>
            <Field label="⛔ Quando NÃO usar"><span className="text-nok/90">{t.quandoNao}</span></Field>
          </div>
          <Field label="Requisitos técnicos">{t.requisitos}</Field>
          <div className="grid sm:grid-cols-2 gap-3">
            <Field label="Entrada → Saída"><span className="font-mono text-xs">{t.io}</span></Field>
            <Field label="Latência típica">{t.latencia}</Field>
          </div>
          <Field label="Integração">{t.integracao}</Field>
          <Field label="KPI primário">
            <div className="flex flex-wrap gap-1.5">
              {t.kpi.map((k) => <span key={k} className="text-[11px] font-mono px-2 py-0.5 rounded bg-edge border border-edge">{k}</span>)}
            </div>
          </Field>

          <div className="border-t border-edge pt-3">
            <Field label="No VisionDesk">
              <div className="flex items-start gap-2">
                <span className={"shrink-0 text-[10px] px-2 py-0.5 rounded-full " + STATUS_LABEL[t.vdStatus].cls}>{STATUS_LABEL[t.vdStatus].txt}</span>
                <span>{t.vd}</span>
              </div>
            </Field>
          </div>
        </section>

        {/* Matriz de decisão */}
        <section className="vd-surface border border-edge rounded-card p-4">
          <h3 className="font-bold text-sm mb-2">🧭 Como escolher (matriz de decisão · §7)</h3>
          <div className="divide-y divide-edge/50">
            {DECISAO.map((d) => (
              <div key={d.q} className="flex items-center gap-3 py-1.5 text-sm">
                <span className="text-muted flex-1">{d.q}</span>
                <span className="text-accent font-medium shrink-0">{d.tech}</span>
              </div>
            ))}
          </div>
          <button className="mt-3 text-xs text-accent hover:underline" onClick={() => setView("estudocaso")}>
            → Ver estudo de caso aplicado às câmeras
          </button>
        </section>
      </div>
    </div>
  );
}
