import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  getBoard, getLabelPrefill, getSegments, tagGenerate,
  type BoardCard, type GeneratedLabel, type LabelData, type SegmentInfo,
} from "../../api/vps";

// Dono do contexto por tipo (espelha rbac.ENTITY_OWNER) — auto-preenche owner.
const ENTITY_OWNER: Record<string, string> = {
  OP: "Operations", PICK: "Supply", ITEM: "Supply", STOCK: "Supply", SO: "Sales",
  PROJ: "Projects", SHIP: "Operations", INV: "Finance", MEAS: "Quality", OCC: "Quality",
};

// CSS da etiqueta (porta fiel de VPS_Gerador_Etiquetas.html — em mm, p/ impressão térmica).
const LABEL_CSS = `
.vlbl{background:#fff;color:#14110e;position:relative;overflow:hidden;font-family:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.vlbl.size-62x100{width:62mm;height:100mm}
.vlbl.size-62x90{width:62mm;height:90mm}
.vlbl.size-29x90{width:90mm;height:29mm}
.vlbl .bind{position:absolute;top:0;bottom:0;left:2.2mm;width:.38mm;background:linear-gradient(180deg,#9c7a1e,#e6c34a,#b8902a,#9c7a1e)}
.vlbl .stitch{position:absolute;left:1.65mm;width:1.45mm;height:1.45mm;border-radius:50%;background:radial-gradient(circle at 35% 30%,#e6c34a,#b8902a);border:.25mm solid #fff;box-shadow:0 0 0 .18mm #9c7a1e}
.vlbl .lpad{position:absolute;inset:0;padding:2.2mm 2.8mm 1.8mm 4.4mm;display:flex;flex-direction:column}
.vlbl .lhead{display:flex;align-items:center;justify-content:space-between;gap:1.3mm}
.vlbl .lhead .mk{display:flex;align-items:center;gap:1.0mm;min-width:0;flex:1 1 auto;overflow:hidden}
.vlbl .lhead .redbar{width:1.0mm;height:3.2mm;background:#c8102e;border-radius:.3mm;flex:0 0 auto}
.vlbl .lhead .brand{font-weight:800;letter-spacing:.03em;text-transform:uppercase;font-size:2.05mm;white-space:nowrap;overflow:hidden;text-overflow:clip;min-width:0;flex:1 1 auto}
.vlbl .lhead .brand i{color:#b8902a;font-style:normal}
.vlbl .badges{display:flex;gap:.9mm;flex:0 0 auto}
.vlbl .badge{background:#c8102e;color:#fff;font-weight:800;letter-spacing:.04em;text-transform:uppercase;font-size:1.7mm;padding:.6mm 1.1mm;border-radius:.6mm;white-space:nowrap}
.vlbl .badge.state{background:#14110e;color:#fff}
.vlbl .hthread{height:.7mm;margin:1.4mm 0;border-radius:1mm;background:linear-gradient(90deg,#9c7a1e,#e6c34a 45%,#b8902a 75%,#9c7a1e)}
.vlbl .ltype{font-weight:800;letter-spacing:.01em;text-transform:uppercase;font-size:3.4mm;line-height:1.02;margin:.2mm 0 .3mm}
.vlbl .ltype small{display:block;font-size:1.85mm;letter-spacing:.16em;color:#5a5249;font-weight:700;margin-bottom:.3mm}
.vlbl .crumb{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:1.9mm;color:#5a5249;margin:.3mm 0 1.0mm;word-break:break-word;line-height:1.26}
.vlbl .crumb b{color:#c8102e}
.vlbl .hero{font-family:ui-monospace,Menlo,Consolas,monospace;font-weight:800;font-size:4.8mm;line-height:1.0;letter-spacing:-.01em;color:#14110e;margin:.5mm 0 1.2mm;white-space:nowrap;overflow:hidden;text-overflow:clip}
.vlbl .qrow{display:flex;gap:2.2mm;align-items:center}
.vlbl .qbox{flex:0 0 auto;background:#fff;padding:.6mm;border:.3mm solid #e7e1d8;box-shadow:0 0 0 .25mm #f2eee7}
.vlbl .qbox svg{display:block;width:28mm;height:28mm}
.vlbl .qbox .qmiss{width:28mm;height:28mm;display:flex;align-items:center;justify-content:center;text-align:center;font-size:1.9mm;color:#b08;line-height:1.3;padding:2mm}
.vlbl .qmeta{min-width:0;flex:1;display:flex;flex-direction:column;justify-content:center;gap:.45mm}
.vlbl .qmeta .sub{font-size:2.05mm;color:#5a5249;letter-spacing:.02em;font-family:ui-monospace,Menlo,Consolas,monospace}
.vlbl .qmeta .sub b{color:#14110e;font-weight:700}
.vlbl .tagid{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:2.15mm;margin:1.4mm 0 0;word-break:break-all;line-height:1.26;color:#14110e}
.vlbl .tagid b{color:#c8102e}
.vlbl .divider{height:.25mm;background:#e2dcd1;margin:1.2mm 0}
.vlbl .grid{display:grid;grid-template-columns:auto 1fr;column-gap:2.0mm;row-gap:.5mm;font-size:2.0mm;line-height:1.18}
.vlbl .grid .k{color:#14110e;font-weight:700;text-transform:uppercase;letter-spacing:.02em;font-size:1.8mm;white-space:nowrap}
.vlbl .grid .v{font-family:ui-monospace,Menlo,Consolas,monospace;color:#5a5249;word-break:break-word}
.vlbl .grid .v b{color:#14110e;font-weight:700}
.vlbl .spacer{flex:1 1 auto;min-height:.4mm}
.vlbl .lfoot{font-size:1.6mm;color:#5a5249;letter-spacing:.01em;line-height:1.18;margin-top:1.0mm;text-align:center}
.vlbl .lfoot b{color:#b8902a}
.vlbl.station .hero{font-size:4.4mm}
.vlbl.station .qbox svg,.vlbl.station .qbox .qmiss{width:23mm;height:23mm}
.vlbl.size-29x90 .lpad{padding:1.8mm 3mm 1.6mm 5mm}
.vlbl.size-29x90 .ltype{font-size:3.2mm;margin:.2mm 0 .4mm}
.vlbl.size-29x90 .hero{font-size:4.0mm;margin:.4mm 0 .8mm}
.vlbl.size-29x90 .qbox svg,.vlbl.size-29x90 .qbox .qmiss{width:17mm;height:17mm}
.vlbl.size-29x90 .hthread{margin:.7mm 0}
.vlbl.size-29x90 .tagid{font-size:2.0mm;margin-top:.8mm}
.vlbl.size-29x90 .grid,.vlbl.size-29x90 .crumb{display:none}
`;

