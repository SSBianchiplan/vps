import { useCallback, useEffect, useRef, useState } from "react";
import { useStore, type View } from "../../store/useStore";
import {
  otAck, otAckAll, otAlarms, otEvents, otSaveSynoptic, otSimulate, otSynoptic, otVisionInspect,
  type Link, type LinkKind, type OtAlarm, type OtEvent, type Widget, type WType,
} from "../../api/automation";
import { btnCls, btnPrimaryCls, inputCls, labelCls, selectCls } from "../../lib/ui";
import { getConfig, missingFields, type SupLinkField } from "../../api/appconfig";
import { QrLabelModal } from "./QrLabelModal";

// fallback do schema (espelha backend sup_link_fields) — usado se o config não carregar
const DEFAULT_LINK_FIELDS: SupLinkField[] = [
  { name: "tag", label: "Tag da linha (P&ID)", type: "text", required: ["process", "signal", "electric", "vision"], placeholder: "LN-1001 / SIG-204" },
  { name: "direction", label: "Sentido do fluxo", type: "select", options: ["uni", "bi"], required: ["process", "signal", "electric", "vision"], default: "uni" },
  { name: "priority", label: "Criticidade", type: "select", options: ["baixa", "normal", "alta", "critica"], required: ["process", "signal", "electric", "vision"], default: "normal" },
  { name: "medium", label: "Meio / fluido", type: "select", options: ["água", "vapor", "ar comprimido", "óleo", "gás", "produto", "efluente", "inspeção/visão"], required: ["process", "vision"] },
  { name: "signal_type", label: "Tipo de sinal", type: "select", options: ["4-20mA", "0-10V", "Digital", "PROFINET", "PROFIBUS", "Modbus", "OPC UA", "HART", "IO-Link"], required: ["signal", "electric"] },
  { name: "diameter", label: "Bitola / seção", type: "text", required: [], placeholder: "DN50 / 2.5mm²" },
  { name: "engineering_unit", label: "Unidade de engenharia", type: "text", required: [] },
  { name: "interlock", label: "Participa de intertravamento", type: "bool", required: [] },
  { name: "description", label: "Descrição", type: "text", required: [] },
];

const RUN = new Set(["RUN", "EXECUTE", "AUTO", "ON", "PASS"]);
const ASSETS = ["M-301", "RIO-L1", "TK-12", "INJ-07", "PR-22"];
const ACTIONS = ["MACHINE_STATE", "COUNTER_READ", "PROCESS_VALUE_READ", "CYCLE_COMPLETED", "IO_STATE", "VISION_INSPECTION"];
const PALETTE: { t: WType; ic: string; l: string }[] = [
  { t: "tag", ic: "🔢", l: "Tag" }, { t: "gauge", ic: "📊", l: "Gauge" }, { t: "tank", ic: "🛢", l: "Tanque" },
  { t: "valve", ic: "🔻", l: "Válvula" }, { t: "pump", ic: "⛽", l: "Bomba" }, { t: "fan", ic: "🌀", l: "Fan" },
  { t: "motor", ic: "⚙", l: "Motor" }, { t: "machine", ic: "🏭", l: "Máquina" }, { t: "vision", ic: "👁", l: "Visão" },
  { t: "lamp", ic: "💡", l: "Lâmpada" }, { t: "switch", ic: "🎛", l: "Chave" }, { t: "button", ic: "🔘", l: "Botão" }, { t: "label", ic: "🏷", l: "Texto" },
];
const SIZE: Record<WType, [number, number]> = {
  tag: [130, 56], gauge: [70, 150], tank: [110, 160], valve: [70, 60], pump: [90, 80], fan: [90, 80],
  motor: [110, 80], machine: [150, 90], vision: [120, 92], lamp: [120, 60], switch: [120, 64], button: [140, 44], label: [200, 26],
  pipe: [140, 16], arrow: [56, 40], process: [150, 70], decision: [104, 104], terminator: [150, 56],
};
const VALUE_T = new Set<WType>(["tag", "gauge", "tank", "valve", "pump", "fan", "motor", "machine", "lamp", "switch", "vision"]);
const COLOR_T = new Set<WType>(["tag", "label", "pipe", "arrow", "process", "decision", "terminator"]);
const LINK_STYLE: Record<LinkKind, { stroke: string; width: number; dash?: string; lbl: string }> = {
  process: { stroke: "#6b7280", width: 5, lbl: "Processo" },
  signal: { stroke: "#3da9fc", width: 2, dash: "6 4", lbl: "Sinal" },
  electric: { stroke: "#f0a020", width: 2, dash: "9 3 2 3", lbl: "Elétrico" },
  vision: { stroke: "#19C3B2", width: 2.5, dash: "2 5", lbl: "Visão" },
};

// roteamento ortogonal P&ID (ângulo reto) entre dois widgets
function anchors(s: Widget, t: Widget): [number, number][] {
  const scx = s.x + s.w / 2, scy = s.y + s.h / 2, tcx = t.x + t.w / 2, tcy = t.y + t.h / 2;
  const dx = tcx - scx, dy = tcy - scy;
  if (Math.abs(dx) >= Math.abs(dy)) {
    const sx = dx >= 0 ? s.x + s.w : s.x, tx = dx >= 0 ? t.x : t.x + t.w, mx = (sx + tx) / 2;
    return [[sx, scy], [mx, scy], [mx, tcy], [tx, tcy]];
  }
  const sy = dy >= 0 ? s.y + s.h : s.y, ty = dy >= 0 ? t.y : t.y + t.h, my = (sy + ty) / 2;
  return [[scx, sy], [scx, my], [tcx, my], [tcx, ty]];
}
const pathOf = (p: [number, number][]) => `M ${p[0][0]},${p[0][1]} ` + p.slice(1).map((q) => `L ${q[0]},${q[1]}`).join(" ");

