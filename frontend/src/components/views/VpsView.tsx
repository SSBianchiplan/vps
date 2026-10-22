import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  advanceThread, bindSource, clearPending, clearReconDocs, connectVpsLive, correctThread, downloadGold,
  exportThread, getBoard, getBridge, getGoldModels, getKpis, getLgpd, getRecon, getRoles, getSegments, getThread,
  getVpsRole, importReconCsv, resolveOccurrence, seedRecon, seedVps, setAutoCapture, setGenesisSegment, setLgpd,
  setVpsRole, sweepLgpd,
  type Board, type BoardCard, type BridgeStatus, type GoldModel, type Kpis, type LabelData, type Lgpd, type Recon, type RolesInfo, type SegmentInfo, type Thread,
} from "../../api/vps";
import { LabelGenerator } from "../vps/LabelGenerator";
import { StationScanner } from "../vps/StationScanner";
import { useStore } from "../../store/useStore";

// ── helpers ──────────────────────────────────────────────────────────
const fmtAge = (h: number) => (h < 1 ? "<1h" : h < 24 ? `${Math.round(h)}h` : `${(h / 24).toFixed(1)}d`);
const fmtTs = (s: string) => new Date(s).toLocaleString();

const SLA_COLOR: Record<string, string> = { ok: "var(--ok)", warn: "var(--warn)", late: "var(--nok)" };
const stateBadge = (s: string) =>
  s === "EXCEPTION" ? "bg-nok/15 text-nok" :
  s === "COMPLETED" || s === "ARCHIVED" ? "bg-ok/15 text-ok" :
  s === "IN_PROCESS" ? "bg-accent/15 text-accent" : "bg-edge text-muted";

const KPI_DEFS: { key: string; label: string; suffix?: string; accent?: string; currency?: boolean }[] = [
  { key: "CLD_Thread_LeadTime_h", label: "Lead time médio", suffix: "h", accent: "var(--accent)" },
  { key: "CLD_OTIF", label: "OTIF", suffix: "%", accent: "var(--ok)" },
  { key: "CLD_Schedule_Adherence", label: "Aderência", suffix: "%", accent: "var(--text)" },
  { key: "CLD_Active_Threads", label: "Fios ativos", accent: "var(--text)" },
  { key: "CLD_Completed_Threads", label: "Concluídos", accent: "var(--ok)" },
  { key: "CLD_Pending_Open", label: "Pendências", accent: "var(--warn)" },
  { key: "CLD_Occurrence_Open", label: "Ocorrências", accent: "var(--nok)" },
  { key: "CLD_Cost_of_Pendencies", label: "Custo pendências", currency: true, accent: "var(--nok)" },
  { key: "CLD_Reconciliation_Rate", label: "Reconciliação", suffix: "%", accent: "var(--text)" },
  { key: "CLD_Vision_Coverage", label: "Cobertura visão", suffix: "%", accent: "var(--text)" },
];

const LANES: { key: string; label: string }[] = [
  { key: "OP", label: "OP" }, { key: "SO", label: "Pedidos" },
  { key: "PROJ", label: "Projetos" }, { key: "SHIP", label: "Logística" },
  { key: "all", label: "Todos" },
];

const RECON_COLOR: Record<string, string> = { MATCHED: "var(--ok)", DIVERGENT: "var(--nok)", PENDING: "var(--muted)" };

// Pai (linhagem) → "TIPO:chave" p/ prefixar a etiqueta a partir de um Fio existente.
function parentToInit(parentTagId?: string): string {
  const p = (parentTagId || "").split(":");
  return p.length >= 4 && p[0] === "VPS" ? `${p[2]}:${p[3]}` : "";
}

