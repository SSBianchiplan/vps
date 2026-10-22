import { useEffect, useState } from "react";
import { useStore } from "../store/useStore";
import { btnCls, btnPrimaryCls, inputCls } from "../lib/ui";
import {
  ACCENTS,
  BG_DARKS,
  BG_LIGHTS,
  BTN_STYLES,
  CARD_LAYOUTS,
  CARD_RADII,
  CARD_STYLES,
  CHART_PALETTES,
  CHART_THEMES,
  DENSITIES,
  FONT_SIZES,
  INTENSITY_LEVELS,
  MODAL_BG_STYLES,
  MODAL_STYLES,
  MOTIONS,
  NAV_WIDTHS,
  SIDEBAR_THEMES,
  TOOLTIP_STYLES,
  type SavedTheme,
  type ThemeState,
} from "../theme/presets";
import {
  applySavedTheme,
  deleteSavedTheme,
  exportTheme,
  importTheme,
  listSavedThemes,
  readThemeState,
  resetTheme,
  saveTheme,
  setTheme,
  subscribeTheme,
} from "../theme/engine";
import { getConfigAll, putConfig, type UiComponent } from "../api/appconfig";
import { ComponentGallery } from "./ComponentGallery";

function isDarkMode(s: ThemeState): boolean {
  if (s.themeMode === "dark") return true;
  if (s.themeMode === "light") return false;
  try { return window.matchMedia("(prefers-color-scheme: dark)").matches; } catch { return true; }
}

// ── Helpers de UI ────────────────────────────────────────────────────────
function Section({ icon, title, desc, children }: {
  icon: string; title: string; desc?: string; children: React.ReactNode;
}) {
  return (
    <section className="vd-surface border border-edge rounded-card p-4">
      <div className="mb-3">
        <h3 className="text-sm font-semibold flex items-center gap-2">
          <span className="opacity-70">{icon}</span> {title}
        </h3>
        {desc && <p className="text-xs text-muted mt-0.5">{desc}</p>}
      </div>
      {children}
    </section>
  );
}

function Tile({ selected, onClick, children, title }: {
  selected: boolean; onClick: () => void; children: React.ReactNode; title?: string;
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      className={
        "vd-keep relative text-left rounded-card border p-2.5 transition-all " +
        (selected ? "border-accent ring-1 ring-accent/40" : "border-edge hover:border-accent/60")
      }
    >
      {children}
      {selected && (
        <span className="absolute top-1.5 right-1.5 w-4 h-4 rounded-full bg-accent text-onaccent text-[10px] flex items-center justify-center">✓</span>
      )}
    </button>
  );
}

function Grid({ cols = 4, children }: { cols?: number; children: React.ReactNode }) {
  const cls = cols === 2 ? "grid-cols-2" : cols === 3 ? "grid-cols-2 sm:grid-cols-3" : "grid-cols-2 sm:grid-cols-4";
  return <div className={"grid gap-2 " + cls}>{children}</div>;
}

function Caption({ children }: { children: React.ReactNode }) {
  return <div className="text-xs font-medium mt-1.5">{children}</div>;
}

