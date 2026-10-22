import { useEffect, useState } from "react";
import { useStore } from "../store/useStore";
import type { View } from "../store/useStore";

interface NavItem {
  key: View;
  icon: string;
  label: string;
  desc: string;
}

// Menu agrupado (IA do VPS_Menu_Navegacao_Escalavel.md): Home + 6 grupos funcionais,
// cada item VINCULADO à view existente. Estável na forma, escalável no conteúdo.
interface NavGroup { group: string; icon: string; items: NavItem[] }
const GROUPS: NavGroup[] = [
  { group: "", icon: "🏠", items: [
    { key: "painel", icon: "🏠", label: "Home", desc: "Visão geral · KPIs do dia" },
  ] },
  { group: "Operações", icon: "👁", items: [
    { key: "monitor", icon: "📶", label: "Monitoramento", desc: "Sinal IoT · board ao vivo" },
    { key: "cameras", icon: "📷", label: "Câmeras", desc: "Dispositivos & estações" },
    { key: "captura", icon: "🖥", label: "Captura de Tela", desc: "Tela como câmera (ERP/SCADA)" },
    { key: "automacao", icon: "🏭", label: "Automação Industrial", desc: "PLC/IHM · OPC UA · OEE (read-only)" },
    { key: "aerea", icon: "🛸", label: "Drone", desc: "Visão aérea (RTMP)" },
    { key: "osmo", icon: "🎥", label: "Vídeos", desc: "Osmo · evidências" },
  ] },
  { group: "IA", icon: "🧠", items: [
    { key: "iamac", icon: "🧠", label: "iaMAC (Copiloto)", desc: "RAG + flywheel · IA do VPS (MLX)" },
    { key: "estudio", icon: "🎛", label: "Análise CV", desc: "LER/CONTAR/DESCREVER/ANALISAR" },
    { key: "industria", icon: "🏭", label: "Modelos", desc: "Modelos CV industriais" },
    { key: "estudocaso", icon: "🧪", label: "Casos de Uso", desc: "Aplicado por segmento" },
    { key: "acoes", icon: "⚡", label: "Ações", desc: "AGIR / M5 (automação)" },
  ] },
  { group: "Analytics", icon: "📈", items: [
    { key: "vps", icon: "🧵", label: "VPS Visual Planning System", desc: "Cockpit · Fio Dourado (M6)" },
    { key: "eventos", icon: "🔔", label: "Eventos", desc: "Event Store · linha do tempo" },
    { key: "modais", icon: "📋", label: "Modais & Vínculos", desc: "Dado vinculado a dado" },
    { key: "downloads", icon: "⬇", label: "Downloads", desc: "Exports · gravações" },
  ] },
  { group: "Planejamento", icon: "📅", items: [
    { key: "planejamento", icon: "🗂", label: "Visual Planning", desc: "Projetos & cards" },
    { key: "aps", icon: "📅", label: "APS", desc: "Sequenciamento (capacidade finita)" },
  ] },
  { group: "Ativos", icon: "🏭", items: [
    { key: "operadores", icon: "👷", label: "Operadores", desc: "Gente · papéis · skills" },
    { key: "face", icon: "🙂", label: "Reconhecimento Facial", desc: "Login por face · biometria (LGPD)" },
    { key: "termografia", icon: "🌡", label: "Termografia", desc: "Preditiva · hotspot/ΔT/tendência" },
    { key: "metrologia", icon: "📏", label: "Metrologia", desc: "Medição dimensional · tolerância/Cpk" },
    { key: "matriz", icon: "📐", label: "Câmeras & Tokens", desc: "Matriz de dispositivos" },
    { key: "bases", icon: "🗄", label: "Bases", desc: "Schemas · dados · snapshot" },
  ] },
  { group: "Administração", icon: "⚙", items: [
    { key: "acesso", icon: "🔐", label: "Acesso & Regras", desc: "Usuários · papéis · FaceID" },
    { key: "seguranca", icon: "🛡", label: "Cibersegurança", desc: "Postura NIST · IEC 62443 · LGPD · integridade" },
    { key: "e2e", icon: "🧪", label: "Testes", desc: "E2E · demo do sistema" },
    { key: "manual", icon: "📖", label: "Manual", desc: "Admin & usuário" },
  ] },
];

// Visibilidade por RBAC (matriz §5): default Admin vê tudo; Viewer = leitura.
// RBAC: view = leitura; operador = tudo menos administração/config; admin = tudo.
const VIEW_KEYS = new Set<View>(["painel", "vps", "eventos", "modais", "downloads", "manual", "iamac"]);
const OPERADOR_DENY = new Set<View>(["acesso", "bases", "seguranca"]);
function canSee(role: string, key: View): boolean {
  if (role === "admin") return true;
  if (role === "operador") return !OPERADOR_DENY.has(key);
  return VIEW_KEYS.has(key);  // view
}

