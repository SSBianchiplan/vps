import { useState, type ReactNode } from "react";
import type { UiComponent } from "../api/appconfig";
import { btnCls, btnPrimaryCls, inputCls, selectCls } from "../lib/ui";
import { DataTable } from "./ui/DataTable";
import { Card } from "./ui/Card";
import { BarChart } from "./ui/Chart";
import { Modal } from "./ui/Modal";
import { Drawer } from "./ui/Drawer";
import { Carousel } from "./ui/Carousel";
import { Timeline } from "./ui/Timeline";
import { VirtualList } from "./ui/VirtualList";
import { ToastHost, useToast, type ToastKind } from "./ui/Toast";
import { Autocomplete } from "./ui/Autocomplete";
import { TagInput } from "./ui/TagInput";
import { DateRange } from "./ui/DateRange";
import { MaskedInput, MASKS } from "./ui/MaskedInput";
import { RichText } from "./ui/RichText";
import { DropZone } from "./ui/DropZone";
import { Breadcrumbs } from "./ui/Breadcrumbs";
import { TreeView } from "./ui/TreeView";
import { Accordion } from "./ui/Accordion";
import { Stepper } from "./ui/Stepper";
import { ContextMenu } from "./ui/ContextMenu";
import { Fab } from "./ui/Fab";
import { MegaMenu } from "./ui/MegaMenu";
import { SystemBanner } from "./ui/SystemBanner";
import { Skeleton } from "./ui/Skeleton";
import { Tour } from "./ui/Tour";

// ── Demos com estado próprio ──
const Toggle = () => { const [on, setOn] = useState(true); return <button onClick={() => setOn((o) => !o)} className={"w-10 h-6 rounded-full relative transition-colors " + (on ? "bg-accent" : "bg-edge")}><span className={"absolute top-0.5 w-5 h-5 rounded-full bg-white transition-all " + (on ? "left-[18px]" : "left-0.5")} /></button>; };
const Tabs = () => { const [t, setT] = useState(0); const x = ["Aba A", "Aba B", "Aba C"]; return <div className="w-full"><div className="flex gap-1 border-b border-edge">{x.map((l, i) => <button key={i} onClick={() => setT(i)} className={"px-2 py-1 text-xs border-b-2 -mb-px " + (t === i ? "border-accent text-accent" : "border-transparent text-muted")}>{l}</button>)}</div><div className="text-xs text-muted pt-1.5">conteúdo {x[t]}</div></div>; };
const Hamburger = () => { const [o, setO] = useState(false); return <div className="relative"><button onClick={() => setO((v) => !v)} className="w-8 h-8 rounded border border-edge bg-edge">☰</button>{o && <ul className="absolute mt-1 vd-surface border border-edge rounded-card py-1 text-xs z-20 min-w-[110px]">{["Início", "Câmeras", "Sair"].map((l) => <li key={l} onClick={() => setO(false)} className="px-3 py-1 hover:bg-edge cursor-pointer">{l}</li>)}</ul>}</div>; };
const DAuto = () => { const [v, setV] = useState(""); return <Autocomplete options={["Portaria", "Pátio", "Doca", "Linha 01", "INJ-07"]} value={v} onChange={setV} placeholder="filtrar…" />; };
const DTags = () => { const [t, setT] = useState(["pessoa", "veículo"]); return <TagInput value={t} onChange={setT} suggestions={["capacete", "caixa", "empilhadeira"]} />; };
const DRange = () => { const [d, setD] = useState({ s: "", e: "" }); return <DateRange start={d.s} end={d.e} onChange={(s, e) => setD({ s, e })} />; };
const DMask = () => { const [v, setV] = useState(""); return <MaskedInput mask={MASKS.cpf} value={v} onChange={setV} />; };
const DStep = () => { const [i, setI] = useState(1); return <div className="w-full"><Stepper steps={["A", "B", "C", "D"]} current={i} onStep={setI} /></div>; };
const DRich = () => { const [v, setV] = useState("<b>Texto</b> rico"); return <div className="w-full"><RichText value={v} onChange={setV} /></div>; };
const DDrop = () => { const [n, setN] = useState(0); return <div className="w-full"><DropZone hint="solte arquivos" onFiles={(f) => setN(f.length)} />{n > 0 && <p className="text-[10px] text-muted mt-1">{n} arquivo(s)</p>}</div>; };
const DModal = () => { const [o, setO] = useState(false); return <><button className={btnCls} onClick={() => setO(true)}>Abrir modal</button><Modal open={o} onClose={() => setO(false)} title="Janela modal" footer={<button className={btnCls} onClick={() => setO(false)}>OK</button>}><p className="text-sm text-muted">Conteúdo do modal — bloqueia até resposta.</p></Modal></>; };
const DDrawer = () => { const [o, setO] = useState(false); return <><button className={btnCls} onClick={() => setO(true)}>Abrir gaveta</button><Drawer open={o} onClose={() => setO(false)} title="Painel gaveta"><p className="text-sm text-muted">Desliza da lateral.</p></Drawer></>; };
const DTour = () => { const [o, setO] = useState(false); return <><button className={btnCls} onClick={() => setO(true)}>Iniciar tour</button><Tour open={o} onClose={() => setO(false)} steps={[{ title: "Bem-vindo", body: "Tour guiado da plataforma." }, { title: "Câmeras", body: "Gerencie seus dispositivos aqui." }]} /></>; };
const Tip = () => <span className="relative group inline-block"><span className="text-sm underline decoration-dotted cursor-help">passe o mouse</span><span className="absolute left-0 -top-7 hidden group-hover:block vd-surface border border-edge text-[10px] px-1.5 py-0.5 rounded whitespace-nowrap">dica explicativa</span></span>;