const SIZES: Record<string, string> = { "62x100": "62 × 100 mm (DK-11202)", "62x90": "62 mm contínuo", "29x90": "29 × 90 mm (estação)" };
const ENTITY_TYPES = ["OP", "PICK", "ITEM", "LOT", "SO", "PROJ", "PO", "SHIP", "INV", "MEAS", "GROUP", "STATION"];
const ESTADOS = ["BOUND", "IN_PROCESS", "RESOLVED", "CAPTURED", "EXCEPTION", "COMPLETED"];

// Fluxo da simulação ponta a ponta (PANEL_ETO) — VPS_Gerador_de_Tags.md §9.
const FLOW: Partial<LabelData>[] = [
  { type: "ENTITY", entity_type: "SO", natural_key: "PV-2026-7781", parent: "", estado: "COMPLETED", owner: "Sales", phase: "VENDAS" },
  { type: "ENTITY", entity_type: "PROJ", natural_key: "PRJ-2026-118", parent: "SO:PV-2026-7781", estado: "COMPLETED", owner: "Projects", phase: "PROJETO" },
  { type: "ENTITY", entity_type: "OP", natural_key: "OP-2026-04412", parent: "PROJ:PRJ-2026-118", estado: "IN_PROCESS", owner: "Operations", qtd: "12", lote: "L-2026-0088", phase: "PRODUÇÃO" },
  { type: "ENTITY", entity_type: "PICK", natural_key: "PK-04412-01", parent: "OP:OP-2026-04412", estado: "COMPLETED", owner: "Supply", qtd: "12", lote: "L-2026-0088", sla: "8h", phase: "PICKING" },
  { type: "STATION", entity_type: "STATION", natural_key: "ALMOX-02", parent: "", estado: "", owner: "Supply", station: "ALMOX-02", phase: "PICKING" },
  { type: "ENTITY", entity_type: "MEAS", natural_key: "MD-04412", parent: "OP:OP-2026-04412", estado: "COMPLETED", owner: "Quality", phase: "MEDIÇÃO" },
  { type: "ENTITY", entity_type: "SHIP", natural_key: "SH-04412", parent: "OP:OP-2026-04412", estado: "COMPLETED", owner: "Logistics", phase: "EXPEDIÇÃO" },
  { type: "ENTITY", entity_type: "INV", natural_key: "NF-2026-3321", parent: "SHIP:SH-04412", estado: "COMPLETED", owner: "Finance", phase: "FATURAMENTO" },
];

