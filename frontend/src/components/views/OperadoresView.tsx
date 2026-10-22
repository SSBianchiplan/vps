import { useCallback, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import {
  clearPending, getBridge, getOperators, getRecentEvents, getThread, identifyOperator,
  seedOperators, setOperatorStatus, upsertOperator,
  type Operator, type Pending, type VpsEvent,
} from "../../api/vps";
import { useStore } from "../../store/useStore";
import { StationScanner } from "../vps/StationScanner";
import { DataTable, type Column } from "../ui/DataTable";

const ROLES = ["Operador", "Supervisor", "Gestor de planta", "Controladoria", "Admin", "Auditoria"];
const empty: Partial<Operator> = { name: "", matricula: "", badge: "", role: "Operador", stations: "", skills: "", shift: "", status: "ativo" };

// ── Form de cadastro (criar/editar) ──────────────────────────────────
function OperatorForm({ initial, onClose, onSaved }: { initial: Partial<Operator>; onClose: () => void; onSaved: () => void }) {
  const [d, setD] = useState<Partial<Operator>>(initial);
  const set = (k: keyof Operator, v: string) => setD((s) => ({ ...s, [k]: v }));
  const save = async () => { if (!d.name?.trim()) return; await upsertOperator(d); onSaved(); onClose(); };
  const F = (label: string, k: keyof Operator, ph = "") => (
    <label className="block text-[10px] uppercase tracking-wider text-muted">{label}
      <input value={(d[k] as string) ?? ""} onChange={(e) => set(k, e.target.value)} placeholder={ph}
        className="w-full mt-1 bg-edge border border-edge rounded px-2 py-1.5 text-sm text-text" />
    </label>
  );
  return createPortal(
    <div className="fixed inset-0 z-[120] flex justify-center items-start pt-12" style={{ background: "rgba(0,0,0,0.5)" }} onClick={onClose}>
      <div className="w-full max-w-md bg-surface border border-edge rounded-card p-4 space-y-2.5" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2"><h3 className="text-base font-bold flex-1">{initial.operator_id ? "Editar" : "Novo"} operador</h3><button onClick={onClose} className="text-muted hover:text-text text-lg">✕</button></div>
        {F("Nome", "name", "J. Silva")}
        <div className="grid grid-cols-2 gap-2">{F("Matrícula", "matricula", "M-123")}{F("Crachá (QR/NFC/PIN)", "badge", "QR-U123")}</div>
        <label className="block text-[10px] uppercase tracking-wider text-muted">Papel (RBAC)
          <select value={d.role ?? "Operador"} onChange={(e) => set("role", e.target.value)} className="w-full mt-1 bg-edge border border-edge rounded px-2 py-1.5 text-sm text-text">
            {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </label>
        {F("Estações habilitadas (csv)", "stations", "ALMOX-02,LINHA-01")}
        <div className="grid grid-cols-2 gap-2">{F("Skills (csv)", "skills", "picking,montagem")}{F("Turno", "shift", "T1")}</div>
        <button onClick={save} disabled={!d.name?.trim()} className="w-full text-sm px-3 py-2 rounded-card border border-accent text-accent hover:bg-accent/10 disabled:opacity-50">Salvar</button>
      </div>
    </div>, document.body);
}

// ── Aba Cadastro ─────────────────────────────────────────────────────
function Cadastro() {
  const [ops, setOps] = useState<Operator[]>([]);
  const [status, setStatus] = useState("ativo");
  const [edit, setEdit] = useState<Partial<Operator> | null>(null);
  const load = useCallback(() => { getOperators(status === "todos" ? undefined : status).then((d) => setOps(d.operators)).catch(() => undefined); }, [status]);
  useEffect(() => { load(); }, [load]);
  const toggle = async (o: Operator) => { await setOperatorStatus(o.operator_id, o.status === "ativo" ? "inativo" : "ativo"); load(); };

  const cols: Column<Operator>[] = [
    { key: "matricula", header: "Matríc.", className: "font-mono text-text", render: (o) => o.matricula ?? "—" },
    { key: "name", header: "Nome", className: "font-medium text-text" },
    { key: "role", header: "Papel" },
    { key: "stations", header: "Estações", render: (o) => o.stations || "—" },
    { key: "skills", header: "Skills", render: (o) => o.skills || "—" },
    { key: "status", header: "●", align: "center", render: (o) => <span className={"inline-block w-2 h-2 rounded-full " + (o.status === "ativo" ? "bg-ok" : "bg-muted")} /> },
    { key: "_acoes", header: "Ações", align: "right", sortable: false, render: (o) => (
      <span className="whitespace-nowrap">
        <button onClick={() => setEdit(o)} className="text-[10px] px-2 py-0.5 rounded border border-edge text-muted hover:border-accent mr-1">editar</button>
        <button onClick={() => toggle(o)} className="text-[10px] px-2 py-0.5 rounded border border-edge text-muted hover:border-accent">{o.status === "ativo" ? "inativar" : "ativar"}</button>
      </span>
    ) },
  ];

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 flex-wrap text-xs">
        <span className="text-muted uppercase tracking-wider">Status</span>
        {["ativo", "inativo", "todos"].map((s) => (
          <button key={s} onClick={() => setStatus(s)} className={"px-2.5 py-1 rounded-card border " + (status === s ? "border-accent text-accent" : "border-edge text-muted")}>{s}</button>
        ))}
        <button onClick={() => setEdit(empty)} className="ml-auto px-3 py-1.5 rounded-card border border-accent text-accent hover:bg-accent/10">+ Novo</button>
        <button onClick={async () => { await seedOperators(); load(); }} className="px-3 py-1.5 rounded-card border border-edge text-muted hover:border-accent">demo</button>
      </div>
      <DataTable columns={cols} rows={ops} getKey={(o) => o.operator_id} pageSize={8}
        empty='Nenhum operador. Use "demo" ou "+ Novo".' />
      <p className="text-[10px] text-muted">Master data SCD2: inativar preserva histórico (nunca apaga). Papel mapeia ao RBAC do VPS. <span className="text-accent">Tabela dinâmica (Onda 4): busca · ordenação · paginação.</span></p>
      {edit && <OperatorForm initial={edit} onClose={() => setEdit(null)} onSaved={load} />}
    </div>
  );
}

// ── Aba Estação (modal do operador §2.4) ─────────────────────────────
function Estacao() {
  const saved = useStore((s) => s.savedCameras);
  const [ops, setOps] = useState<Operator[]>([]);
  const [station, setStation] = useState("ALMOX-02");
  const [opId, setOpId] = useState<string | null>(null);
  const [last, setLast] = useState<VpsEvent | null>(null);
  const [pend, setPend] = useState<Pending[]>([]);

  const stations = Array.from(new Set(["ALMOX-02", "LINHA-01", ...saved.map((c) => `cam:${c.id}`)]));
  useEffect(() => { getOperators("ativo").then((d) => setOps(d.operators)).catch(() => undefined); }, []);

  const refresh = useCallback(async () => {
    const b = await getBridge().catch(() => null);
    setOpId((await getOperators().catch(() => ({ sessions: {} as Record<string, string> }))).sessions[station] ?? null);
    const evs = await getRecentEvents(80).catch(() => ({ events: [] as VpsEvent[] }));
    setLast(evs.events.find((e) => e.station_id === station || e.source_type === station) ?? null);
    const tag = b?.bindings?.[station];
    setPend(tag ? (await getThread(tag).catch(() => null))?.pendencies ?? [] : []);
  }, [station]);
  useEffect(() => { refresh(); const id = window.setInterval(refresh, 5000); return () => window.clearInterval(id); }, [refresh]);

  const identify = async (oid: string) => { await identifyOperator(station, oid ? { operator_id: oid } : {}); refresh(); };
  const resolve = async (id: string) => { await clearPending(id).catch(() => undefined); refresh(); };

  return (
    <div className="max-w-sm mx-auto">
      <div className="bg-panel border border-edge rounded-card overflow-hidden">
        {/* cabeçalho: estação + operador */}
        <div className="flex items-center gap-2 px-3 py-2.5 bg-edge/50 border-b border-edge">
          <span className="font-bold text-sm">▌VPS</span>
          <select value={station} onChange={(e) => setStation(e.target.value)} className="bg-edge border border-edge rounded px-2 py-1 text-xs">
            {stations.map((s) => <option key={s} value={s}>ESTAÇÃO {s}</option>)}
          </select>
          <span className="ml-auto text-xs">👤 {opId ?? "—"}</span>
        </div>
        <div className="p-4 space-y-3">
          {/* login do operador */}
          <div className="flex items-center gap-2">
            <select value={opId ?? ""} onChange={(e) => identify(e.target.value)} className="flex-1 bg-edge border border-edge rounded px-2 py-1.5 text-sm">
              <option value="">— identificar operador —</option>
              {ops.map((o) => <option key={o.operator_id} value={o.operator_id}>{o.name} ({o.operator_id})</option>)}
            </select>
          </div>
          {/* ação primária — scanner funcional (local/mobile/IP/Osmo/drone) */}
          <StationScanner station={station} operatorId={opId} onScanned={refresh} />
          {/* última leitura */}
          <div>
            <p className="text-[10px] uppercase tracking-wider text-muted mb-1">Última leitura</p>
            {last ? (
              <div className="text-xs bg-surface border border-edge rounded p-2">
                <span className="font-mono">{last.tag_id.split(":").slice(2, 4).join(" ")}</span> · {last.phase ?? last.action}
                {last.vision_mode && <span className="ml-1 text-accent">👁{last.vision_mode}</span>}
              </div>
            ) : <p className="text-xs text-muted">sem leitura recente nesta estação</p>}
          </div>
          {/* exceções da estação */}
          <div>
            <p className="text-[10px] uppercase tracking-wider text-nok mb-1">Pendências da estação</p>
            {pend.length === 0 ? <p className="text-xs text-muted">nenhuma pendência ativa</p> : pend.map((p) => (
              <div key={p.pending_id} className="flex items-center gap-2 text-xs bg-nok/10 border border-nok/40 rounded p-2 mb-1">
                <span className="flex-1">⚠ {p.reason}</span>
                <button onClick={() => resolve(p.pending_id)} className="text-[10px] px-2 py-0.5 rounded border border-nok/50 text-nok">Resolver</button>
              </div>
            ))}
          </div>
        </div>
      </div>
      <p className="text-[10px] text-muted mt-2 text-center">Modal do operador: 1 ação primária, feedback imediato, exceções acionáveis. Toda ação carimba o operator_id (P05).</p>
    </div>
  );
}

export function OperadoresView() {
  const [tab, setTab] = useState<"cadastro" | "estacao">("cadastro");
  return (
    <div className="flex flex-col gap-3 min-h-full">
      <div className="flex items-center gap-3 flex-wrap border-b border-edge pb-2">
        <h2 className="text-base font-bold flex items-center gap-2">👷 Operadores
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent/15 text-accent">gente & master data</span>
        </h2>
        <div className="ml-auto flex gap-1">
          {([["cadastro", "Cadastro"], ["estacao", "Estação (operador)"]] as const).map(([k, l]) => (
            <button key={k} onClick={() => setTab(k)} className={"px-3 py-1.5 text-sm rounded-card border-b-2 " + (tab === k ? "border-accent text-accent" : "border-transparent text-muted hover:text-text")}>{l}</button>
          ))}
        </div>
      </div>
      <div className="flex-1 scroll-thin pr-1">
        {tab === "cadastro" ? <Cadastro /> : <Estacao />}
      </div>
    </div>
  );
}