// ── Card do board ────────────────────────────────────────────────────
function Card({ c, onOpen }: { c: BoardCard; onOpen: () => void }) {
  const border = c.state === "EXCEPTION" ? "var(--nok)" : SLA_COLOR[c.sla_status] ?? "var(--edge)";
  return (
    <button onClick={onOpen}
      className="w-full text-left bg-surface border rounded-card p-2.5 hover:border-accent transition-colors"
      style={{ borderColor: border, borderLeftWidth: 3 }}>
      <div className="flex items-center gap-1.5 mb-1">
        <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-edge text-muted shrink-0">{c.entity_type}</span>
        <span className="text-xs font-semibold text-text truncate flex-1" title={c.tag_id}>{c.natural_key}</span>
      </div>
      <div className="flex items-center gap-2 text-[10px] text-muted">
        <span className={"px-1.5 py-0.5 rounded " + stateBadge(c.state)}>{c.state}</span>
        <span title="tempo na fase">⏱ {fmtAge(c.aging_h)}{c.sla_h ? `/${fmtAge(c.sla_h)}` : ""}</span>
        <span className="ml-auto flex gap-1.5">
          {c.pendings > 0 && <span className="text-nok" title="pendências">⛔{c.pendings}</span>}
          {c.occurrences > 0 && <span className="text-warn" title="ocorrências">⚠{c.occurrences}</span>}
        </span>
      </div>
      {c.eta_breach_h != null && (c.risk === "high" || c.risk === "late") && (
        <p className={"text-[10px] mt-1 " + (c.risk === "late" ? "text-nok" : "text-warn")}>
          {c.eta_breach_h < 0 ? `⚠ SLA estourou há ${fmtAge(-c.eta_breach_h)}` : `⏳ estoura em ${fmtAge(c.eta_breach_h)}`}
        </p>
      )}
    </button>
  );
}