export function SupervisorioEditor() {
  const setView = useStore((s) => s.setView);
  const [widgets, setWidgets] = useState<Widget[]>([]);
  const [links, setLinks] = useState<Link[]>([]);
  const [mode, setMode] = useState<"edit" | "run">("run");
  const [sel, setSel] = useState<string | null>(null);
  const [selLink, setSelLink] = useState<string | null>(null);
  const [linkMode, setLinkMode] = useState(false);
  const [linkKind, setLinkKind] = useState<LinkKind>("process");
  const [linkFrom, setLinkFrom] = useState<string | null>(null);
  const [ev, setEv] = useState<OtEvent[]>([]);
  const [alarms, setAlarms] = useState<OtAlarm[]>([]);
  const [modal, setModal] = useState<Widget | null>(null);
  const [qr, setQr] = useState<{ asset: string | null } | null>(null);
  const [linkFields, setLinkFields] = useState<SupLinkField[]>(DEFAULT_LINK_FIELDS);
  const [dirty, setDirty] = useState(false);
  const [grid, setGrid] = useState(true);
  const [msg, setMsg] = useState("");
  const drag = useRef<{ id: string; ox: number; oy: number } | null>(null);
  const canvasRef = useRef<HTMLDivElement | null>(null);

  const loadData = useCallback(() => {
    otEvents().then(setEv).catch(() => undefined);
    otAlarms().then(setAlarms).catch(() => undefined);
  }, []);
  useEffect(() => {
    otSynoptic().then((s) => { setWidgets(s.widgets); setLinks(s.links || []); }).catch(() => undefined);
    getConfig<SupLinkField[]>("sup_link_fields").then((f) => { if (f?.length) setLinkFields(f); }).catch(() => undefined);
    loadData();
  }, [loadData]);
  useEffect(() => {
    if (mode !== "run") return;
    const id = window.setInterval(loadData, 2500);
    return () => window.clearInterval(id);
  }, [mode, loadData]);

  const flash = (m: string) => { setMsg(m); window.setTimeout(() => setMsg(""), 2800); };
  const val = (w: Widget): string | null => {
    if (!w.asset || !w.action) return null;
    const e = ev.find((x) => x.asset_id === w.asset && x.action === w.action);
    return e ? e.value : null;
  };
  const faulted = (w: Widget) => { const v = val(w); return v === "FAULT" || v === "FAIL" || (!!w.asset && alarms.some((a) => a.asset_id === w.asset && a.active)); };
  const num = (w: Widget) => { const v = val(w); const n = v ? parseFloat(v) : NaN; return isNaN(n) ? null : n; };
  const wmap = new Map(widgets.map((w) => [w.id, w]));

  // ── drag (edição) ──
  useEffect(() => {
    if (mode !== "edit") return;
    const mv = (e: PointerEvent) => {
      const d = drag.current, c = canvasRef.current; if (!d || !c) return;
      const r = c.getBoundingClientRect();
      const x = Math.max(0, Math.round((e.clientX - r.left - d.ox) / 8) * 8);
      const y = Math.max(0, Math.round((e.clientY - r.top - d.oy) / 8) * 8);
      setWidgets((ws) => ws.map((w) => (w.id === d.id ? { ...w, x, y } : w)));
    };
    const up = () => { if (drag.current) { drag.current = null; setDirty(true); } };
    window.addEventListener("pointermove", mv); window.addEventListener("pointerup", up);
    return () => { window.removeEventListener("pointermove", mv); window.removeEventListener("pointerup", up); };
  }, [mode]);

  const onDown = (e: React.PointerEvent, w: Widget) => {
    if (mode !== "edit" || linkMode) return;
    setSel(w.id); setSelLink(null);
    const c = canvasRef.current!.getBoundingClientRect();
    drag.current = { id: w.id, ox: e.clientX - c.left - w.x, oy: e.clientY - c.top - w.y };
  };

  const nid = () => "w" + Math.floor(performance.now());
  const add = (t: WType, orient?: "v") => {
    let [w, h] = SIZE[t];
    if (t === "pipe" && orient === "v") [w, h] = [16, 140];
    const nw: Widget = { id: nid(), type: t, x: 48, y: 48, w, h,
      label: VALUE_T.has(t) ? t : t === "process" ? "Processo" : t === "decision" ? "Decisão" : t === "terminator" ? "Início" : t,
      asset: VALUE_T.has(t) ? "M-301" : undefined, action: VALUE_T.has(t) ? (t === "vision" ? "VISION_INSPECTION" : "MACHINE_STATE") : undefined };
    if (t === "label") nw.text = "Texto";
    if (t === "button") { nw.label = "Ação"; nw.action_kind = "simulate"; }
    setWidgets((ws) => [...ws, nw]); setSel(nw.id); setSelLink(null); setDirty(true);
  };
  const patch = (p: Partial<Widget>) => { setWidgets((ws) => ws.map((w) => (w.id === sel ? { ...w, ...p } : w))); setDirty(true); };
  const patchLink = (p: Partial<Link>) => { setLinks((ls) => ls.map((l) => (l.id === selLink ? { ...l, ...p } : l))); setDirty(true); };
  const del = () => { setWidgets((ws) => ws.filter((w) => w.id !== sel)); setLinks((ls) => ls.filter((l) => l.from !== sel && l.to !== sel)); setSel(null); setDirty(true); };
  const selW = widgets.find((w) => w.id === sel) || null;
  const selL = links.find((l) => l.id === selLink) || null;
  const act = (a: "rotate" | "dup" | "front" | "back" | "del") => {
    if (a === "del") {
      if (selLink) { setLinks((ls) => ls.filter((l) => l.id !== selLink)); setSelLink(null); setDirty(true); return; }
      return del();
    }
    if (!selW) return;
    if (a === "rotate") return patch({ rot: ((selW.rot || 0) + 90) % 360 });
    if (a === "dup") { const c = { ...selW, id: nid(), x: selW.x + 16, y: selW.y + 16 }; setWidgets((ws) => [...ws, c]); setSel(c.id); setDirty(true); return; }
    const zs = widgets.map((w) => w.z || 0);
    patch({ z: a === "front" ? Math.max(0, ...zs) + 1 : Math.min(0, ...zs) - 1 });
  };
  const invalidLinks = links.filter((l) => missingFields(l as unknown as Record<string, unknown>, linkFields).length);
  const save = async () => {
    if (invalidLinks.length) { setSelLink(invalidLinks[0].id); setSel(null); flash(`⚠ ${invalidLinks.length} linha(s) com campos obrigatórios faltando`); return; }
    await otSaveSynoptic("default", widgets, links); setDirty(false); flash("✓ salvo");
  };

  // ── ações de automação (operar) ──
  const exportReport = (asset?: string) => {
    const rows = ev.filter((e) => !asset || e.asset_id === asset);
    const csv = "asset,action,value,quality,source,source_ts\n" +
      rows.map((e) => [e.asset_id, e.action, JSON.stringify(e.value), e.quality ?? "", e.source, e.source_ts].join(",")).join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const a = document.createElement("a"); a.href = url; a.download = `ot_${asset || "todos"}.csv`; a.click(); URL.revokeObjectURL(url);
  };
  const fire = async (w: Widget) => {
    switch (w.action_kind) {
      case "ack": if (w.asset) { await otAck(w.asset); loadData(); flash("alarme reconhecido"); } break;
      case "ackAll": { const r = await otAckAll(); loadData(); flash(`${r.count} ativo(s) reconhecido(s)`); break; }
      case "vision": { const r = await otVisionInspect(w.asset || undefined); loadData(); flash(`👁 visão ${r.result}${r.defect ? ": " + r.defect : ""}`); break; }
      case "qr": setQr({ asset: w.asset || null }); break;
      case "report": exportReport(w.asset); flash("relatório exportado"); break;
      case "navigate": if (w.action_target) setView(w.action_target as View); break;
      case "modal": setModal(w); break;
      default: await otSimulate(w.asset || undefined); loadData(); flash("leitura ok");
    }
  };
  const onWidgetClick = (w: Widget) => {
    if (mode === "edit") {
      if (linkMode) {
        if (!linkFrom) setLinkFrom(w.id);
        else if (linkFrom !== w.id) { const id = nid(); setLinks((ls) => [...ls, { id, from: linkFrom, to: w.id, kind: linkKind, animated: linkKind === "process", direction: "uni", priority: "normal" }]); setSel(null); setSelLink(id); setLinkFrom(null); setDirty(true); }
        return;
      }
      setSel(w.id); setSelLink(null); return;
    }
    if (w.type === "button") fire(w);
    else if (w.asset) setModal(w);
  };
  const clearSel = () => { if (mode === "edit") { setSel(null); setSelLink(null); setLinkFrom(null); } };

  return (
    <div className="flex flex-col gap-2 h-full min-h-0">
      <div className="flex items-center gap-2 flex-wrap shrink-0">
        <div className="flex rounded-card border border-edge overflow-hidden">
          {([["run", "▶ Operar"], ["edit", "✎ Editar"]] as const).map(([k, l]) => (
            <button key={k} onClick={() => { setMode(k); setSel(null); setSelLink(null); setLinkMode(false); }}
              className={"px-3 py-1.5 text-sm font-semibold " + (mode === k ? "bg-accent text-onaccent" : "bg-edge text-muted hover:text-text")}>{l}</button>
          ))}
        </div>
        {mode === "edit" && <>
          <span className="text-[11px] text-muted">{linkMode ? (linkFrom ? "clique o destino p/ conectar" : "clique a origem da linha") : "arraste · clique p/ editar · 🔗 conecta o modelo"}</span>
          <button className={btnPrimaryCls + " ml-auto"} onClick={save} disabled={!dirty}>{invalidLinks.length ? `⚠ ${invalidLinks.length} pendência(s)` : dirty ? "💾 Salvar" : "salvo"}</button>
        </>}
        {mode === "run" && <button className={btnCls + " ml-auto"} onClick={() => { otSimulate().then(loadData); }}>▶ Atualizar (ler)</button>}
        {msg && <span className="text-xs text-ok">{msg}</span>}
      </div>

      {mode === "edit" && <Toolbar add={add} act={act} hasSel={!!sel || !!selLink} grid={grid} toggleGrid={() => setGrid((g) => !g)}
        linkMode={linkMode} linkKind={linkKind} setLinkKind={setLinkKind} toggleLink={() => { setLinkMode((m) => !m); setLinkFrom(null); }} />}

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-[1fr_250px] gap-2 min-h-0">
        {/* CANVAS */}
        <div className="overflow-auto scroll-thin rounded-card border border-edge" style={{ background: "#c9ccd1" }}>
          <div ref={canvasRef} onClick={clearSel} className="relative w-full h-full" style={{ minWidth: 1100, minHeight: 640,
            backgroundImage: grid ? "linear-gradient(#0001 1px,transparent 1px),linear-gradient(90deg,#0001 1px,transparent 1px)" : undefined, backgroundSize: "16px 16px" }}>
            {/* LINHAS DO DIAGRAMA (P&ID) */}
            <svg className="absolute inset-0" width="100%" height="100%" style={{ overflow: "visible", pointerEvents: "none" }}>
              <defs>{(Object.keys(LINK_STYLE) as LinkKind[]).map((k) => (
                <marker key={k} id={"arr-" + k} markerWidth="10" markerHeight="10" refX="7" refY="4" orient="auto" markerUnits="userSpaceOnUse">
                  <path d="M0,0 L8,4 L0,8 Z" fill={LINK_STYLE[k].stroke} /></marker>
              ))}</defs>
              {links.map((l) => {
                const s = wmap.get(l.from), t = wmap.get(l.to); if (!s || !t) return null;
                const pts = anchors(s, t), d = pathOf(pts), st = LINK_STYLE[l.kind], col = l.color || st.stroke;
                const lx = (pts[1][0] + pts[2][0]) / 2, ly = (pts[1][1] + pts[2][1]) / 2, on = selLink === l.id;
                return (
                  <g key={l.id}>
                    {on && <path d={d} fill="none" stroke="#19C3B2" strokeWidth={st.width + 7} strokeOpacity={0.3} strokeLinejoin="round" />}
                    <path d={d} fill="none" stroke={col} strokeWidth={st.width} strokeDasharray={st.dash} markerEnd={`url(#arr-${l.kind})`} strokeLinejoin="round" strokeLinecap="round" />
                    {l.animated && <path d={d} fill="none" stroke="#fff" strokeOpacity={0.6} strokeWidth={Math.max(1.5, st.width - 2.5)} strokeDasharray="6 16" strokeLinecap="round">
                      <animate attributeName="stroke-dashoffset" from="22" to="0" dur="0.8s" repeatCount="indefinite" /></path>}
                    {l.label && <text x={lx} y={ly - 5} fontSize="10" textAnchor="middle" fill={col} stroke="#0b1220" strokeWidth="3" paintOrder="stroke" fontWeight={600}>{l.label}</text>}
                    {mode === "edit" && missingFields(l as unknown as Record<string, unknown>, linkFields).length > 0 && (
                      <g><circle cx={lx} cy={ly + 9} r="7" fill="#e5484d" /><text x={lx} y={ly + 12.5} fontSize="10" textAnchor="middle" fill="#fff" fontWeight={800}>!</text></g>
                    )}
                    {mode === "edit" && <path d={d} fill="none" stroke="transparent" strokeWidth={16} style={{ pointerEvents: "stroke", cursor: "pointer" }}
                      onClick={(e) => { e.stopPropagation(); setSelLink(l.id); setSel(null); }} />}
                  </g>
                );
              })}
            </svg>
            {/* NÓS */}
            {widgets.map((w) => (
              <div key={w.id} onPointerDown={(e) => onDown(e, w)} onClick={(e) => { e.stopPropagation(); onWidgetClick(w); }}
                className={"absolute " + (mode === "edit" ? (linkMode ? "cursor-crosshair " : "cursor-move ") : "cursor-pointer ")
                  + (sel === w.id ? "ring-2 ring-accent " : "") + (linkFrom === w.id ? "ring-2 ring-warn " : "")}
                style={{ left: w.x, top: w.y, width: w.w, height: w.h, zIndex: w.z, transform: w.rot ? `rotate(${w.rot}deg)` : undefined }}>
                <WidgetView w={w} v={val(w)} n={num(w)} fault={faulted(w)} />
              </div>
            ))}
          </div>
        </div>

        {/* PROPRIEDADES / LEGENDA */}
        <aside className="bg-panel rounded-card border border-edge p-3 overflow-y-auto scroll-thin text-sm">
          {mode === "edit" ? (
            selL ? <LinkProps l={selL} fields={linkFields} patch={patchLink} del={() => act("del")} /> :
              selW ? <Props w={selW} patch={patch} act={act} /> :
                <p className="text-xs text-muted">Selecione um elemento/linha p/ editar. Adicione pelo <b>menu de ícones</b>; use <b>🔗 Conectar</b> p/ ligar o modelo (linhas P&ID).</p>
          ) : (
            <RunLegend alarms={alarms} onQr={() => setQr({ asset: null })} onVision={async () => { const r = await otVisionInspect(); loadData(); flash(`👁 ${r.result}${r.defect ? ": " + r.defect : ""}`); }} />
          )}
        </aside>
      </div>

      {modal && <DetailModal w={modal} ev={ev} onClose={() => setModal(null)}
        onRead={async () => { await otSimulate(modal.asset || undefined); loadData(); }}
        onAck={modal.asset ? async () => { await otAck(modal.asset!); loadData(); } : undefined}
        onQr={() => setQr({ asset: modal.asset || null })}
        onVision={async () => { const r = await otVisionInspect(modal.asset || undefined); loadData(); flash(`👁 ${r.result}${r.defect ? ": " + r.defect : ""}`); }} />}
      {qr && <QrLabelModal assetId={qr.asset} onClose={() => setQr(null)} />}
    </div>
  );
}