const up = (v?: string | null) => (v || "").toString().trim().toUpperCase();
const esc = (s?: string | null) => (s == null ? "" : String(s)).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c] as string));
const fmtDate = () => { const d = new Date(); return [d.getDate(), d.getMonth() + 1].map((n) => String(n).padStart(2, "0")).join("/") + "/" + d.getFullYear(); };
const colorId = (id: string) => id.split(":").map((p, i) => (i === 0 ? "<b>" + p + "</b>" : p)).join("<b>:</b>");
const row = (k: string, v: string, html = false) => '<div class="k">' + esc(k) + '</div><div class="v">' + (html ? v : esc(v)) + "</div>";
function crumb(d: GeneratedLabel) {
  if (!d.parent || d.parent.indexOf(":") < 0) return "";
  const pp = d.parent.split(":"); const pt = up(pp[0]); const pk = pp.slice(1).join(":");
  return "<b>" + esc(pt) + "</b> " + esc(pk) + " ▸ <b>" + esc(up(d.entity_type)) + "</b> " + esc(d.natural_key);
}

// HTML interno da etiqueta (porta de labelInner).
function labelInner(d: GeneratedLabel): string {
  const isStation = d.type === "STATION";
  const qrHtml = d.qr_svg ? d.qr_svg : '<div class="qmiss">QR indisponível</div>';
  const bigOver = isStation ? "POSTO / AÇÃO" : "SEGMENTO · TIPO";
  const bigTitle = isStation ? (up(d.phase) || "AÇÃO") : up(d.segment) + " · " + up(d.entity_type);
  const cr = isStation ? "" : crumb(d);
  const sub = isStation
    ? '<div class="sub">posto <b>' + esc(up(d.segment)) + "</b></div>"
    : '<div class="sub">instância <b>' + esc(d.instance || "01") + "</b></div>"
      + (d.qtd ? '<div class="sub">qtd <b>' + esc(d.qtd) + "</b></div>" : "")
      + (d.lote ? '<div class="sub">lote <b>' + esc(d.lote) + "</b></div>" : "");
  const grid = isStation
    ? row("Posto", up(d.segment)) + row("Ação", up(d.phase)) + row("Estação", up(d.station)) + row("Emissão", fmtDate()) + row("Lote impr.", d.print_batch)
    : row("Cliente", d.cliente || "—")
      + row("Fase", up(d.phase) + " · " + esc(up(d.template_id)), true)
      + row("Estado", up(d.estado) + (d.sla ? " · SLA " + esc(d.sla) : ""), true)
      + row("Owner", d.owner || "—")
      + row("Emissão", fmtDate() + " · " + esc(up(d.station)))
      + row("Emissor", esc(d.emissor) + " · lote " + esc(d.print_batch));
  const stBadge = isStation || !d.estado ? "" : '<div class="badge state">' + esc(up(d.estado)) + "</div>";
  return ""
    + '<div class="bind"></div><div class="stitch" style="top:5mm"></div><div class="stitch" style="top:46%"></div><div class="stitch" style="bottom:5mm"></div>'
    + '<div class="lpad">'
    + '<div class="lhead"><div class="mk"><div class="redbar"></div><div class="brand">GPlan <i>·</i> VPS</div></div>'
    + '<div class="badges"><div class="badge">' + (isStation ? "ESTAÇÃO" : "ENTIDADE") + "</div>" + stBadge + "</div></div>"
    + '<div class="hthread"></div>'
    + '<div class="ltype"><small>' + bigOver + "</small>" + esc(bigTitle) + "</div>"
    + (cr ? '<div class="crumb">⤷ ' + cr + "</div>" : "")
    + '<div class="hero">' + esc(d.natural_key || "—") + "</div>"
    + '<div class="qrow"><div class="qbox">' + qrHtml + '</div><div class="qmeta">' + sub + "</div></div>"
    + '<div class="tagid">' + colorId(esc(d.tag_id)) + "</div>"
    + '<div class="divider"></div><div class="grid">' + grid + "</div>"
    + '<div class="spacer"></div><div class="hthread"></div>'
    + '<div class="lfoot"><b>Fio Dourado</b> · rastreável de ponta a ponta · by GPlan</div>'
    + "</div>";
}
const labelOuter = (d: GeneratedLabel) =>
  '<div class="vlbl size-' + d.size + (d.type === "STATION" ? " station" : "") + '">' + labelInner(d) + "</div>";