export function NavRail() {
  const view = useStore((s) => s.view);
  const setView = useStore((s) => s.setView);
  const setAparenciaOpen = useStore((s) => s.setAparenciaOpen);
  const connected = useStore((s) => s.connected);
  const role = useStore((s) => s.auth?.role) ?? "view";   // papel real da sessão (RBAC)
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem("vd-nav-collapsed") === "1"; } catch { return false; }
  });
  const toggle = () => setCollapsed((v) => {
    const nv = !v;
    try { localStorage.setItem("vd-nav-collapsed", nv ? "1" : "0"); } catch { /* ignore */ }
    return nv;
  });

  // Grupos recolhíveis (accordion) — abre RECOLHIDO por padrão; preferência persistida.
  const [closedGroups, setClosedGroups] = useState<Record<string, boolean>>(() => {
    try {
      const saved = localStorage.getItem("vd-nav-groups");
      if (saved) return JSON.parse(saved);
    } catch { /* ignore */ }
    return Object.fromEntries(GROUPS.filter((g) => g.group).map((g) => [g.group, true]));  // default: todos recolhidos
  });
  const toggleGroup = (g: string) => setClosedGroups((s) => {
    const nv = { ...s, [g]: !s[g] };
    try { localStorage.setItem("vd-nav-groups", JSON.stringify(nv)); } catch { /* ignore */ }
    return nv;
  });

  // Auto-recolhe em telas pequenas (mobile/tablet).
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 820px)");
    const apply = () => { if (mq.matches) setCollapsed(true); };
    apply();
    mq.addEventListener?.("change", apply);
    return () => mq.removeEventListener?.("change", apply);
  }, []);

  return (
    <nav
      className={"shrink-0 border-r border-edge flex flex-col py-3 gap-1 text-white/90 transition-[width] duration-200 " + (collapsed ? "px-2 items-center" : "px-2")}
      style={{ background: "var(--nav-bg)", width: collapsed ? "60px" : "var(--nav-width)" }}
    >
      <div className={"mb-3 shrink-0 select-none flex " + (collapsed ? "flex-col items-center gap-1" : "items-center gap-2 px-2")}>
        <span className={"text-accent font-black tracking-tight shrink-0 " + (collapsed ? "text-sm" : "text-xl")}>VD+V</span>
        {!collapsed && (
          <span className="flex-1 min-w-0 leading-tight">
            <span className="block font-bold tracking-tight text-white truncate">
              Vision<span className="text-accent">Desk</span> + <span className="text-accent">VPS</span>
            </span>
            <span className="block text-[9px] text-white/40 truncate">Visual Planning System</span>
          </span>
        )}
        <button
          onClick={toggle}
          title={collapsed ? "Expandir menu" : "Recolher menu"}
          className="vd-keep w-6 h-6 flex items-center justify-center rounded-card text-white/60 hover:text-white hover:bg-white/10 text-base transition-colors"
        >
          {collapsed ? "›" : "‹"}
        </button>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto scroll-thin flex flex-col gap-0.5">
      {GROUPS.map((g) => {
        const items = g.items.filter((it) => canSee(role, it.key));  // RBAC por papel
        if (!items.length) return null;
        const open = collapsed || !g.group || !closedGroups[g.group];  // accordion só no modo expandido
        return (
          <div key={g.group || "home"} className="flex flex-col gap-0.5">
            {g.group && (collapsed
              ? <div className="my-1 mx-auto w-6 border-t border-white/10" title={g.group} />
              : <button onClick={() => toggleGroup(g.group)}
                  className="w-full flex items-center gap-1.5 px-2 pt-2 pb-0.5 text-[9px] uppercase tracking-[0.12em] text-white/30 hover:text-white/60 transition-colors">
                  <span>{g.icon}</span><span className="flex-1 text-left">{g.group}</span>
                  <span className="text-[8px]">{open ? "▾" : "▸"}</span>
                </button>)}
            {open && items.map((it) => {
              const active = view === it.key;
              return (
                <button
                  key={it.key}
                  onClick={() => setView(it.key)}
                  title={`${g.group ? g.group + " · " : ""}${it.label} — ${it.desc}`}
                  className={
                    "vd-keep w-full flex items-center rounded-card transition-colors text-left " +
                    (collapsed ? "justify-center px-0 py-2.5" : "gap-3 px-3 py-2") + " " +
                    (active ? "bg-white/15 text-white" : "text-white/60 hover:text-white hover:bg-white/10")
                  }
                >
                  <span className="text-lg leading-none w-5 text-center shrink-0">{it.icon}</span>
                  {!collapsed && (
                    <span className="min-w-0">
                      <span className="block text-sm leading-tight truncate">{it.label}</span>
                      <span className="block text-[10px] leading-tight text-white/40 truncate">{it.desc}</span>
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        );
      })}
      </div>

      <div className={"mt-auto shrink-0 flex items-center pt-3 " + (collapsed ? "flex-col gap-2" : "gap-2 px-3")}>
        <span
          className={"w-2 h-2 rounded-full " + (connected ? "bg-ok" : "bg-nok")}
          title={connected ? "Backend conectado" : "Backend desconectado"}
        />
        {!collapsed && (
          <span className="text-[10px] text-white/40 flex-1 truncate">{connected ? "conectado" : "offline"}</span>
        )}
        <button
          onClick={() => setAparenciaOpen(true)}
          title="Aparência"
          className="vd-keep text-white/60 hover:text-white text-lg transition-colors"
        >
          ⚙
        </button>
      </div>
    </nav>
  );
}