// ── Modelo por componente ──
const MODEL: Record<string, (push: (m: string, k?: ToastKind) => void) => ReactNode> = {
  button: () => <div className="flex gap-2"><button className={btnPrimaryCls}>Primário</button><button className={btnCls}>Secundário</button></div>,
  "text-input": () => <input className={inputCls} placeholder="entrada de texto" />,
  textarea: () => <textarea className={inputCls} rows={2} placeholder="múltiplas linhas" />,
  select: () => <select className={selectCls}><option>Opção A</option><option>Opção B</option></select>,
  checkbox: () => <label className="text-sm flex items-center gap-1.5"><input type="checkbox" defaultChecked /> aceito os termos</label>,
  radio: () => <div className="flex gap-3 text-sm">{["Sim", "Não"].map((x) => <label key={x} className="flex items-center gap-1"><input type="radio" name="g-radio" defaultChecked={x === "Sim"} /> {x}</label>)}</div>,
  toggle: () => <Toggle />,
  slider: () => <input type="range" defaultValue={60} className="w-full accent-[var(--accent)]" />,
  "file-input": () => <input type="file" className="text-xs text-muted" />,
  link: () => <a className="text-accent underline cursor-pointer">Hiperlink →</a>,
  navbar: () => <div className="w-full flex items-center gap-3 bg-edge rounded px-2 py-1 text-xs"><span className="font-bold text-accent">VD</span><span className="text-muted">Início</span><span className="text-muted">Câmeras</span><span className="ml-auto">👤</span></div>,
  hamburger: () => <Hamburger />,
  tabs: () => <Tabs />,
  footer: () => <div className="w-full text-center text-[10px] text-muted border-t border-edge pt-1.5">© VisionDesk · termos · suporte</div>,
  icon: () => <div className="flex gap-2 text-lg">📷 📊 ⚙️ 🔔 👁</div>,
  label: () => <span className="text-xs font-medium text-muted">Rótulo do campo</span>,
  tooltip: () => <Tip />,
  avatar: () => <div className="flex items-center gap-2"><span className="w-8 h-8 rounded-full bg-accent text-onaccent flex items-center justify-center text-xs font-bold">SB</span><span className="w-8 h-8 rounded-full bg-edge flex items-center justify-center">👤</span></div>,
  spinner: () => <span className="inline-block w-6 h-6 border-2 border-edge border-t-accent rounded-full animate-spin" />,
  progress: () => <div className="w-full"><div className="h-2 bg-edge rounded overflow-hidden"><div className="h-full bg-accent" style={{ width: "65%" }} /></div><span className="text-[10px] text-muted">65%</span></div>,
  badge: () => <button className="relative px-2 py-1 rounded border border-edge text-lg">🔔<span className="absolute -top-1 -right-1 bg-nok text-white text-[9px] rounded-full w-4 h-4 flex items-center justify-center">3</span></button>,
  autocomplete: () => <DAuto />,
  "tag-input": () => <DTags />,
  "date-range": () => <DRange />,
  "masked-input": () => <DMask />,
  "rich-text": () => <DRich />,
  dropzone: () => <DDrop />,
  breadcrumbs: () => <Breadcrumbs items={[{ label: "Operações" }, { label: "Câmeras" }, { label: "Portaria" }]} />,
  "tree-view": () => <div className="w-full text-left"><TreeView data={[{ id: "1", label: "Planta", children: [{ id: "1a", label: "Linha 01", children: [{ id: "1a1", label: "Câmera", icon: "📷" }] }, { id: "1b", label: "Pátio", icon: "📁" }] }]} /></div>,
  "context-menu": () => <ContextMenu items={[{ label: "Abrir", icon: "📂" }, { label: "Renomear", icon: "✏️" }, { label: "Excluir", icon: "🗑", danger: true }]}><div className="w-full text-center text-xs text-muted border border-dashed border-edge rounded py-3 cursor-context-menu">clique direito aqui</div></ContextMenu>,
  accordion: () => <div className="w-full"><Accordion items={[{ title: "Seção 1", content: "conteúdo da seção 1" }, { title: "Seção 2", content: "conteúdo da seção 2" }]} /></div>,
  stepper: () => <DStep />,
  fab: () => <div className="relative w-full h-24 border border-dashed border-edge rounded"><Fab fixed={false} actions={[{ icon: "📷", label: "câmera", onClick: () => undefined }, { icon: "➕", label: "novo", onClick: () => undefined }]} /></div>,
  "mega-menu": () => <MegaMenu label="Produtos" columns={[{ title: "Visão", links: [{ label: "Câmeras", icon: "📷" }, { label: "Estúdio", icon: "🎬" }] }, { title: "Dados", links: [{ label: "Eventos", icon: "📊" }, { label: "Bases", icon: "🗄" }] }]} />,
  "data-table": () => <div className="w-full"><DataTable searchable={false} pageSize={3} columns={[{ key: "id", header: "ID", className: "font-mono text-text" }, { key: "nome", header: "Nome", className: "text-text" }, { key: "st", header: "Status" }]} rows={[{ id: "01", nome: "Portaria", st: "online" }, { id: "02", nome: "Pátio", st: "online" }, { id: "03", nome: "Doca", st: "offline" }]} /></div>,
  card: () => <div className="w-full"><Card title="Cartão" subtitle="exemplo" footer="rodapé"><span className="text-xl font-bold text-accent">128</span></Card></div>,
  "virtual-list": () => <div className="w-full"><VirtualList items={Array.from({ length: 200 }, (_, i) => i)} height={92} render={(n) => <span className="font-mono text-muted">item #{String(n).padStart(3, "0")}</span>} /></div>,
  carousel: () => <div className="w-full"><Carousel height={70}><div className="h-full grid place-items-center bg-accent/10 text-accent font-bold">Banner 1</div><div className="h-full grid place-items-center bg-ok/10 text-ok font-bold">Banner 2</div><div className="h-full grid place-items-center bg-accent-2/10 text-accent-2 font-bold">Banner 3</div></Carousel></div>,
  charts: () => <div className="w-full"><BarChart data={[{ label: "S", value: 8 }, { label: "T", value: 14 }, { label: "Q", value: 6 }, { label: "Q", value: 18 }, { label: "S", value: 11 }]} height={72} /></div>,
  timeline: () => <Timeline items={[{ time: "08:12", title: "Online" }, { time: "09:40", title: "Detecção", color: "#f0a020" }]} />,
  modal: () => <DModal />,
  drawer: () => <DDrawer />,
  toast: (push) => <button className={btnCls} onClick={() => push("Toast de exemplo ✓", "ok")}>Disparar toast</button>,
  "system-banner": () => <div className="w-full"><SystemBanner kind="warn" message="Licença expira em 3 dias." action={{ label: "Renovar", onClick: () => undefined }} /></div>,
  skeleton: () => <div className="w-full"><Skeleton lines={3} avatar /></div>,
  tour: () => <DTour />,
};

// Tooltip: COMO/QUANDO usar cada componente.
const DESC: Record<string, string> = {
  button: "Use para disparar uma ação (salvar, enviar, confirmar).",
  "text-input": "Use para um valor curto de 1 linha (nome, IP, tag).",
  textarea: "Use para texto longo/multilinha (observações, descrição).",
  select: "Use para escolher 1 opção de uma lista curta.",
  checkbox: "Use para opções independentes ou ligar/desligar (sim/não).",
  radio: "Use para escolher 1 entre poucas opções exclusivas.",
  toggle: "Use para alternar estado on/off com efeito imediato.",
  slider: "Use para ajustar valor contínuo numa faixa (limiar, volume).",
  "file-input": "Use para enviar 1 arquivo do dispositivo.",
  link: "Use para navegar/redirecionar (ação não destrutiva).",
  navbar: "Use para a navegação principal sempre visível.",
  hamburger: "Use para esconder a navegação em telas estreitas.",
  tabs: "Use para alternar vistas relacionadas sem trocar de tela.",
  footer: "Use para links secundários/estruturais no rodapé.",
  icon: "Use para reforçar a ação/estado (sempre com rótulo).",
  label: "Use para identificar o campo (acessibilidade).",
  tooltip: "Use para explicar um elemento no hover sem poluir a tela.",
  avatar: "Use para identificar usuário/origem (foto ou iniciais).",
  spinner: "Use para espera curta de duração desconhecida.",
  progress: "Use para progresso de tarefa com fim conhecido (%).",
  badge: "Use para sinalizar contagem/novidade sobre um ícone.",
  autocomplete: "Use quando a lista é grande: filtra ao digitar.",
  "tag-input": "Use para inserir vários termos/rótulos (filtros, skills).",
  "date-range": "Use para filtrar por período (início → fim).",
  "masked-input": "Use para entrada padronizada (CPF, telefone, CEP).",
  "rich-text": "Use para texto formatado (relatórios, notas).",
  dropzone: "Use para upload de vários arquivos arrastando.",
  breadcrumbs: "Use para mostrar e voltar na hierarquia de navegação.",
  "tree-view": "Use para navegar estruturas aninhadas (plantas, pastas).",
  "context-menu": "Use para ações contextuais no clique direito do item.",
  accordion: "Use para condensar seções longas, expandindo sob demanda.",
  stepper: "Use para guiar um processo em etapas (cadastro, checkout).",
  fab: "Use para a ação principal recorrente da tela (mobile).",
  "mega-menu": "Use para navegação ampla com muitas categorias.",
  "data-table": "Use para listas densas com ordenar/filtrar/paginar.",
  card: "Use para resumir um objeto com ações (câmera, KPI).",
  "virtual-list": "Use para listas enormes sem perder desempenho.",
  carousel: "Use para alternar banners/cartões no mesmo espaço.",
  charts: "Use para visualizar métricas e tendências.",
  timeline: "Use para histórico cronológico de eventos.",
  modal: "Use para decisão/edição que exige foco e resposta.",
  drawer: "Use para formulário/detalhe lateral sem sair da tela.",
  toast: "Use para confirmar ação rápida sem interromper.",
  "system-banner": "Use para aviso global persistente (licença, manutenção).",
  skeleton: "Use no carregamento para preservar o layout.",
  tour: "Use para ensinar a interface a novos usuários.",
};

export function ComponentGallery({ components }: { components: UiComponent[] }) {
  const toast = useToast();
  const withModel = components.filter((c) => MODEL[c.id]);
  const waves = Array.from(new Set(withModel.map((c) => c.wave))).sort((a, b) => a - b);
  return (
    <div className="space-y-5">
      {waves.map((w) => {
        const list = withModel.filter((c) => c.wave === w);
        return (
          <div key={w}>
            <div className="flex items-center gap-2 mb-2">
              <h4 className="text-[11px] uppercase tracking-wider text-muted">Onda {w}</h4>
              <span className="text-[10px] text-muted">{list.length} modelo(s)</span>
              <div className="flex-1 h-px bg-edge" />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {list.map((c) => (
                <figure key={c.id} className="vd-surface border border-edge rounded-card p-3 flex flex-col gap-2">
                  <figcaption className="flex items-center gap-1.5">
                    <span className="text-xs font-medium text-text truncate">{c.name}</span>
                    <span className="relative group inline-flex shrink-0">
                      <span className="w-3.5 h-3.5 rounded-full border border-muted/50 text-muted text-[9px] leading-none flex items-center justify-center cursor-help" title={DESC[c.id] ?? c.en}>i</span>
                      <span className="pointer-events-none absolute left-1/2 -translate-x-1/2 bottom-full mb-1 hidden group-hover:block z-[60] w-48 vd-surface border border-edge rounded-card px-2 py-1 text-[10px] text-text shadow-lg whitespace-normal text-left leading-snug">
                        {DESC[c.id] ?? c.en}
                      </span>
                    </span>
                    <span className={"ml-auto text-[8px] px-1 py-0.5 rounded-full " + (c.tier === "basico" ? "bg-accent-2/20 text-accent-2" : "bg-accent/15 text-accent")}>{c.tier}</span>
                  </figcaption>
                  <div className="min-h-[56px] flex items-center">{MODEL[c.id](toast.push)}</div>
                </figure>
              ))}
            </div>
          </div>
        );
      })}
      <ToastHost items={toast.items} dismiss={toast.dismiss} />
    </div>
  );
}