function printLabels(htmls: string[]) {
  const w = window.open("", "_blank");
  if (!w) return;
  w.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>Etiquetas VPS</title><style>${LABEL_CSS}
    body{margin:0;background:#fff}.vlbl{box-shadow:none;break-after:page;page-break-after:always}@page{margin:0}</style></head><body>${htmls.join("")}</body></html>`);
  w.document.close();
  setTimeout(() => w.print(), 350);
}

const DEFAULTS: LabelData = {
  type: "ENTITY", segment: "PANEL", entity_type: "OP", natural_key: "OP-2026-04412", instance: "01",
  parent: "SO:PV-2026-7781", cliente: "COOP-DEMO", lote: "L-2026-0088", qtd: "12", estado: "BOUND",
  phase: "PICKING", sla: "8h", template_id: "PANEL_ETO_V1", owner: "Operations",
  station: "ALMOX-02", emissor: "u123", encode: "TAGID", size: "62x100",
};

export function LabelGenerator({ initial, onClose }: { initial?: Partial<LabelData>; onClose: () => void }) {
  const batch = useMemo(() => "IMP-" + Math.random().toString(36).slice(-5).toUpperCase(), []);
  const [d, setD] = useState<LabelData>({ ...DEFAULTS, ...initial, print_batch: batch });
  const [mode, setMode] = useState<"single" | "sim">("single");
  const [gen, setGen] = useState<GeneratedLabel | null>(null);
  const [sim, setSim] = useState<GeneratedLabel[]>([]);
  const [tags, setTags] = useState<BoardCard[]>([]);
  const [segs, setSegs] = useState<SegmentInfo[]>([]);
  const [link, setLink] = useState("");
  const timer = useRef<number | undefined>(undefined);

  // fontes do sistema p/ vincular (Fios existentes + segmentos)
  useEffect(() => {
    getBoard().then((b) => setTags(b.cards)).catch(() => undefined);
    getSegments().then((s) => setSegs(s.segments)).catch(() => undefined);
  }, []);

  const set = (k: keyof LabelData, v: string) => setD((s) => {
    const next = { ...s, [k]: v };
    if (k === "type" && v === "STATION") next.entity_type = "STATION";
    if (k === "entity_type" && ENTITY_OWNER[v]) next.owner = ENTITY_OWNER[v];   // owner segue o tipo
    return next;
  });

  // Vincular a um Fio existente → backend deriva e preenche os campos.
  const linkTo = async (tagId: string) => {
    setLink(tagId);
    if (!tagId) return;
    const pf = await getLabelPrefill(tagId).catch(() => null);
    if (pf) setD((s) => ({ ...s, ...pf } as LabelData));
  };

  // single: regenera (QR no backend) com debounce
  useEffect(() => {
    if (mode !== "single") return;
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => { tagGenerate(d).then(setGen).catch(() => undefined); }, 250);
    return () => window.clearTimeout(timer.current);
  }, [d, mode]);

  const buildSim = useCallback(async () => {
    const out = await Promise.all(FLOW.map((f) => tagGenerate({
      ...DEFAULTS, segment: "PANEL", instance: "01", cliente: "COOP-DEMO", template_id: "PANEL_ETO_V1",
      station: "ALMOX-02", emissor: "u123", sla: "8h", encode: "TAGID", size: "62x100", print_batch: batch, ...f,
    } as LabelData).catch(() => null)));
    setSim(out.filter(Boolean) as GeneratedLabel[]);
  }, [batch]);
  useEffect(() => { if (mode === "sim") buildSim(); }, [mode, buildSim]);

  const doPrint = () => {
    if (mode === "sim") printLabels(sim.map(labelOuter));
    else if (gen) printLabels([labelOuter(gen)]);
  };
  const copyTag = () => { if (gen) navigator.clipboard?.writeText(gen.tag_id); };

  const scale = d.size === "29x90" ? 2.2 : 1.9;

  return createPortal(
    <div className="fixed inset-0 z-[120] flex" style={{ background: "rgba(0,0,0,0.55)" }} onClick={onClose}>
      <style>{LABEL_CSS}</style>
      <div className="m-auto w-full max-w-5xl h-[90vh] bg-surface border border-edge rounded-card flex overflow-hidden" onClick={(e) => e.stopPropagation()}>
        {/* Controles */}
        <aside className="w-[320px] shrink-0 border-r border-edge overflow-y-auto scroll-thin p-4 space-y-3">
          <div className="flex items-center gap-2">
            <h3 className="text-base font-bold flex-1">🏷 Gerador de Tags</h3>
            <button onClick={onClose} className="text-muted hover:text-text text-lg">✕</button>
          </div>
          <div className="flex rounded-card border border-edge overflow-hidden text-xs">
            {(["single", "sim"] as const).map((m) => (
              <button key={m} onClick={() => setMode(m)} className={"flex-1 px-2 py-1.5 " + (mode === m ? "bg-accent text-onaccent" : "bg-edge text-muted")}>
                {m === "single" ? "Etiqueta única" : "Simulação ponta a ponta"}
              </button>
            ))}
          </div>

          {mode === "single" && (
            <div className="space-y-2.5">
              {/* Vincular a um Fio existente → auto-preenche os campos do sistema */}
              <label className="block text-[10px] uppercase tracking-wider text-accent">⛓ Vincular a um Fio (auto-fill)
                <select value={link} onChange={(e) => linkTo(e.target.value)} className="w-full mt-1 bg-edge border border-accent/40 rounded px-2 py-1.5 text-sm text-text">
                  <option value="">— novo / manual —</option>
                  {tags.map((t) => <option key={t.tag_id} value={t.tag_id}>{t.natural_key} · {t.entity_type} · {t.phase}</option>)}
                </select>
              </label>
              <p className="text-[10px] text-muted">Campos <span className="text-warn">●</span> em destaque = manuais (sem fonte no sistema). Demais vêm do Fio vinculado.</p>

              <div className="flex rounded-card border border-edge overflow-hidden text-xs">
                {(["ENTITY", "STATION"] as const).map((tp) => (
                  <button key={tp} onClick={() => set("type", tp)} className={"flex-1 px-2 py-1.5 " + (d.type === tp ? "bg-accent text-onaccent" : "bg-edge text-muted")}>
                    {tp === "ENTITY" ? "Entidade" : "Estação/Ação"}
                  </button>
                ))}
              </div>
              <SelectField label="Segmento" v={d.segment} opts={Array.from(new Set([d.segment, ...segs.map((s) => s.segment)]))} onChange={(v) => set("segment", v)} />
              <SelectField label="Tipo" v={d.entity_type} opts={ENTITY_TYPES} onChange={(v) => set("entity_type", v)} />
              <Field label="Chave natural" v={d.natural_key} onChange={(v) => set("natural_key", v)} mono />
              <Field label="Instância" v={d.instance} onChange={(v) => set("instance", v)} mono />
              <Field label="Origem / pai (tipo:chave)" v={d.parent ?? ""} onChange={(v) => set("parent", v)} mono />
              <Field label="Cliente" v={d.cliente ?? ""} onChange={(v) => set("cliente", v)} manual />
              <Field label="Lote / Série" v={d.lote ?? ""} onChange={(v) => set("lote", v)} mono manual />
              <Field label="Qtd" v={d.qtd ?? ""} onChange={(v) => set("qtd", v)} mono manual />
              <SelectField label="Estado" v={d.estado ?? ""} opts={ESTADOS} onChange={(v) => set("estado", v)} />
              <Field label="Fase" v={d.phase ?? ""} onChange={(v) => set("phase", v)} />
              <Field label="SLA" v={d.sla ?? ""} onChange={(v) => set("sla", v)} />
              <Field label="Template" v={d.template_id ?? ""} onChange={(v) => set("template_id", v)} mono />
              <Field label="Owner" v={d.owner ?? ""} onChange={(v) => set("owner", v)} />
              <Field label="Estação emissora" v={d.station ?? ""} onChange={(v) => set("station", v)} mono manual />
              <Field label="Emissor" v={d.emissor ?? ""} onChange={(v) => set("emissor", v)} mono manual />
              <SelectField label="QR codifica" v={d.encode} opts={["TAGID", "DEEPLINK"]} onChange={(v) => set("encode", v)} />
            </div>
          )}
          <SelectField label="Tamanho" v={d.size} opts={Object.keys(SIZES)} optLabels={SIZES} onChange={(v) => set("size", v)} />

          <button onClick={doPrint} className="w-full text-sm px-3 py-2 rounded-card border border-accent text-accent hover:bg-accent/10">🖨 Imprimir / PDF</button>
          {mode === "single" && <button onClick={copyTag} className="w-full text-xs px-3 py-1.5 rounded-card border border-edge text-muted hover:border-accent">Copiar Tag-ID</button>}
          <p className="text-[10px] text-muted">QR correção Q (industrial) ≥ 20 mm · Brother QL-800 300 dpi. A geração NÃO abre a instância — a câmera (modo LER) abre ao ler o token.</p>
        </aside>

        {/* Palco / preview */}
        <main className="flex-1 overflow-auto scroll-thin bg-black/20 p-6">
          {mode === "single" ? (
            <div className="flex justify-center">
              {gen ? (
                <div style={{ transform: `scale(${scale})`, transformOrigin: "top center" }}
                  dangerouslySetInnerHTML={{ __html: labelOuter(gen) }} />
              ) : <p className="text-muted text-sm">Gerando…</p>}
            </div>
          ) : (
            <div>
              <p className="text-sm font-bold mb-1">Simulação ponta a ponta — o Fio Dourado</p>
              <p className="text-[11px] text-muted font-mono mb-4">PV-2026-7781 · do pedido ao faturamento ({sim.length} etiquetas)</p>
              <div className="grid gap-6" style={{ gridTemplateColumns: "repeat(auto-fill,minmax(240px,1fr))" }}>
                {sim.map((g, i) => (
                  <div key={i} className="flex flex-col items-center gap-2">
                    <span className="self-start text-[10px] uppercase tracking-wider text-muted flex items-center gap-2">
                      <span className="w-5 h-5 grid place-items-center rounded-full bg-accent text-onaccent font-bold">{i + 1}</span>
                      <span className="text-accent font-semibold">{FLOW[i].phase}</span> · {g.entity_type}
                    </span>
                    <div dangerouslySetInnerHTML={{ __html: labelOuter(g) }} />
                  </div>
                ))}
              </div>
            </div>
          )}
        </main>
      </div>
    </div>, document.body);
}

function Field({ label, v, onChange, mono, manual }: { label: string; v: string; onChange: (v: string) => void; mono?: boolean; manual?: boolean }) {
  return (
    <label className={"block text-[10px] uppercase tracking-wider " + (manual ? "text-warn" : "text-muted")}>
      {label}{manual && " ●"}
      <input value={v} onChange={(e) => onChange(e.target.value)}
        className={"w-full mt-1 rounded px-2 py-1.5 text-sm text-text border " + (mono ? "font-mono " : "")
          + (manual ? "bg-warn/10 border-warn/50 focus:border-warn" : "bg-edge border-edge")} />
    </label>
  );
}
function SelectField({ label, v, opts, optLabels, onChange }: { label: string; v: string; opts: string[]; optLabels?: Record<string, string>; onChange: (v: string) => void }) {
  return (
    <label className="block text-[10px] uppercase tracking-wider text-muted">{label}
      <select value={v} onChange={(e) => onChange(e.target.value)} className="w-full mt-1 bg-edge border border-edge rounded px-2 py-1.5 text-sm text-text">
        {opts.map((o) => <option key={o} value={o}>{optLabels?.[o] ?? o}</option>)}
      </select>
    </label>
  );
}