// ── Menu de ícones (ações / fluxograma / conexões) ──
function Toolbar({ add, act, hasSel, grid, toggleGrid, linkMode, linkKind, setLinkKind, toggleLink }: {
  add: (t: WType, o?: "v") => void; act: (a: "rotate" | "dup" | "front" | "back" | "del") => void;
  hasSel: boolean; grid: boolean; toggleGrid: () => void;
  linkMode: boolean; linkKind: LinkKind; setLinkKind: (k: LinkKind) => void; toggleLink: () => void;
}) {
  const Btn = ({ on, ic, title, dis, active }: { on: () => void; ic: string; title: string; dis?: boolean; active?: boolean }) => (
    <button title={title} disabled={dis} onClick={on}
      className={"w-7 h-7 rounded border text-sm leading-none flex items-center justify-center disabled:opacity-25 disabled:hover:border-edge "
        + (active ? "bg-accent text-onaccent border-accent" : "border-edge bg-edge hover:border-accent hover:text-accent")}>{ic}</button>
  );
  const Sep = () => <span className="w-px h-6 bg-edge mx-1 shrink-0" />;
  const Lbl = ({ t }: { t: string }) => <span className="text-[9px] uppercase tracking-wider text-muted mr-0.5 shrink-0">{t}</span>;
  return (
    <div className="flex items-center gap-1 flex-wrap bg-panel border border-edge rounded-card px-2 py-1.5 shrink-0">
      <Lbl t="Elem" />
      {PALETTE.map((p) => <Btn key={p.t} ic={p.ic} title={p.l} on={() => add(p.t)} />)}
      <Sep />
      <Lbl t="Fluxo" />
      <Btn ic="―" title="Tubo horizontal" on={() => add("pipe")} />
      <Btn ic="│" title="Tubo vertical" on={() => add("pipe", "v")} />
      <Btn ic="➜" title="Seta de fluxo" on={() => add("arrow")} />
      <Btn ic="▭" title="Processo" on={() => add("process")} />
      <Btn ic="◇" title="Decisão" on={() => add("decision")} />
      <Btn ic="⬭" title="Início / Fim" on={() => add("terminator")} />
      <Sep />
      <Lbl t="Conexão" />
      <select value={linkKind} onChange={(e) => setLinkKind(e.target.value as LinkKind)} title="Tipo de linha"
        className="h-7 text-xs rounded border border-edge bg-edge px-1">
        {(Object.keys(LINK_STYLE) as LinkKind[]).map((k) => <option key={k} value={k}>{LINK_STYLE[k].lbl}</option>)}
      </select>
      <Btn ic="🔗" title="Conectar (clique origem → destino)" active={linkMode} on={toggleLink} />
      <Sep />
      <Lbl t="Ações" />
      <Btn ic="⟳" title="Girar 90°" dis={!hasSel} on={() => act("rotate")} />
      <Btn ic="⧉" title="Duplicar" dis={!hasSel} on={() => act("dup")} />
      <Btn ic="⤒" title="Trazer p/ frente" dis={!hasSel} on={() => act("front")} />
      <Btn ic="⤓" title="Enviar p/ trás" dis={!hasSel} on={() => act("back")} />
      <Btn ic="🗑" title="Excluir" dis={!hasSel} on={() => act("del")} />
      <Sep />
      <Btn ic={grid ? "▦" : "▢"} title="Grade on/off" on={toggleGrid} />
    </div>
  );
}

