import { useCallback, useEffect, useState } from "react";
import { getBoard, getModal, type BoardCard, type ModalBindings } from "../../api/vps";

// Cor por origem do dado (taxonomia de binding do doc §3).
const ORIGIN: Record<string, { c: string; t: string }> = {
  MD: { c: "#9fb6cc", t: "Master data" }, TAG: { c: "#e6c34a", t: "Tag-ID" }, LIN: { c: "#dca93a", t: "Linhagem" },
  EVT: { c: "#cdbfa6", t: "Event store" }, PROJ: { c: "#7cc4a0", t: "Projeção/estado" }, VIS: { c: "#c89bd6", t: "Visão" },
  TPL: { c: "#8fb0e0", t: "Template" }, REC: { c: "#6fcf97", t: "Reconciliação" }, CALC: { c: "#b0a89a", t: "Derivado" },
  IN: { c: "#e08a8a", t: "Entrada → evento" },
};
const OCODES = Object.keys(ORIGIN);

// Catálogo dos 11 modais (doc §4–6).
const CATALOG = [
  { id: "M1", t: "Operador (estação)", q: "operador logado", ev: "—", o: ["MD", "EVT", "PROJ", "VIS"] },
  { id: "M2", t: "Leitura / Resolução", q: "token lido pela câmera", ev: "OP_OPENED, avanço, OCCURRENCE_RAISED", o: ["TAG", "LIN", "PROJ", "VIS", "TPL"] },
  { id: "M3", t: "Conferência (CONTAR)", q: "fase de contagem", ev: "PICK_ITEM_CONFIRMED, PICK_COMPLETED, PICK_SHORT", o: ["MD", "EVT", "PROJ", "VIS", "TPL"] },
  { id: "M4", t: "Pendência", q: "PENDING_OPENED", ev: "SUPPLY_LINK, PENDING_CLEARED", o: ["MD", "TAG", "LIN", "EVT"] },
  { id: "M5", t: "Ocorrência", q: "OCCURRENCE_RAISED", ev: "OCCURRENCE_TRIAGED, OCCURRENCE_RESOLVED", o: ["MD", "TAG", "EVT", "VIS", "TPL"] },
  { id: "M6", t: "Fio Dourado", q: "buscar/escanear Tag-ID", ev: "— (consulta)", o: ["TAG", "LIN", "EVT", "PROJ", "VIS"] },
  { id: "M7", t: "Medição", q: "fase de medição", ev: "MEASUREMENT_APPROVED, MEASUREMENT_REJECTED", o: ["TAG", "LIN", "VIS", "TPL"] },
  { id: "M8", t: "Reconciliação", q: "recon pendente/divergente", ev: "MATCHED (ou M10)", o: ["TAG", "EVT", "REC"] },
  { id: "M9", t: "Cadastro (master data)", q: "admin cria/edita", ev: "versão SCD2", o: ["MD"] },
  { id: "M10", t: "Correção (compensatório)", q: "corrigir dado registrado", ev: "QTY_CORRECTION (referencia o original)", o: ["MD", "TAG", "EVT", "IN"] },
  { id: "M11", t: "Vínculo (suprimento/kit)", q: "ligar demanda↔oferta", ev: "SUPPLY_LINK, agrupamento", o: ["TAG", "LIN", "IN"] },
];

function OB({ o }: { o: string }) {
  const d = ORIGIN[o] ?? { c: "var(--edge)", t: o };
  return <span className="text-[8px] font-bold px-1 py-0.5 rounded" style={{ background: d.c, color: "#1c1407" }} title={d.t}>{o}</span>;
}