// ── Drawer do Fio Dourado ────────────────────────────────────────────
function ThreadDrawer({ tagId, onClose, onNav, onBound, onLabel }: { tagId: string; onClose: () => void; onNav: (t: string) => void; onBound: () => void; onLabel: (init: Partial<LabelData>) => void }) {
  const [t, setT] = useState<Thread | null>(null);
  const [scanOpen, setScanOpen] = useState(false);
  const saved = useStore((s) => s.savedCameras);
  const reload = useCallback(() => { getThread(tagId).then(setT).catch(() => undefined); onBound(); }, [tagId, onBound]);
  useEffect(() => { setT(null); getThread(tagId).then(setT).catch(() => undefined); }, [tagId]);
  const linkCam = async (sid: string) => { if (sid) { await bindSource(sid, tagId); onBound(); } };
  const guard = async (fn: () => Promise<unknown>) => { try { await fn(); reload(); } catch (e) { window.alert((e as Error).message); } };
  const doAdvance = () => guard(() => advanceThread(tagId));
  const doCorrect = async () => { const n = window.prompt("Nota da correção (evento compensatório):"); if (n) guard(() => correctThread(tagId, n)); };
  const doClearPending = (id: string) => guard(() => clearPending(id));
  const doResolveOcc = (id: string) => guard(() => resolveOccurrence(id));

  const body = (
    <div className="fixed inset-0 z-[120] flex justify-end" style={{ background: "rgba(0,0,0,0.5)" }} onClick={onClose}>
      <div className="w-full max-w-lg h-full bg-surface border-l border-edge overflow-y-auto scroll-thin p-4 space-y-4"
        onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start gap-2">
          <div className="flex-1 min-w-0">
            <p className="text-[10px] text-muted uppercase tracking-wider">Fio Dourado 🧵</p>
            <h3 className="text-base font-bold truncate" title={tagId}>{t?.tag?.natural_key ?? tagId}</h3>
            <p className="text-[10px] text-muted truncate">{tagId}</p>
          </div>
          <button onClick={onClose} className="text-muted hover:text-text text-lg">✕</button>
        </div>

        {!t ? <p className="text-xs text-muted">Carregando…</p> : (
          <>
            <div className="flex flex-wrap gap-2 text-[11px]">
              <span className={"px-2 py-0.5 rounded " + stateBadge(String(t.tag.state))}>{t.tag.state}</span>
              <span className="px-2 py-0.5 rounded bg-edge text-muted">fase: {t.tag.current_phase}</span>
              <span className="px-2 py-0.5 rounded bg-edge text-muted">template: {t.tag.template_id}</span>
            </div>

            {/* Ações de governança */}
            <div className="flex gap-2 flex-wrap">
              {!["COMPLETED", "ARCHIVED"].includes(String(t.tag.state)) && (
                <button onClick={doAdvance} className="text-[11px] px-2.5 py-1 rounded-card border border-accent/50 text-accent hover:bg-accent/10">▶ Avançar fase</button>
              )}
              <button onClick={doCorrect} className="text-[11px] px-2.5 py-1 rounded-card border border-edge text-muted hover:border-accent">✎ Correção (compensação)</button>
              <button onClick={() => exportThread(tagId, String(t.tag.natural_key ?? "tag"))} className="text-[11px] px-2.5 py-1 rounded-card border border-edge text-muted hover:border-accent">⬇ Auditoria</button>
              <button onClick={() => onLabel({
                segment: String(t.tag.segment ?? "PANEL"), entity_type: String(t.tag.entity_type ?? "OP"),
                natural_key: String(t.tag.natural_key ?? ""), instance: String(t.tag.instance ?? "01"),
                parent: parentToInit(t.lineage.parents[0]?.parent_tag_id), estado: String(t.tag.state ?? ""),
                phase: String(t.tag.current_phase ?? ""), template_id: String(t.tag.template_id ?? ""),
              })} className="text-[11px] px-2.5 py-1 rounded-card border border-edge text-muted hover:border-accent">🏷 Etiqueta</button>
            </div>

            {/* Câmera deste Fio: bind p/ auto-captura + scanner manual (modo LER) */}
            <div className="bg-panel border border-edge rounded-card p-2 space-y-2">
              <div className="flex items-center gap-2 text-[11px]">
                <span className="text-muted">👁 Auto-captura:</span>
                <select defaultValue="" onChange={(e) => linkCam(e.target.value)}
                  className="bg-edge border border-edge rounded px-2 py-1 text-[11px] flex-1">
                  <option value="">ligar câmera…</option>
                  {saved.map((c) => <option key={c.id} value={`cam:${c.id}`}>{c.name}</option>)}
                </select>
                <button onClick={() => setScanOpen((v) => !v)}
                  className={"text-[11px] px-2 py-1 rounded-card border " + (scanOpen ? "border-accent text-accent" : "border-edge text-muted hover:border-accent")}>📷 Escanear</button>
              </div>
              {scanOpen && <StationScanner station={`fio:${t.tag.natural_key ?? tagId}`} operatorId={null} onScanned={reload} tagHint={tagId} />}
            </div>

            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="bg-panel border border-edge rounded-card p-2"><p className="text-lg font-bold">{t.kpis.lead_time_h}<span className="text-[10px] text-muted">h</span></p><p className="text-[10px] text-muted">lead time</p></div>
              <div className="bg-panel border border-edge rounded-card p-2"><p className="text-lg font-bold">{t.kpis.events}</p><p className="text-[10px] text-muted">eventos</p></div>
              <div className="bg-panel border border-edge rounded-card p-2"><p className="text-sm font-bold truncate" title={t.kpis.bottleneck ?? ""}>{t.kpis.bottleneck ?? "—"}</p><p className="text-[10px] text-muted">gargalo</p></div>
            </div>

            {/* Linhagem */}
            {(t.lineage.parents.length > 0 || t.lineage.children.length > 0) && (
              <div>
                <p className="text-[10px] uppercase tracking-wider text-muted mb-1">Linhagem</p>
                <div className="flex flex-wrap gap-1.5">
                  {t.lineage.parents.map((p) => (
                    <button key={p.parent_tag_id} onClick={() => onNav(p.parent_tag_id)}
                      className="text-[10px] px-2 py-0.5 rounded border border-edge hover:border-accent text-muted">↑ {p.parent_tag_id.split(":").slice(2, 4).join(" ")}</button>
                  ))}
                  {t.lineage.children.map((c) => (
                    <button key={c.child_tag_id} onClick={() => onNav(c.child_tag_id)}
                      className="text-[10px] px-2 py-0.5 rounded border border-edge hover:border-accent text-muted">↓ {c.child_tag_id.split(":").slice(2, 4).join(" ")}</button>
                  ))}
                </div>
              </div>
            )}

            {/* Pendências / Ocorrências */}
            {t.pendencies.length > 0 && (
              <div>
                <p className="text-[10px] uppercase tracking-wider text-nok mb-1">Pendências (bloqueiam)</p>
                {t.pendencies.map((p) => (
                  <div key={p.pending_id} className="flex items-center gap-2 text-xs bg-nok/10 border border-nok/40 rounded p-2 mb-1">
                    <span className="flex-1">⛔ {p.reason} <span className="text-muted">· {p.phase}</span></span>
                    <button onClick={() => doClearPending(p.pending_id)} className="text-[10px] px-2 py-0.5 rounded border border-nok/50 text-nok hover:bg-nok/10">limpar</button>
                  </div>
                ))}
              </div>
            )}
            {t.occurrences.filter((o) => !o.resolved_ts).length > 0 && (
              <div>
                <p className="text-[10px] uppercase tracking-wider text-warn mb-1">Ocorrências abertas</p>
                {t.occurrences.filter((o) => !o.resolved_ts).map((o) => (
                  <div key={o.occ_id} className="flex items-center gap-2 text-xs bg-warn/10 border border-warn/40 rounded p-2 mb-1">
                    <span className="flex-1">⚠ {o.kind} — {o.note}</span>
                    <button onClick={() => doResolveOcc(o.occ_id)} className="text-[10px] px-2 py-0.5 rounded border border-warn/50 text-warn hover:bg-warn/10">resolver</button>
                  </div>
                ))}
              </div>
            )}

            {/* Timeline */}
            <div>
              <p className="text-[10px] uppercase tracking-wider text-muted mb-1">Timeline (eventos)</p>
              <ol className="relative border-l border-edge ml-2 space-y-2">
                {t.timeline.map((e) => (
                  <li key={e.event_id} className="ml-3">
                    <span className="absolute -left-[5px] w-2 h-2 rounded-full bg-accent mt-1" />
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs font-semibold text-text">{e.action}</span>
                      {e.phase && <span className="text-[9px] px-1 rounded bg-edge text-muted">{e.phase}</span>}
                      {e.vision_mode && <span className="text-[9px] px-1 rounded bg-accent/15 text-accent">👁 {e.vision_mode}{e.confidence != null ? ` ${(e.confidence * 100).toFixed(0)}%` : ""}</span>}
                    </div>
                    <p className="text-[10px] text-muted">{fmtTs(e.event_ts)} · {e.domain} · {e.owner}</p>
                    {Object.keys(e.payload || {}).length > 0 && <p className="text-[10px] text-muted">{JSON.stringify(e.payload)}</p>}
                  </li>
                ))}
              </ol>
            </div>
          </>
        )}
      </div>
    </div>
  );
  return createPortal(body, document.body);
}