// ── Legenda / ações rápidas (operar) ──
function RunLegend({ alarms, onQr, onVision }: { alarms: OtAlarm[]; onQr: () => void; onVision: () => void }) {
  const active = alarms.filter((a) => a.active);
  return (
    <>
      <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Supervisório</h3>
      <p className="text-[11px] text-muted">Clique num elemento p/ detalhe/ação. Botões executam (ler/ack/visão/QR). Vinculado à simulação OT — <b>read-only</b>.</p>
      <div className="mt-2 space-y-1">
        {[["RUN/AUTO/PASS", "bg-ok"], ["FAULT/FAIL/alarme", "bg-nok"], ["parado/sem dado", "bg-muted"]].map(([t, c]) => (
          <div key={t} className="flex items-center gap-2 text-[11px]"><span className={"w-2.5 h-2.5 rounded-full " + c} />{t}</div>
        ))}
      </div>
      <div className="mt-3 pt-2 border-t border-edge space-y-1.5">
        <h4 className="text-[10px] uppercase tracking-wider text-muted">Linhas P&amp;ID</h4>
        {(Object.keys(LINK_STYLE) as LinkKind[]).map((k) => (
          <div key={k} className="flex items-center gap-2 text-[11px]"><span className="inline-block w-6 h-0" style={{ borderTop: `${LINK_STYLE[k].width}px ${LINK_STYLE[k].dash ? "dashed" : "solid"} ${LINK_STYLE[k].stroke}` }} />{LINK_STYLE[k].lbl}</div>
        ))}
      </div>
      <div className="mt-3 pt-2 border-t border-edge space-y-1.5">
        <button className={btnCls + " w-full"} onClick={onVision}>👁 Inspeção de visão (PR-22)</button>
        <button className={btnCls + " w-full"} onClick={onQr} disabled={!active.length}>🏷 Etiqueta QR do alarme</button>
        <p className="text-[10px] text-muted">{active.length} alarme(s) ativo(s).</p>
      </div>
    </>
  );
}