// ── Painel ────────────────────────────────────────────────────────────────
export function ModuloAparencia() {
  const open = useStore((s) => s.aparenciaOpen);
  const setOpen = useStore((s) => s.setAparenciaOpen);

  const [s, setS] = useState<ThemeState>(() => readThemeState());
  const [saved, setSaved] = useState<SavedTheme[]>([]);
  const [name, setName] = useState("");
  const [tokens, setTokens] = useState<[string, string][]>([]);
  const [comps, setComps] = useState<UiComponent[]>([]);
  const [cfgMsg, setCfgMsg] = useState("");

  useEffect(() => subscribeTheme(setS), []);
  useEffect(() => {
    if (!open) return;
    setS(readThemeState());
    setSaved(listSavedThemes());
    getConfigAll().then((c) => setComps(c.ui_components || [])).catch(() => undefined);
  }, [open]);
  useEffect(() => {
    if (!open) return;
    const cs = getComputedStyle(document.documentElement);
    const names = ["--bg", "--card-bg", "--text", "--primary", "--accent-2", "--radius", "--nav-width"];
    setTokens(names.map((n) => [n, cs.getPropertyValue(n).trim()]));
  }, [open, s]);

  if (!open) return null;

  const dark = isDarkMode(s);
  const up = (p: Partial<ThemeState>) => setS(setTheme(p));

  const cfgFlash = (m: string) => { setCfgMsg(m); window.setTimeout(() => setCfgMsg(""), 2200); };
  const saveAppearance = () => putConfig("appearance", readThemeState()).then(() => cfgFlash("✓ aparência salva no servidor")).catch(() => undefined);

  const doSave = () => { saveTheme(name.trim() || `Tema ${saved.length + 1}`); setSaved(listSavedThemes()); setName(""); };
  const doExport = () => {
    const blob = new Blob([exportTheme()], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = "visiondesk-tema.json"; a.click();
    URL.revokeObjectURL(a.href);
  };
  const doImport = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]; if (!f) return;
    f.text().then((t) => { try { importTheme(t); setS(readThemeState()); setSaved(listSavedThemes()); } catch { useStore.getState().setError("Tema inválido"); } });
    e.target.value = "";
  };

  return (
    <div className="vd-modal-overlay fixed inset-0 z-50 flex items-stretch justify-center p-3" onClick={() => setOpen(false)}>
      <div
        className="vd-modal w-full max-w-3xl max-h-full flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center gap-3 px-5 py-3 border-b border-edge shrink-0">
          <div>
            <h2 className="font-bold text-base">Aparência</h2>
            <p className="text-xs text-muted">Escolha como o VisionDesk aparece. Mudanças são aplicadas e salvas automaticamente.</p>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <button className={btnCls} onClick={() => { resetTheme(); setS(readThemeState()); }}>Resetar padrões</button>
            <button className="vd-keep text-muted hover:text-text text-lg" onClick={() => setOpen(false)}>✕</button>
          </div>
        </div>

        {/* Corpo */}
        <div className="flex-1 overflow-y-auto scroll-thin p-4 space-y-4">
          {/* Modo do tema */}
          <Section icon="◐" title="Modo do tema" desc="Selecione um único tema ou sincronize com o sistema operacional.">
            <Grid cols={3}>
              {([
                ["light", "Claro", "Interface clara com fundo branco e sombras delicadas."],
                ["dark", "Escuro", "Fundo profundo em liquid glass e brilho de superfície."],
                ["system", "Sincronizar com sistema", "Alterna automaticamente conforme a preferência do SO."],
              ] as const).map(([k, label, d]) => (
                <Tile key={k} selected={s.themeMode === k} onClick={() => up({ themeMode: k })}>
                  <div className="h-12 rounded mb-1 border border-edge overflow-hidden flex">
                    <div className="flex-1" style={{ background: k === "dark" ? "#0b0f14" : k === "light" ? "#eef2f6" : "linear-gradient(90deg,#eef2f6 50%,#0b0f14 50%)" }} />
                  </div>
                  <Caption>{label}</Caption>
                  <p className="text-[10px] text-muted leading-tight">{d}</p>
                </Tile>
              ))}
            </Grid>
          </Section>

          {/* Estilo do card */}
          <Section icon="▭" title="Estilo do card" desc="Define o visual de toda superfície: cards, KPIs, tabelas e painéis do sistema.">
            <Grid cols={4}>
              {CARD_STYLES.map((c) => {
                const v = c.vars[dark ? "dark" : "light"];
                return (
                  <Tile key={c.key} selected={s.cardStyle === c.key} onClick={() => up({ cardStyle: c.key })}>
                    <div className="h-12 rounded mb-1 border" style={{ background: v["--glass-bg"], borderColor: v["--glass-border"], boxShadow: v["--glass-shadow"] }} />
                    <Caption>{c.label}</Caption>
                  </Tile>
                );
              })}
            </Grid>
          </Section>

          {/* Layout dos cards */}
          <Section icon="▤" title="Layout dos cards" desc="Densidade de espaçamento e título dos cards.">
            <Grid cols={3}>
              {CARD_LAYOUTS.map((l) => (
                <Tile key={l.key} selected={s.cardLayout === l.key} onClick={() => up({ cardLayout: l.key })}>
                  <div className="rounded border border-edge bg-edge mb-1" style={{ padding: l.pad }}>
                    <div className="h-1.5 rounded bg-muted/50" style={{ marginBottom: l.gap }} />
                    <div className="h-1.5 rounded bg-muted/30" />
                  </div>
                  <Caption>{l.label}</Caption>
                </Tile>
              ))}
            </Grid>
          </Section>

          {/* Intensidade liquid glass */}
          <Section icon="◍" title="Intensidade de liquid glass" desc="Controla o nível de desfoque (backdrop blur).">
            <Grid cols={4}>
              {INTENSITY_LEVELS.map((l) => (
                <Tile key={l.key} selected={s.intensity === l.key} onClick={() => up({ intensity: l.key })}>
                  <div className="h-10 rounded mb-1 border border-edge bg-gradient-to-br from-white/20 to-white/5" style={{ backdropFilter: `blur(${l.blur})` }} />
                  <Caption>{l.label}</Caption>
                  <p className="text-[10px] text-muted">{l.blur}</p>
                </Tile>
              ))}
            </Grid>
          </Section>

          {/* Botões e filtros */}
          <Section icon="⬚" title="Botões e filtros" desc="Define o visual de botões de ação e filtros rápidos do sistema.">
            <Grid cols={4}>
              {BTN_STYLES.map((b) => (
                <Tile key={b.key} selected={s.btnStyle === b.key} onClick={() => up({ btnStyle: b.key })}>
                  <div className="h-10 flex items-center justify-center mb-1">
                    <span
                      className="px-2 py-1 text-[10px] text-white"
                      style={{
                        background: b.key === "outlined" ? "transparent" : "var(--accent)",
                        border: b.key === "outlined" ? "1px solid var(--accent)" : "none",
                        color: b.key === "outlined" ? "var(--accent)" : "var(--on-accent)",
                        borderRadius: b.key === "pill" ? "999px" : "8px",
                      }}
                    >Botão</span>
                  </div>
                  <Caption>{b.label}</Caption>
                </Tile>
              ))}
            </Grid>
          </Section>

          {/* Estilo dos modais + blur */}
          <Section icon="❒" title="Estilo dos modais" desc="Forma, raio e sombra das janelas modais.">
            <Grid cols={4}>
              {MODAL_STYLES.map((m) => {
                const v = m.vars[dark ? "dark" : "light"];
                return (
                  <Tile key={m.key} selected={s.modalStyle === m.key} onClick={() => up({ modalStyle: m.key })}>
                    <div className="h-12 rounded mb-1 border border-edge bg-surface flex items-center justify-center">
                      <div className="w-3/4 h-7 border border-edge" style={{ background: "var(--card-bg)", borderRadius: v["--radius-modal"], boxShadow: v["--modal-shadow"] }} />
                    </div>
                    <Caption>{m.label}</Caption>
                  </Tile>
                );
              })}
            </Grid>
            <div className="flex items-center gap-3 mt-3">
              <span className="text-xs text-muted w-32">Intensidade do blur</span>
              <input type="range" min={0} max={100} value={s.modalBlurPct} onChange={(e) => up({ modalBlurPct: Number(e.target.value) })} className="flex-1 accent-[var(--accent)]" />
              <span className="text-xs text-muted w-10 text-right">{s.modalBlurPct}%</span>
            </div>
          </Section>

          {/* Fundo dos modais */}
          <Section icon="▦" title="Fundo dos modais" desc="Superfície de fundo das janelas modais.">
            <Grid cols={4}>
              {MODAL_BG_STYLES.map((m) => {
                const v = m.vars[dark ? "dark" : "light"];
                return (
                  <Tile key={m.key} selected={s.modalBgStyle === m.key} onClick={() => up({ modalBgStyle: m.key })}>
                    <div className="h-12 rounded mb-1 border" style={{ background: v["--modal-bg"], borderColor: v["--modal-border"] }} />
                    <Caption>{m.label}</Caption>
                  </Tile>
                );
              })}
            </Grid>
          </Section>

          {/* Gráficos */}
          <Section icon="📈" title="Gráficos" desc="Tema visual e paleta de séries dos gráficos.">
            <p className="text-xs text-muted mb-1.5">Tema visual</p>
            <Grid cols={5}>
              {CHART_THEMES.map((t) => {
                const v = t.vars[dark ? "dark" : "light"];
                return (
                  <Tile key={t.key} selected={s.chartTheme === t.key} onClick={() => up({ chartTheme: t.key })}>
                    <div className="h-10 rounded mb-1 relative overflow-hidden" style={{ background: v["--chart-bg"] }}>
                      <div className="absolute bottom-1 left-1 right-1 h-px" style={{ background: v["--chart-grid"] }} />
                      <svg viewBox="0 0 40 20" className="w-full h-full"><polyline points="0,16 10,8 20,12 30,4 40,9" fill="none" stroke="var(--accent)" strokeWidth="1.5" /></svg>
                    </div>
                    <Caption>{t.label}</Caption>
                  </Tile>
                );
              })}
            </Grid>
            <p className="text-xs text-muted mt-3 mb-1.5">Paleta de cores</p>
            <div className="space-y-1.5">
              {CHART_PALETTES.map((p) => (
                <button key={p.key} onClick={() => up({ chartPalette: p.key })}
                  className={"vd-keep w-full flex items-center gap-2 px-2 py-1.5 rounded-card border transition-colors " + (s.chartPalette === p.key ? "border-accent" : "border-edge hover:border-accent/60")}>
                  <span className="text-xs flex-1 text-left">{p.label}</span>
                  <span className="flex gap-1">{p.colors.map((c) => <span key={c} className="w-3.5 h-3.5 rounded-full" style={{ background: c }} />)}</span>
                  {s.chartPalette === p.key && <span className="text-accent text-xs">✓</span>}
                </button>
              ))}
            </div>
          </Section>

          {/* Tooltip */}
          <Section icon="💬" title="Tooltip" desc="Estilo aplicado a todas as tooltips do sistema — cards, tabelas e gráficos.">
            <Grid cols={4}>
              {TOOLTIP_STYLES.map((t) => (
                <Tile key={t.key} selected={s.tooltipStyle === t.key} onClick={() => up({ tooltipStyle: t.key })}>
                  <div className="h-12 flex items-center justify-center mb-1">
                    <span className="px-2 py-1 text-[10px]" style={{ background: t.vars["--tip-bg"], color: t.vars["--tip-color"], border: `1px solid ${t.vars["--tip-border"]}`, borderRadius: t.vars["--tip-radius"], boxShadow: t.vars["--tip-shadow"] }}>Dica</span>
                  </div>
                  <Caption>{t.label}</Caption>
                </Tile>
              ))}
            </Grid>
          </Section>

          {/* Cor de destaque */}
          <Section icon="🎨" title="Cor de destaque" desc="Define a cor de ação principal (links, botões, seleção).">
            <div className="flex flex-wrap items-center gap-2">
              {ACCENTS.map((a) => (
                <button key={a.value} title={a.label} onClick={() => up({ accent: a.value })}
                  className={"vd-keep w-8 h-8 rounded-full border-2 transition-transform hover:scale-110 " + (s.accent.toLowerCase() === a.value.toLowerCase() ? "border-text" : "border-transparent")}
                  style={{ background: a.value }} />
              ))}
              <label className="flex items-center gap-1.5 ml-1 text-xs text-muted cursor-pointer">
                <input type="color" value={s.accent} onChange={(e) => up({ accent: e.target.value })} className="vd-keep w-8 h-8 rounded cursor-pointer bg-transparent border border-edge" />
                custom
              </label>
            </div>
          </Section>

          {/* Tipografia + contraste */}
          <Section icon="Aa" title="Tamanho da fonte" desc="Ajusta o tamanho do texto em toda a interface.">
            <Grid cols={3}>
              {FONT_SIZES.map((f) => (
                <Tile key={f.key} selected={s.fontSize === f.value} onClick={() => up({ fontSize: f.value })}>
                  <div className="h-10 flex items-center justify-center mb-1"><span style={{ fontSize: f.value }} className="font-bold">Aa</span></div>
                  <Caption>{f.label}</Caption>
                  <p className="text-[10px] text-muted">{f.value}</p>
                </Tile>
              ))}
            </Grid>
            <label className="flex items-center gap-2 text-sm cursor-pointer mt-3">
              <input type="checkbox" checked={s.highContrast} onChange={(e) => up({ highContrast: e.target.checked })} />
              Aumentar contraste
            </label>
          </Section>

          {/* Preview ao vivo */}
          <Section icon="👁" title="Preview ao vivo" desc="Visualização de como ficam cartões e tabelas com as configurações atuais.">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="vd-surface border border-edge rounded-card p-3">
                <p className="text-[10px] text-muted uppercase tracking-wider">Card • KPI</p>
                <p className="text-2xl font-bold text-accent">128</p>
                <p className="text-xs text-muted">detecções hoje</p>
              </div>
              <table className="w-full text-xs">
                <tbody>
                  <tr className="border-b border-edge"><td className="text-muted">Câmera</td><td className="text-right text-text">Status</td></tr>
                  <tr className="border-b border-edge"><td>Frente</td><td className="text-right text-ok">● online</td></tr>
                  <tr><td>Fundos</td><td className="text-right text-ok">● online</td></tr>
                </tbody>
              </table>
            </div>
          </Section>

          {/* Raio dos cards */}
          <Section icon="⬛" title="Raio dos cards" desc="Arredondamento dos cantos em cards, botões e painéis.">
            <Grid cols={5}>
              {CARD_RADII.map((r) => (
                <Tile key={r.key} selected={s.cardRadius === r.value} onClick={() => up({ cardRadius: r.value })}>
                  <div className="h-10 flex items-center justify-center mb-1"><div className="w-9 h-9 bg-edge border border-muted/40" style={{ borderRadius: r.value }} /></div>
                  <Caption>{r.label}</Caption>
                </Tile>
              ))}
            </Grid>
          </Section>

          {/* Densidade */}
          <Section icon="≣" title="Densidade das tabelas" desc="Espaçamento interno das células em tabelas do sistema.">
            <Grid cols={3}>
              {DENSITIES.map((d) => (
                <Tile key={d.key} selected={s.tableDensity === d.key} onClick={() => up({ tableDensity: d.key })}>
                  <div className="h-10 flex flex-col justify-center gap-1 px-1 mb-1">
                    <div className="h-1 rounded bg-muted/40" /><div className="h-1 rounded bg-muted/30" /><div className="h-1 rounded bg-muted/20" />
                  </div>
                  <Caption>{d.label}</Caption>
                </Tile>
              ))}
            </Grid>
          </Section>

          {/* Fundo do app */}
          <Section icon="▓" title="Fundo do app" desc="Cor de fundo da interface (claro/escuro).">
            <p className="text-xs text-muted mb-1">Claro</p>
            <div className="flex flex-wrap gap-2 mb-3">
              {BG_LIGHTS.map((b) => (
                <button key={b.value} title={b.label} onClick={() => up({ bgLight: b.value })}
                  className={"vd-keep w-8 h-8 rounded border-2 " + (s.bgLight.toLowerCase() === b.value.toLowerCase() ? "border-accent" : "border-edge")} style={{ background: b.value }} />
              ))}
              <input type="color" value={s.bgLight} onChange={(e) => up({ bgLight: e.target.value })} className="vd-keep w-8 h-8 rounded border border-edge bg-transparent" />
            </div>
            <p className="text-xs text-muted mb-1">Escuro</p>
            <div className="flex flex-wrap gap-2">
              {BG_DARKS.map((b) => (
                <button key={b.value} title={b.label} onClick={() => up({ bgDark: b.value })}
                  className={"vd-keep w-8 h-8 rounded border-2 " + (s.bgDark.toLowerCase() === b.value.toLowerCase() ? "border-accent" : "border-edge")} style={{ background: b.value }} />
              ))}
              <input type="color" value={s.bgDark} onChange={(e) => up({ bgDark: e.target.value })} className="vd-keep w-8 h-8 rounded border border-edge bg-transparent" />
            </div>
          </Section>

          {/* Largura menu lateral */}
          <Section icon="▥" title="Largura de menu lateral" desc="Ajusta a largura da barra de navegação.">
            <Grid cols={3}>
              {NAV_WIDTHS.map((n) => (
                <Tile key={n.key} selected={s.navWidth === n.value} onClick={() => up({ navWidth: n.value })}>
                  <div className="h-10 flex items-center gap-1 mb-1"><div className="h-full bg-edge rounded" style={{ width: `${Math.round(parseInt(n.value) / 12)}px` }} /><div className="flex-1 h-full bg-surface rounded" /></div>
                  <Caption>{n.label}</Caption>
                  <p className="text-[10px] text-muted">{n.value}</p>
                </Tile>
              ))}
            </Grid>
          </Section>

          {/* Animações */}
          <Section icon="✦" title="Animações" desc="Velocidade das transições e animações da interface.">
            <Grid cols={4}>
              {MOTIONS.map((m) => (
                <Tile key={m.key} selected={s.motion === m.key} onClick={() => up({ motion: m.key })}>
                  <div className="h-8 flex items-center justify-center mb-1 text-lg">{m.key === "off" ? "⏸" : m.key === "fast" ? "⚡" : m.key === "slow" ? "🐢" : "▶"}</div>
                  <Caption>{m.label}</Caption>
                </Tile>
              ))}
            </Grid>
          </Section>

          {/* Cor menu lateral */}
          <Section icon="🎚" title="Cor de menu lateral" desc="Gradiente de fundo da barra de navegação.">
            <div className="flex flex-wrap gap-2">
              {SIDEBAR_THEMES.map((t) => (
                <button key={t.label} title={t.label} onClick={() => up({ navBg: t.value })}
                  className={"vd-keep w-12 h-10 rounded-card border-2 " + (s.navBg === t.value ? "border-accent" : "border-edge")} style={{ background: t.value }} />
              ))}
            </div>
          </Section>

          {/* Temas salvos */}
          <Section icon="💾" title="Temas salvos" desc="Salve combinações completas e reaplique quando quiser.">
            <div className="flex gap-2 mb-2">
              <input className={inputCls} placeholder="Nome do tema" value={name} onChange={(e) => setName(e.target.value)} />
              <button className={btnPrimaryCls} onClick={doSave}>Salvar</button>
            </div>
            {saved.length === 0 ? <p className="text-xs text-muted">Nenhum tema salvo ainda.</p> : (
              <div className="space-y-1">
                {saved.map((t) => (
                  <div key={t.id} className="flex items-center gap-1">
                    <button onClick={() => { applySavedTheme(t.id); setS(readThemeState()); }}
                      className="vd-keep flex-1 text-left px-2 py-1.5 rounded-card text-sm border border-edge hover:border-accent transition-colors">{t.name}</button>
                    <button className="vd-keep px-2 py-1.5 text-muted hover:text-nok" onClick={() => { deleteSavedTheme(t.id); setSaved(listSavedThemes()); }}>✕</button>
                  </div>
                ))}
              </div>
            )}
          </Section>

          {/* Tokens CSS ativos */}
          <Section icon="{ }" title="Tokens CSS ativos" desc="Variáveis aplicadas no momento (computadas do tema atual).">
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {tokens.map(([k, v]) => (
                <div key={k} className="rounded-card border border-edge p-2">
                  <div className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded-full border border-edge" style={{ background: v }} />
                    <span className="font-mono text-[10px] text-muted truncate">{k}</span>
                  </div>
                  <p className="font-mono text-[10px] text-text truncate mt-0.5">{v || "—"}</p>
                </div>
              ))}
            </div>
          </Section>

          {/* Princípios de aplicação + Liquid Glass */}
          <Section icon="✶" title="Princípios de aplicação — Liquid Glass aplicado" desc="Como o design system é aplicado no VisionDesk.">
            <ul className="space-y-1 text-xs text-muted">
              {[
                "Liquid Glass: superfícies translúcidas (backdrop-blur), bordas sutis e profundidade por sombra — tokens --glass-bg/--glass-border/--glass-shadow.",
                "Uma cor de destaque (--accent) para ação/seleção; o resto neutro. Raio e densidade consistentes via tokens (--radius).",
                "1 ação primária por tela; feedback imediato (Toast/Skeleton/Spinner) e exceções acionáveis.",
                "Componentes reutilizáveis em components/ui/ — o mesmo modelo (abaixo) é usado em todas as telas.",
                "Contraste AA e movimento configurável (reduzir/encerrar animações).",
                "Tema e catálogo persistidos no banco (app_config) → consistência entre sessões e dispositivos.",
              ].map((p, i) => <li key={i} className="flex gap-2"><span className="text-accent">✓</span>{p}</li>)}
            </ul>
          </Section>

          {/* Galeria de componentes — modelos ao vivo, prontos p/ uso (por último) */}
          <Section icon="🪄" title="Galeria de Componentes (modelos ao vivo)" desc="Modelo interativo e pronto p/ uso de cada componente. Passe o mouse para a descrição de uso.">
            {comps.length === 0 ? <p className="text-xs text-muted">Carregando…</p> : <ComponentGallery components={comps} />}
          </Section>
        </div>

        {/* Footer */}
        <div className="p-3 border-t border-edge flex items-center gap-2 shrink-0">
          <button className={btnCls} onClick={doExport}>⬇ Exportar</button>
          <label className={btnCls + " cursor-pointer"}>⬆ Importar<input type="file" accept="application/json" className="hidden" onChange={doImport} /></label>
          <button className={btnCls} onClick={saveAppearance}>☁ Salvar no servidor</button>
          {cfgMsg && <span className="text-xs text-ok">{cfgMsg}</span>}
          <button className={btnPrimaryCls + " ml-auto"} onClick={() => setOpen(false)}>Concluir</button>
        </div>
      </div>
    </div>
  );
}