// ── Modal de Reconciliação ERP/MES ───────────────────────────────────
function ReconModal({ onClose, onOpenTag }: { onClose: () => void; onOpenTag: (t: string) => void }) {
  const [r, setR] = useState<Recon | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  useEffect(() => { getRecon().then(setR).catch(() => undefined); }, []);
  const reseed = async () => { setBusy(true); try { setR(await seedRecon()); setMsg("Docs de demonstração carregados."); } finally { setBusy(false); } };
  const onFile = async (f: File | null) => {
    if (!f) return;
    setBusy(true);
    try { const txt = await f.text(); const res = await importReconCsv(txt); setR(res); setMsg(`${res.ingested} documento(s) importado(s) de ${f.name}.`); }
    finally { setBusy(false); }
  };
  const clearDocs = async () => { setBusy(true); try { setR(await clearReconDocs()); setMsg("Documentos ERP removidos."); } finally { setBusy(false); } };

  return createPortal(
    <div className="fixed inset-0 z-[120] flex justify-center items-start pt-12" style={{ background: "rgba(0,0,0,0.5)" }} onClick={onClose}>
      <div className="w-full max-w-2xl bg-surface border border-edge rounded-card overflow-y-auto scroll-thin max-h-[80vh] p-4 space-y-3" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2">
          <h3 className="text-base font-bold flex-1">🔗 Reconciliação ERP/MES</h3>
          <button onClick={onClose} className="text-muted hover:text-text text-lg">✕</button>
        </div>

        {/* Conector ERP/MES: ingestão de documentos */}
        <div className="bg-panel border border-edge rounded-card p-3 space-y-2">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-muted flex-1">Conector ERP/MES — ingerir documentos ({r?.docs.length ?? 0} carregado(s))</span>
            <label className="text-xs px-2.5 py-1 rounded-card border border-accent/50 text-accent hover:bg-accent/10 cursor-pointer">
              ⬆ Importar CSV
              <input type="file" accept=".csv,text/csv" className="hidden" onChange={(e) => onFile(e.target.files?.[0] ?? null)} />
            </label>
            <button onClick={reseed} disabled={busy} className="text-xs px-2.5 py-1 rounded-card border border-edge hover:border-accent text-muted disabled:opacity-50">demo</button>
            <button onClick={clearDocs} disabled={busy} className="text-xs px-2.5 py-1 rounded-card border border-edge hover:border-nok text-muted disabled:opacity-50">limpar</button>
          </div>
          <p className="text-[10px] text-muted">CSV: <code>natural_key,doc,qty,value,status</code> — ex.: <code>OP-2026-04412,ERP-OP-77120,12,18450,OPEN</code>. (Produção: CDC SAP/HANA ou OPC UA Opcenter.)</p>
          {msg && <p className="text-[10px] text-accent">{msg}</p>}
        </div>
        {!r ? <p className="text-xs text-muted">Carregando…</p> : (
          <>
            <div className="grid grid-cols-4 gap-2 text-center">
              <div className="bg-panel border border-edge rounded-card p-2"><p className="text-xl font-bold text-text">{r.rate}%</p><p className="text-[10px] text-muted">casados</p></div>
              <div className="bg-panel border border-edge rounded-card p-2"><p className="text-xl font-bold text-ok">{r.matched}</p><p className="text-[10px] text-muted">MATCHED</p></div>
              <div className="bg-panel border border-edge rounded-card p-2"><p className="text-xl font-bold text-nok">{r.divergent}</p><p className="text-[10px] text-muted">DIVERGENT</p></div>
              <div className="bg-panel border border-edge rounded-card p-2"><p className="text-xl font-bold text-muted">{r.unmatched}</p><p className="text-[10px] text-muted">sem doc</p></div>
            </div>
            <p className="text-[10px] text-muted">VPS reconcilia e referencia — não escreve transação financeira. Divergência (visão ≠ ERP) gera ocorrência.</p>
            <div className="space-y-1">
              {r.items.map((it) => (
                <button key={it.tag_id} onClick={() => onOpenTag(it.tag_id)}
                  className="w-full flex items-center gap-2 text-xs bg-panel border border-edge rounded-card p-2 text-left hover:border-accent">
                  <span className="w-2 h-2 rounded-full shrink-0" style={{ background: RECON_COLOR[it.status] ?? "var(--muted)" }} />
                  <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-edge text-muted">{it.entity_type}</span>
                  <span className="font-medium text-text flex-1 truncate">{it.natural_key}</span>
                  <span className="text-muted">{it.erp_doc ?? "sem doc ERP"}</span>
                  <span className="font-semibold" style={{ color: RECON_COLOR[it.status] }}>{it.status}</span>
                </button>
              ))}
            </div>
          </>
        )}
      </div>
    </div>, document.body);
}