// ── Render de cada widget (estilo HMI industrial) ──
function WidgetView({ w, v, n, fault }: { w: Widget; v: string | null; n: number | null; fault: boolean }) {
  const run = !fault && !!v && RUN.has(v);
  const stColor = fault ? "#e5484d" : run ? "#30a46c" : "#8b8d98";
  const box = "w-full h-full flex flex-col items-center justify-center";
  if (w.type === "label") return <div className="w-full h-full flex items-center font-bold text-sm" style={{ color: w.color || "#1a1d23" }}>{w.text || w.label}</div>;
  if (w.type === "pipe") { const horiz = w.w >= w.h; return (
    <div className="w-full h-full" style={{ borderRadius: 99,
      background: w.color || `linear-gradient(${horiz ? "to bottom" : "to right"},#c2c6cc,#868b94 48%,#5a5f68)`,
      boxShadow: "inset 0 1px 2px #ffffff80, inset 0 -2px 3px #00000055" }} />
  ); }
  if (w.type === "arrow") return (
    <svg viewBox="0 0 56 40" className="w-full h-full"><polygon points="2,13 32,13 32,5 54,20 32,35 32,27 2,27" fill={w.color || "#3da9fc"} stroke="#0006" /></svg>
  );
  if (w.type === "process") return (
    <div className="w-full h-full flex items-center justify-center rounded border-2 text-xs font-semibold text-center px-1" style={{ borderColor: w.color || "#5b606b", background: "#eef0f3", color: "#1a1d23" }}>{w.label}</div>
  );
  if (w.type === "decision") return (
    <div className="relative w-full h-full flex items-center justify-center">
      <div className="absolute" style={{ inset: "14%", transform: "rotate(45deg)", border: `2px solid ${w.color || "#5b606b"}`, background: "#eef0f3" }} />
      <span className="relative text-[10px] font-semibold text-center px-1" style={{ color: "#1a1d23" }}>{w.label}</span>
    </div>
  );
  if (w.type === "terminator") return (
    <div className="w-full h-full flex items-center justify-center text-xs font-semibold px-2 border-2" style={{ borderRadius: 999, borderColor: w.color || "#5b606b", background: "#eef0f3", color: "#1a1d23" }}>{w.label}</div>
  );
  if (w.type === "vision") return (
    <div className="w-full h-full rounded-lg border-2 flex flex-col items-center justify-center gap-0.5" style={{ borderColor: stColor, background: "#0e1116" }}>
      <span className="text-2xl leading-none">👁</span>
      <div className="text-[10px] font-semibold text-white/80 truncate max-w-full px-1">{w.label}</div>
      <div className="text-[11px] font-bold" style={{ color: stColor }}>{v ?? "—"}</div>
    </div>
  );
  if (w.type === "tag") return (
    <div className="w-full h-full rounded bg-[#111] border-2 px-2 py-1 flex flex-col justify-center" style={{ borderColor: w.color || "#3da9fc" }}>
      <div className="text-[9px] text-white/60 uppercase truncate">{w.label}</div>
      <div className="text-lg font-bold font-mono" style={{ color: w.color || "#3da9fc" }}>{v ?? "—"}<span className="text-[10px] ml-0.5 text-white/50">{w.unit}</span></div>
    </div>
  );
  if (w.type === "gauge") { const pct = n != null ? Math.min(100, (n / (w.max || 100)) * 100) : 0; return (
    <div className={box}>
      <div className="text-[9px] text-[#1a1d23] font-semibold truncate w-full text-center">{w.label}</div>
      <div className="flex-1 w-5 bg-[#2b2f36] rounded relative overflow-hidden my-1">
        <div className="absolute bottom-0 w-full" style={{ height: `${pct}%`, background: pct > 85 ? "#e5484d" : "#3da9fc" }} />
      </div>
      <div className="text-[11px] font-mono font-bold text-[#1a1d23]">{v ?? "—"}{w.unit}</div>
    </div>
  ); }
  if (w.type === "tank") { const pct = n != null ? Math.min(100, n) : 0; return (
    <div className={box}>
      <div className="text-[10px] font-semibold text-[#1a1d23]">{w.label}</div>
      <div className="flex-1 w-full border-2 border-[#5b606b] rounded-lg relative overflow-hidden my-1" style={{ background: "#dfe2e6" }}>
        <div className="absolute bottom-0 w-full transition-all" style={{ height: `${pct}%`, background: "linear-gradient(#7cc4ff,#2f7fd1)" }} />
        <div className="absolute inset-0 flex items-center justify-center text-[12px] font-bold font-mono text-[#1a1d23]">{v ?? "—"}{w.unit}</div>
      </div>
    </div>
  ); }
  if (w.type === "valve") return (
    <div className={box}><svg viewBox="0 0 40 32" className="w-12 h-10">
      <polygon points="2,4 2,28 20,16" fill={stColor} stroke="#333" /><polygon points="38,4 38,28 20,16" fill={stColor} stroke="#333" />
    </svg><div className="text-[9px] font-semibold text-[#1a1d23]">{w.label}{v ? ` · ${v}` : ""}</div></div>
  );
  if (w.type === "pump" || w.type === "fan" || w.type === "motor") return (
    <div className={box}>
      <div className="rounded-full flex items-center justify-center" style={{ width: 44, height: 44, background: stColor, boxShadow: "inset 0 0 0 3px #ffffff55" }}>
        <span className={"text-white text-lg " + (run && w.type === "fan" ? "animate-spin" : "")}>{w.type === "pump" ? "⛽" : w.type === "fan" ? "✲" : "M"}</span>
      </div>
      <div className="text-[10px] font-semibold mt-0.5 text-[#1a1d23]">{w.label}</div>
      <div className="text-[9px] font-mono text-[#1a1d23]">{v ?? "—"}{w.unit || ""}</div>
    </div>
  );
  if (w.type === "machine") return (
    <div className="w-full h-full rounded-lg border-2 p-1.5 flex flex-col" style={{ borderColor: stColor, background: "#eef0f3" }}>
      <div className="text-[10px] font-bold text-[#1a1d23]">{w.label}</div>
      <div className="flex-1 flex items-center justify-center"><span className="text-2xl">🏭</span></div>
      <div className="text-center text-[11px] font-bold" style={{ color: stColor }}>● {v ?? "—"}</div>
    </div>
  );
  if (w.type === "lamp") return (
    <div className="w-full h-full flex items-center gap-2 px-2 rounded border border-[#5b606b]" style={{ background: "#eef0f3" }}>
      <span className="w-6 h-6 rounded-full shrink-0" style={{ background: stColor, boxShadow: `0 0 8px ${stColor}` }} />
      <span className="text-[11px] font-semibold leading-tight text-[#1a1d23]">{w.label}<br /><span className="text-muted">{v ?? "—"}</span></span>
    </div>
  );
  if (w.type === "switch") return (
    <div className="w-full h-full rounded border border-[#5b606b] flex flex-col items-center justify-center" style={{ background: "#dfe2e6" }}>
      <div className="text-[9px] font-semibold mb-0.5 text-[#1a1d23]">{w.label}</div>
      <div className="flex gap-0.5">{["AUTO", "MAN", "OFF"].map((s) => (
        <span key={s} className={"text-[8px] px-1 py-0.5 rounded " + (v === s ? "bg-[#30a46c] text-white" : "bg-[#b9bcc2] text-[#333]")}>{s}</span>
      ))}</div>
    </div>
  );
  return <button className="w-full h-full rounded-card font-semibold text-sm bg-accent text-onaccent hover:brightness-110 shadow">{w.label}</button>;
}