export function ModaisView() {
  const [tab, setTab] = useState<"vivo" | "catalogo">("vivo");
  const [tags, setTags] = useState<BoardCard[]>([]);
  const [sel, setSel] = useState("");
  const [m, setM] = useState<ModalBindings | null>(null);

  useEffect(() => { getBoard().then((b) => { setTags(b.cards); if (b.cards[0]) setSel(b.cards[0].tag_id); }).catch(() => undefined); }, []);
  const load = useCallback(() => { if (sel) getModal(sel).then(setM).catch(() => undefined); }, [sel]);
  useEffect(() => { load(); }, [load]);

  return (
    <div className="flex flex-col gap-3 min-h-full">
      <div className="flex items-center gap-3 flex-wrap border-b border-edge pb-2">
        <h2 className="text-base font-bold flex items-center gap-2">📋 Modais & Vínculos
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent/15 text-accent">dado vinculado a dado</span>
        </h2>
        <div className="ml-auto flex gap-1">
          {([["vivo", "Vínculos ao vivo"], ["catalogo", "Catálogo (11 modais)"]] as const).map(([k, l]) => (
            <button key={k} onClick={() => setTab(k)} className={"px-3 py-1.5 text-sm rounded-card border-b-2 " + (tab === k ? "border-accent text-accent" : "border-transparent text-muted hover:text-text")}>{l}</button>
          ))}
        </div>
      </div>

      {/* legenda de origem */}
      <div className="flex flex-wrap gap-1.5 items-center text-[10px] text-muted">
        <span className="uppercase tracking-wider">Origem:</span>
        {OCODES.map((o) => <span key={o} className="flex items-center gap-1"><OB o={o} /> {ORIGIN[o].t}</span>)}
      </div>

      <div className="flex-1 scroll-thin pr-1">
        {tab === "vivo" ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-xs">
              <span className="text-muted uppercase tracking-wider">Fio (instância)</span>
              <select value={sel} onChange={(e) => setSel(e.target.value)} className="bg-edge border border-edge rounded px-2 py-1 text-xs">
                {tags.map((t) => <option key={t.tag_id} value={t.tag_id}>{t.natural_key} · {t.entity_type} · {t.phase}</option>)}
                {tags.length === 0 && <option value="">— sem instâncias —</option>}
              </select>
              <span className="text-[10px] text-muted">cada campo = projeção de um vínculo · read-only (vínculo) vs <span className="text-warn">●</span> entrada → evento</span>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              {m?.modais.map((g) => (
                <section key={g.id} className="bg-panel border border-edge rounded-card p-3">
                  <h3 className="text-xs font-bold mb-2">{g.title}</h3>
                  <div className="space-y-1">
                    {g.fields.map((f, i) => (
                      <div key={i} className={"flex items-center gap-2 text-xs rounded px-2 py-1 " + (f.editable ? "bg-warn/10 border border-warn/40" : "")}>
                        <span className="text-muted w-32 shrink-0">{f.label}{f.editable && " ●"}</span>
                        <span className="flex-1 font-mono text-text break-all">{f.value ?? "—"}</span>
                        <OB o={f.origin} />
                      </div>
                    ))}
                  </div>
                </section>
              ))}
              {!m && <p className="text-xs text-muted">Selecione um Fio.</p>}
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
              {CATALOG.map((mo) => (
                <div key={mo.id} className="bg-panel border border-edge rounded-card p-3">
                  <p className="text-sm font-bold">{mo.id} · {mo.t}</p>
                  <p className="text-[10px] text-muted mt-0.5">quando: {mo.q}</p>
                  <p className="text-[10px] text-muted">eventos: <span className="font-mono">{mo.ev}</span></p>
                  <div className="flex flex-wrap gap-1 mt-1.5">{mo.o.map((o) => <OB key={o} o={o} />)}</div>
                </div>
              ))}
            </div>
            <section className="bg-panel border border-edge rounded-card p-3 overflow-x-auto scroll-thin">
              <h3 className="text-xs font-bold mb-2">Matriz modal × origem</h3>
              <table className="text-[11px] border-collapse">
                <thead><tr className="text-muted"><th className="py-1 pr-3 text-left">Modal</th>{OCODES.map((o) => <th key={o} className="px-1.5"><OB o={o} /></th>)}</tr></thead>
                <tbody>
                  {CATALOG.map((mo) => (
                    <tr key={mo.id} className="border-t border-edge/40">
                      <td className="py-1 pr-3 font-medium whitespace-nowrap">{mo.id} {mo.t}</td>
                      {OCODES.map((o) => <td key={o} className="px-1.5 text-center">{mo.o.includes(o) ? <span className="text-ok">✓</span> : <span className="text-muted/30">·</span>}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
            <p className="text-[10px] text-muted">B01 todo campo tem origem · B02 ler≠escrever (entrada vira evento) · B03 linhagem na tela · B04 evidência junto do dado · B05 correção = evento compensatório.</p>
          </div>
        )}
      </div>
    </div>
  );
}