// ── Modal de Dados / BI (Gold GLX_) ──────────────────────────────────
function DataModal({ onClose }: { onClose: () => void }) {
  const [models, setModels] = useState<GoldModel[]>([]);
  useEffect(() => { getGoldModels().then((d) => setModels(d.models)).catch(() => undefined); }, []);
  return createPortal(
    <div className="fixed inset-0 z-[120] flex justify-center items-start pt-12" style={{ background: "rgba(0,0,0,0.5)" }} onClick={onClose}>
      <div className="w-full max-w-lg bg-surface border border-edge rounded-card p-4 space-y-3" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2">
          <h3 className="text-base font-bold flex-1">📊 Plataforma de Dados / BI</h3>
          <button onClick={onClose} className="text-muted hover:text-text text-lg">✕</button>
        </div>
        <p className="text-[10px] text-muted">Modelo semântico <b>GLX_</b> (camada Gold) derivado do Event Store — fatos e dimensões prontos p/ Power BI. Medidas <b>CLD_</b> nos KPIs.</p>
        <div className="space-y-1.5">
          {models.map((m) => (
            <div key={m.key} className="flex items-center gap-2 text-xs bg-panel border border-edge rounded-card p-2">
              <span className="font-mono text-[11px] flex-1 truncate" title={m.name}>{m.name}</span>
              <button onClick={() => downloadGold(m.key, m.name, "csv")} className="text-[10px] px-2 py-0.5 rounded border border-edge hover:border-accent text-muted">CSV</button>
              <button onClick={() => downloadGold(m.key, m.name, "json")} className="text-[10px] px-2 py-0.5 rounded border border-edge hover:border-accent text-muted">JSON</button>
            </div>
          ))}
        </div>
      </div>
    </div>, document.body);
}