// ── Propriedades de elemento ──
function Props({ w, patch, act }: { w: Widget; patch: (p: Partial<Widget>) => void; act: (a: "rotate" | "dup" | "front" | "back" | "del") => void }) {
  const isBtn = w.type === "button"; const isLabel = w.type === "label";
  const isFlow = w.type === "pipe" || w.type === "arrow";
  const hasLabel = !isFlow && !isLabel && !isBtn;
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between border-b border-edge pb-1">
        <h3 className="text-xs uppercase tracking-wider text-muted">{w.type}</h3>
        <div className="flex gap-1">
          <button title="Girar" className="text-xs px-1.5 rounded border border-edge hover:border-accent" onClick={() => act("rotate")}>⟳</button>
          <button title="Duplicar" className="text-xs px-1.5 rounded border border-edge hover:border-accent" onClick={() => act("dup")}>⧉</button>
          <button title="Excluir" className="text-xs px-1.5 rounded border border-edge text-nok hover:border-nok" onClick={() => act("del")}>🗑</button>
        </div>
      </div>
      {isLabel && <div><label className={labelCls}>Texto</label><input className={inputCls} value={w.text || ""} onChange={(e) => patch({ text: e.target.value })} /></div>}
      {(hasLabel || isBtn) && <div><label className={labelCls}>Rótulo</label><input className={inputCls} value={w.label || ""} onChange={(e) => patch({ label: e.target.value })} /></div>}
      {VALUE_T.has(w.type) && <>
        <div><label className={labelCls}>Ativo (bind)</label><select className={selectCls} value={w.asset || ""} onChange={(e) => patch({ asset: e.target.value })}><option value="">—</option>{ASSETS.map((a) => <option key={a}>{a}</option>)}</select></div>
        <div><label className={labelCls}>Sinal</label><select className={selectCls} value={w.action || ""} onChange={(e) => patch({ action: e.target.value })}>{ACTIONS.map((a) => <option key={a}>{a}</option>)}</select></div>
        {(w.type === "tag" || w.type === "gauge" || w.type === "tank") &&
          <div><label className={labelCls}>Unidade</label><input className={inputCls} value={w.unit || ""} onChange={(e) => patch({ unit: e.target.value })} /></div>}
        {w.type === "gauge" && <div><label className={labelCls}>Máx</label><input type="number" className={inputCls} value={w.max ?? 100} onChange={(e) => patch({ max: Number(e.target.value) })} /></div>}
      </>}
      {COLOR_T.has(w.type) && <div><label className={labelCls}>Cor</label><input className={inputCls} value={w.color || ""} onChange={(e) => patch({ color: e.target.value })} placeholder="#3da9fc" /></div>}
      {isBtn && <>
        <div><label className={labelCls}>Ação</label><select className={selectCls} value={w.action_kind || "simulate"} onChange={(e) => patch({ action_kind: e.target.value as Widget["action_kind"] })}>
          <option value="simulate">Ler (simular)</option><option value="ack">Reconhecer (ativo)</option><option value="ackAll">Reconhecer todos</option>
          <option value="vision">Inspeção de visão</option><option value="qr">Gerar etiqueta QR</option><option value="report">Exportar relatório CSV</option>
          <option value="modal">Abrir detalhe</option><option value="navigate">Navegar p/ módulo</option></select></div>
        {w.action_kind === "navigate"
          ? <div><label className={labelCls}>View destino</label><input className={inputCls} value={w.action_target || ""} onChange={(e) => patch({ action_target: e.target.value })} placeholder="ex.: eventos" /></div>
          : w.action_kind !== "ackAll" &&
          <div><label className={labelCls}>Ativo alvo</label><select className={selectCls} value={w.asset || ""} onChange={(e) => patch({ asset: e.target.value })}><option value="">(todos)</option>{ASSETS.map((a) => <option key={a}>{a}</option>)}</select></div>}
      </>}
      <div className="grid grid-cols-3 gap-1">
        {(["x", "y", "w", "h"] as const).map((k) => <div key={k}><label className={labelCls}>{k.toUpperCase()}</label><input type="number" className={inputCls} value={w[k]} onChange={(e) => patch({ [k]: Number(e.target.value) } as Partial<Widget>)} /></div>)}
        <div><label className={labelCls}>Rot°</label><input type="number" step={15} className={inputCls} value={w.rot || 0} onChange={(e) => patch({ rot: Number(e.target.value) })} /></div>
      </div>
    </div>
  );
}

// ── Propriedades de linha do processo (P&ID · supervisório avançado) ──
function LinkProps({ l, fields, patch, del }: { l: Link; fields: SupLinkField[]; patch: (p: Partial<Link>) => void; del: () => void }) {
  const rec = l as unknown as Record<string, unknown>;
  const miss = missingFields(rec, fields);
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between border-b border-edge pb-1">
        <h3 className="text-xs uppercase tracking-wider text-muted">linha · {l.from}→{l.to}</h3>
        <button title="Excluir" className="text-xs px-1.5 rounded border border-edge text-nok hover:border-nok" onClick={del}>🗑</button>
      </div>
      {miss.length > 0 && <div className="text-[11px] text-nok bg-nok/10 border border-nok/30 rounded px-2 py-1">⚠ obrigatórios faltando: {miss.join(", ")}</div>}
      <div><label className={labelCls}>Tipo de linha</label><select className={selectCls} value={l.kind} onChange={(e) => patch({ kind: e.target.value as LinkKind })}>
        {(Object.keys(LINK_STYLE) as LinkKind[]).map((k) => <option key={k} value={k}>{LINK_STYLE[k].lbl}</option>)}</select></div>

      {/* campos do processo (schema do banco · obrigatórios por kind) */}
      {fields.map((f) => {
        const req = f.required.includes(l.kind);
        const v = rec[f.name];
        const bad = req && (v == null || (typeof v === "string" && !v.trim()));
        const lab = <label className={labelCls}>{f.label}{req && <span className="text-nok"> *</span>}</label>;
        if (f.type === "bool") return <label key={f.name} className="flex items-center gap-2 text-sm cursor-pointer"><input type="checkbox" checked={!!v} onChange={(e) => patch({ [f.name]: e.target.checked } as Partial<Link>)} /> {f.label}</label>;
        if (f.type === "select") return <div key={f.name}>{lab}<select className={bad ? selectCls + " border-nok" : selectCls} value={(v as string) || ""} onChange={(e) => patch({ [f.name]: e.target.value } as Partial<Link>)}><option value="">—</option>{f.options?.map((o) => <option key={o} value={o}>{o}</option>)}</select></div>;
        return <div key={f.name}>{lab}<input className={bad ? inputCls + " border-nok" : inputCls} value={(v as string) || ""} placeholder={f.placeholder} onChange={(e) => patch({ [f.name]: e.target.value } as Partial<Link>)} /></div>;
      })}

      <div className="border-t border-edge pt-2 space-y-2">
        <div><label className={labelCls}>Rótulo no diagrama</label><input className={inputCls} value={l.label || ""} onChange={(e) => patch({ label: e.target.value })} placeholder="ex.: linha de recalque" /></div>
        <div><label className={labelCls}>Cor</label><input className={inputCls} value={l.color || ""} onChange={(e) => patch({ color: e.target.value })} placeholder={LINK_STYLE[l.kind].stroke} /></div>
        <label className="flex items-center gap-2 text-sm cursor-pointer"><input type="checkbox" checked={!!l.animated} onChange={(e) => patch({ animated: e.target.checked })} /> Fluxo animado</label>
        <button className={btnCls + " w-full"} onClick={() => patch({ from: l.to, to: l.from })}>⇄ Inverter sentido</button>
      </div>
    </div>
  );
}