// ── Modal de Segurança / LGPD ────────────────────────────────────────
function SecurityModal({ onClose }: { onClose: () => void }) {
  const [l, setL] = useState<Lgpd | null>(null);
  const [roles, setRoles] = useState<RolesInfo | null>(null);
  const [msg, setMsg] = useState<string>("");
  useEffect(() => { getLgpd().then(setL).catch(() => undefined); getRoles().then(setRoles).catch(() => undefined); }, []);
  const toggleBlur = async () => { if (l) setL(await setLgpd(!l.blur)); };
  const sweep = async () => { const r = await sweepLgpd(); setMsg(`Retenção: ${r.removed} arquivo(s) removido(s) (${r.freed_mb} MB).`); getLgpd().then(setL); };

  return createPortal(
    <div className="fixed inset-0 z-[120] flex justify-center items-start pt-12" style={{ background: "rgba(0,0,0,0.5)" }} onClick={onClose}>
      <div className="w-full max-w-lg bg-surface border border-edge rounded-card p-4 space-y-3" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2">
          <h3 className="text-base font-bold flex-1">🔒 Segurança & LGPD</h3>
          <button onClick={onClose} className="text-muted hover:text-text text-lg">✕</button>
        </div>

        <div className="bg-panel border border-edge rounded-card p-3 space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-sm flex-1">Anonimização (blur facial nos frames)</span>
            <button onClick={toggleBlur} disabled={!l?.blur_available}
              className={"text-xs px-3 py-1.5 rounded-card border transition-colors disabled:opacity-50 " + (l?.blur ? "border-ok/50 text-ok bg-ok/10" : "border-edge text-muted")}>
              {l?.blur ? "ON" : "OFF"}
            </button>
          </div>
          <p className="text-[10px] text-muted">{l?.blur_available ? "OpenCV Haar disponível — rostos borrados antes de persistir." : "OpenCV indisponível neste host (no-op)."}</p>
        </div>

        <div className="bg-panel border border-edge rounded-card p-3 space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-sm flex-1">Retenção de imagens: <b>{l?.retention_days ?? "—"}</b> dias</span>
            <button onClick={sweep} className="text-xs px-3 py-1.5 rounded-card border border-edge hover:border-accent text-muted">Aplicar agora</button>
          </div>
          <p className="text-[10px] text-muted">Arquivos: {l ? Object.entries(l.files).map(([k, v]) => `${k}=${v}`).join(" · ") : "—"}</p>
          {msg && <p className="text-[10px] text-accent">{msg}</p>}
        </div>

        {roles && (
          <p className="text-[10px] text-muted">RBAC: papel atual <b>{getVpsRole()}</b>. Ações de governança exigem o dono do contexto (OP→Operations, PICK→Supply, SO→Sales…) ou Admin. Viewer = só leitura.</p>
        )}
      </div>
    </div>, document.body);
}