// ── Modal de detalhe/ação ──
function DetailModal({ w, ev, onClose, onRead, onAck, onQr, onVision }: {
  w: Widget; ev: OtEvent[]; onClose: () => void; onRead: () => void; onAck?: () => void; onQr: () => void; onVision: () => void;
}) {
  const recent = ev.filter((e) => e.asset_id === w.asset).slice(0, 8);
  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center p-4 bg-black/50" onClick={onClose}>
      <div className="vd-surface border border-edge rounded-card w-full max-w-md p-4 space-y-3" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2"><h3 className="font-bold">{w.label} · {w.asset || "—"}</h3><button className="ml-auto text-muted hover:text-text" onClick={onClose}>✕</button></div>
        <div className="flex gap-2 flex-wrap">
          <button className={btnPrimaryCls} onClick={onRead}>▶ Ler agora</button>
          <button className={btnCls} onClick={onVision}>👁 Inspeção visão</button>
          {onAck && <button className={btnCls} onClick={onAck}>Reconhecer</button>}
          <button className={btnCls} onClick={onQr}>🏷 QR</button>
        </div>
        <div>
          <div className="text-xs uppercase tracking-wider text-muted mb-1">Últimos eventos</div>
          <div className="space-y-0.5 max-h-56 overflow-y-auto scroll-thin">
            {recent.length === 0 ? <p className="text-xs text-muted">sem dados — clique Ler.</p> : recent.map((e, i) => (
              <div key={i} className="text-[11px] flex gap-2 border-b border-edge/40 py-0.5">
                <span className="text-muted">{new Date(e.source_ts).toLocaleTimeString()}</span>
                <span className={"font-semibold " + (e.action.includes("ALARM") || e.action.includes("FAIL") || e.action.includes("FAULT") ? "text-nok" : "text-text")}>{e.action}</span>
                <span className="text-muted truncate ml-auto">{e.value}</span>
              </div>
            ))}
          </div>
        </div>
        <p className="text-[10px] text-muted">Observador (read-only): lê, inspeciona (visão), reconhece e gera QR — não escreve no PLC.</p>
      </div>
    </div>
  );
}