// ── View ─────────────────────────────────────────────────────────────
export function VpsView() {
  const [board, setBoard] = useState<Board | null>(null);
  const [kpis, setKpis] = useState<Kpis | null>(null);
  const [bridge, setBridge] = useState<BridgeStatus | null>(null);
  const [sel, setSel] = useState<string | null>(null);
  const [lane, setLane] = useState("OP");
  const [reconOpen, setReconOpen] = useState(false);
  const [secOpen, setSecOpen] = useState(false);
  const [dataOpen, setDataOpen] = useState(false);
  const [labelInit, setLabelInit] = useState<Partial<LabelData> | null>(null);
  const [seeding, setSeeding] = useState(false);
  const [live, setLive] = useState(false);
  const [role, setRole] = useState(getVpsRole());
  const [roles, setRoles] = useState<string[]>(["Admin"]);
  const [segment, setSegment] = useState("PANEL");
  const [segments, setSegments] = useState<SegmentInfo[]>([]);
  const saved = useStore((s) => s.savedCameras);

  const load = useCallback(() => {
    getBoard(lane === "all" ? undefined : lane, segment).then(setBoard).catch(() => undefined);
    getKpis().then(setKpis).catch(() => undefined);
    getBridge().then(setBridge).catch(() => undefined);
  }, [lane, segment]);
  // WS é a fonte primária de frescor; poll lento como fallback.
  const loadRef = useRef(load); loadRef.current = load;
  useEffect(() => { load(); const id = window.setInterval(load, 20000); return () => window.clearInterval(id); }, [load]);
  useEffect(() => {
    const ws = connectVpsLive((evs) => { if (evs.length) { setLive(true); loadRef.current(); } });
    ws.onopen = () => setLive(true);
    ws.onclose = () => setLive(false);
    return () => ws.close();
  }, []);
  useEffect(() => { getRoles().then((r) => setRoles(r.roles)).catch(() => undefined); }, []);
  useEffect(() => { getSegments().then((d) => { setSegments(d.segments); setSegment(d.current); }).catch(() => undefined); }, []);
  const pickRole = (r: string) => { setVpsRole(r); setRole(r); };
  const pickSegment = (s: string) => { setSegment(s); setGenesisSegment(s); };  // filtra board + define gênese

  const doSeed = async () => { setSeeding(true); try { await seedVps(true); load(); } finally { setSeeding(false); } };
  const toggleAuto = async () => { if (bridge) { setBridge(await setAutoCapture(!bridge.auto_capture)); } };
  const unbind = async (src: string) => { await bindSource(src, null); load(); };
  const srcLabel = (src: string) => src.startsWith("cam:") ? (saved.find((c) => c.id === src.slice(4))?.name ?? src) : src;
  const bindings = Object.entries(bridge?.bindings ?? {});

  const cardsBy = (col: string) => (board?.cards ?? []).filter((c) => c.phase === col);
  const empty = board && board.total === 0;

  return (
    <div className="flex flex-col gap-3 min-h-full">
      {/* Header */}
      <div className="flex items-center gap-3 flex-wrap border-b border-edge pb-2">
        <h2 className="text-base font-bold flex items-center gap-2">🧵 VPS — Visual Planning System
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent/15 text-accent">Fio Dourado</span>
        </h2>
        <span className="flex items-center gap-1 text-[11px]" title={live ? "Conectado ao stream ao vivo" : "Sem conexão ao vivo"}>
          <span className={"w-1.5 h-1.5 rounded-full " + (live ? "bg-ok animate-pulse" : "bg-muted")} />
          <span className="text-muted">{live ? "ao vivo" : "—"}</span>
        </span>
        {board?.bottleneck && <span className="text-[11px] px-2 py-0.5 rounded-full bg-nok/15 text-nok">gargalo: {board.bottleneck}</span>}
        <span className="text-xs text-muted">{board?.total ?? 0} instância(s)</span>
        <select value={segment} onChange={(e) => pickSegment(e.target.value)} title="Segmento (filtra o board + define a gênese)"
          className="bg-edge border border-edge rounded px-2 py-1 text-xs ml-1">
          {segments.map((s) => <option key={s.segment} value={s.segment}>🏭 {s.segment}</option>)}
        </select>
        <div className="flex rounded-card border border-edge overflow-hidden text-xs">
          {LANES.map((l) => (
            <button key={l.key} onClick={() => setLane(l.key)}
              className={"px-2.5 py-1 transition-colors " + (lane === l.key ? "bg-accent text-onaccent" : "bg-edge text-muted hover:text-text")}>{l.label}</button>
          ))}
        </div>
        <select value={role} onChange={(e) => pickRole(e.target.value)} title="Papel (RBAC) — gate das ações de governança"
          className="bg-edge border border-edge rounded px-2 py-1 text-xs">
          {roles.map((r) => <option key={r} value={r}>👤 {r}</option>)}
        </select>
        <button onClick={() => setLabelInit({})} className="text-xs px-3 py-1.5 rounded-card border border-edge hover:border-accent text-muted">🏷 Etiqueta</button>
        <button onClick={() => setDataOpen(true)} className="text-xs px-3 py-1.5 rounded-card border border-edge hover:border-accent text-muted">📊 BI</button>
        <button onClick={() => setSecOpen(true)} className="text-xs px-3 py-1.5 rounded-card border border-edge hover:border-accent text-muted">🔒 Segurança</button>
        <button onClick={() => setReconOpen(true)} className="text-xs px-3 py-1.5 rounded-card border border-edge hover:border-accent text-muted">🔗 Reconciliação</button>
        <button onClick={toggleAuto}
          title="Gênese pela visão (LER→Tag-ID) + verificação (CONTAR/ANALISAR)"
          className={"ml-auto text-xs px-3 py-1.5 rounded-card border transition-colors " +
            (bridge?.auto_capture ? "border-ok/50 text-ok bg-ok/10" : "border-edge text-muted")}>
          👁 Visão→VPS: {bridge?.auto_capture ? "ON" : "OFF"}
        </button>
        <button onClick={doSeed} disabled={seeding}
          className="text-xs px-3 py-1.5 rounded-card border border-edge hover:border-accent text-muted disabled:opacity-50">
          {seeding ? "gerando…" : "⟳ Gerar demo"}
        </button>
      </div>

      {/* Fontes de visão ligadas a um Fio Dourado */}
      {bindings.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap text-[11px]">
          <span className="text-muted">Fontes ligadas:</span>
          {bindings.map(([src, tag]) => (
            <span key={src} className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-accent/10 border border-accent/40">
              <button onClick={() => setSel(tag)} className="text-accent hover:underline">👁 {srcLabel(src)} → {tag.split(":").slice(2, 4).join(" ")}</button>
              <button onClick={() => unbind(src)} className="text-muted hover:text-nok" title="desligar">✕</button>
            </span>
          ))}
        </div>
      )}

      {/* KPIs */}
      <div className="grid grid-cols-3 sm:grid-cols-5 gap-2">
        {KPI_DEFS.map((d) => {
          const v = kpis?.[d.key];
          const cur = kpis?.CLD_Currency ?? "";
          const txt = v == null ? "—" : d.currency ? `${cur} ${v}` : `${v}${d.suffix ?? ""}`;
          return (
            <div key={d.key} className="bg-panel border border-edge rounded-card p-2.5">
              <p className="text-[10px] uppercase tracking-wider text-muted truncate">{d.label}</p>
              <p className="text-xl font-extrabold truncate" style={{ color: d.accent }}>{txt}</p>
            </div>
          );
        })}
      </div>

      {/* Exceções */}
      {board && board.alerts.length > 0 && (
        <div className="bg-nok/5 border border-nok/30 rounded-card p-2 flex items-center gap-2 flex-wrap">
          <span className="text-xs font-semibold text-nok">⚠ Exceções:</span>
          {board.alerts.map((a) => (
            <button key={a.tag_id} onClick={() => setSel(a.tag_id)}
              className="text-[11px] px-2 py-0.5 rounded-full bg-surface border border-nok/40 hover:border-nok text-text">
              {a.natural_key} · {a.reason === "EXCEPTION" ? "bloqueado" : a.reason === "RISCO" ? "risco" : "SLA"} {a.phase}
            </button>
          ))}
        </div>
      )}

      {/* Board kanban */}
      <div className="flex-1">
        {empty ? (
          <div className="min-h-[50vh] grid place-items-center text-center">
            <div>
              <p className="text-muted text-sm mb-2">Nenhum Fio Dourado ainda. A gênese vem da visão (modo LER → Tag-ID) ou via API <code>/vps/capture</code>.</p>
              <button onClick={doSeed} className="text-xs px-3 py-1.5 rounded-card border border-accent text-accent">Gerar dados de demonstração</button>
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto scroll-thin pb-2">
            <div className="flex gap-3 items-start" style={{ minWidth: "max-content" }}>
              {(board?.columns ?? []).map((col) => {
                const cards = cardsBy(col);
                const isDone = col === "DONE";
                const isBottleneck = col === board?.bottleneck;
                return (
                  <div key={col} className="w-56 shrink-0 flex flex-col rounded-card border border-edge" style={{ background: "var(--chart-bg)" }}>
                    <div className="flex items-center gap-2 px-2.5 py-2 border-b border-edge">
                      <span className={"text-xs font-semibold " + (isDone ? "text-ok" : isBottleneck ? "text-nok" : "text-text")}>{col}</span>
                      <span className="text-[10px] text-muted ml-auto">{cards.length}</span>
                      {isBottleneck && <span className="text-[9px] text-nok">●</span>}
                    </div>
                    <div className="scroll-thin p-2 space-y-2">
                      {cards.length === 0 && <p className="text-[10px] text-muted text-center py-2">—</p>}
                      {cards.map((c) => <Card key={c.tag_id} c={c} onOpen={() => setSel(c.tag_id)} />)}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {sel && <ThreadDrawer tagId={sel} onClose={() => setSel(null)} onNav={setSel} onBound={load} onLabel={setLabelInit} />}
      {reconOpen && <ReconModal onClose={() => setReconOpen(false)} onOpenTag={(t) => { setReconOpen(false); setSel(t); }} />}
      {secOpen && <SecurityModal onClose={() => setSecOpen(false)} />}
      {dataOpen && <DataModal onClose={() => setDataOpen(false)} />}
      {labelInit && <LabelGenerator initial={labelInit} onClose={() => setLabelInit(null)} />}
    </div>
  );
}
