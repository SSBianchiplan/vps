// ─────────────────────────────────────────────────────────────────────────
// VisionDesk — Theme Engine (runtime). Lê o snapshot app_* do localStorage e
// escreve TODAS as CSS vars do spec_aparencia.md (§6/§7) + data-attributes no
// documentElement. Faz a ponte com os tokens nativos do VisionDesk (--bg,
// --panel, --edge, --surface, --accent) para que o estilo escolhido se aplique
// a TODOS os elementos sem re-render React.
// ─────────────────────────────────────────────────────────────────────────

import {
  BTN_STYLES,
  CARD_LAYOUTS,
  CARD_STYLES,
  CHART_PALETTES,
  CHART_THEMES,
  DEFAULTS,
  FONT_SIZES,
  INTENSITY_LEVELS,
  MODAL_BG_STYLES,
  MODAL_STYLES,
  STORAGE_KEYS as K,
  TOOLTIP_STYLES,
  type SavedTheme,
  type ThemeMode,
  type ThemeState,
  type Vars,
} from "./presets";

const root = () => document.documentElement;
const css = (k: string, v: string) => root().style.setProperty(k, v);
const attr = (k: string, v: string) => root().setAttribute(k, v);

function getItem(key: string, def: string): string {
  try { return localStorage.getItem(key) ?? def; } catch { return def; }
}
function setItem(key: string, val: string): void {
  try { localStorage.setItem(key, val); } catch { /* indisponível */ }
}

export function readThemeState(): ThemeState {
  return {
    themeMode: getItem(K.themeMode, DEFAULTS.themeMode) as ThemeMode,
    cardStyle: getItem(K.cardStyle, DEFAULTS.cardStyle),
    intensity: getItem(K.intensity, DEFAULTS.intensity),
    cardLayout: getItem(K.cardLayout, DEFAULTS.cardLayout),
    accent: getItem(K.accent, DEFAULTS.accent),
    fontSize: getItem(K.fontSize, DEFAULTS.fontSize),
    btnStyle: getItem(K.btnStyle, DEFAULTS.btnStyle),
    modalStyle: getItem(K.modalStyle, DEFAULTS.modalStyle),
    modalBgStyle: getItem(K.modalBgStyle, DEFAULTS.modalBgStyle),
    modalBlurPct: Number(getItem(K.modalBlurPct, String(DEFAULTS.modalBlurPct))) || DEFAULTS.modalBlurPct,
    highContrast: getItem(K.highContrast, String(DEFAULTS.highContrast)) === "true",
    chartTheme: getItem(K.chartTheme, DEFAULTS.chartTheme),
    chartPalette: getItem(K.chartPalette, DEFAULTS.chartPalette),
    tooltipStyle: getItem(K.tooltipStyle, DEFAULTS.tooltipStyle),
    cardRadius: getItem(K.cardRadius, DEFAULTS.cardRadius),
    tableDensity: getItem(K.tableDensity, DEFAULTS.tableDensity),
    bgLight: getItem(K.bgLight, DEFAULTS.bgLight),
    bgDark: getItem(K.bgDark, DEFAULTS.bgDark),
    navWidth: getItem(K.navWidth, DEFAULTS.navWidth),
    navBg: getItem(K.navBg, DEFAULTS.navBg),
    motion: getItem(K.motion, DEFAULTS.motion),
  };
}

function prefersDark(): boolean {
  try { return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? true; }
  catch { return true; }
}
function resolveDark(mode: ThemeMode): boolean {
  return mode === "dark" || (mode === "system" && prefersDark());
}

function writeVars(vars: Vars): void {
  for (const [k, v] of Object.entries(vars)) css(k, v);
}

/** Converte #RGB/#RRGGBB em canais "r g b" (ou null se não for hex). */
function hexToChannels(hex: string): { rgb: string; lum: number } | null {
  let h = hex.trim().replace("#", "");
  if (h.length === 3) h = h.split("").map((c) => c + c).join("");
  if (h.length !== 6 || /[^0-9a-fA-F]/.test(h)) return null;
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return { rgb: `${r} ${g} ${b}`, lum };
}

/** Aplica o snapshot completo no DOM (todas as CSS vars + data-attrs). */
export function applyTheme(s: ThemeState): void {
  const isDark = resolveDark(s.themeMode);
  const mode = isDark ? "dark" : "light";
  attr("data-theme", mode);

  // ── Cards (§5.1/§6) ──────────────────────────────────────────────
  const card = CARD_STYLES.find((c) => c.key === s.cardStyle) ?? CARD_STYLES[0];
  const cv = card.vars[mode];
  writeVars(cv);
  const blur = INTENSITY_LEVELS.find((l) => l.key === s.intensity)?.blur ?? "24px";
  css("--card-bg", cv["--glass-bg"] ?? "rgba(255,255,255,.65)");
  css("--card-border", cv["--glass-border"] ?? "rgba(255,255,255,.85)");
  css("--card-shadow", cv["--glass-shadow"] ?? "none");
  css("--card-kpi-shadow", cv["--glass-kpi-shadow"] ?? cv["--glass-shadow"] ?? "none");
  if (!cv["--card-blur"]) css("--card-blur", blur);

  // Ponte com o token nativo --panel → todo .bg-panel vira superfície de vidro.
  // --edge/--surface ficam estáveis (do bloco [data-theme]) p/ legibilidade dos
  // controles; a borda dos cards usa --card-border via a regra .bg-panel no CSS.
  css("--panel", cv["--glass-bg"] ?? "var(--panel)");

  // ── Layout dos cards (§5.3) ──────────────────────────────────────
  const layout = CARD_LAYOUTS.find((l) => l.key === s.cardLayout) ?? CARD_LAYOUTS[0];
  attr("data-card-layout", layout.key);
  css("--system-card-pad", layout.pad);
  css("--system-card-gap", layout.gap);
  css("--system-card-title", layout.title);

  // ── Accent / fonte / raio ────────────────────────────────────────
  css("--primary", s.accent);
  css("--accent", s.accent); // token nativo do VisionDesk
  const ch = hexToChannels(s.accent);
  if (ch) {
    css("--accent-rgb", ch.rgb); // habilita bg-accent/20 etc. no Tailwind
    // contraste do texto sobre o acento, independente do tema
    css("--on-accent", ch.lum > 0.6 ? "#0b0f14" : "#ffffff");
  }
  css("--font-size", s.fontSize);
  root().style.fontSize = s.fontSize;
  css("--radius", s.cardRadius);
  attr("data-font-size", FONT_SIZES.find((f) => f.value === s.fontSize)?.key ?? "medio");

  // ── Botões (§8) ──────────────────────────────────────────────────
  attr("data-btn-style", BTN_STYLES.find((b) => b.key === s.btnStyle)?.key ?? "glass");

  // ── Motion / densidade / contraste ───────────────────────────────
  attr("data-motion", s.motion);
  attr("data-table-density", s.tableDensity);
  attr("data-density", s.tableDensity === "comfortable" ? "default" : s.tableDensity);
  attr("data-high-contrast", String(s.highContrast));

  // ── Fundo do app ─────────────────────────────────────────────────
  css("--bg", isDark ? s.bgDark : s.bgLight);

  // ── Navegação ────────────────────────────────────────────────────
  css("--nav-bg", s.navBg);
  css("--nav-width", s.navWidth);

  // ── Modal (forma + fundo + blur/saturate) (§5.5/§7) ──────────────
  const mShape = MODAL_STYLES.find((m) => m.key === s.modalStyle);
  if (mShape) writeVars(mShape.vars[mode]);
  const mBg = MODAL_BG_STYLES.find((m) => m.key === s.modalBgStyle);
  if (mBg) writeVars(mBg.vars[mode]);
  const blurPx = Math.round((s.modalBlurPct / 100) * 64);
  css("--modal-blur", `${blurPx}px`);
  css("--modal-saturate", `${Math.round(120 + s.modalBlurPct * 0.8)}%`);

  // ── Gráficos (§5.6/§5.7) ─────────────────────────────────────────
  const ct = CHART_THEMES.find((t) => t.key === s.chartTheme);
  if (ct) writeVars(ct.vars[mode]);
  const cp = CHART_PALETTES.find((p) => p.key === s.chartPalette);
  if (cp) cp.colors.forEach((c, i) => css(`--chart-c${i + 1}`, c));

  // ── Tooltips (§5.8) ──────────────────────────────────────────────
  const tip = TOOLTIP_STYLES.find((t) => t.key === s.tooltipStyle);
  if (tip) writeVars(tip.vars);
}

export function persistTheme(s: ThemeState): void {
  setItem(K.themeMode, s.themeMode);
  setItem(K.cardStyle, s.cardStyle);
  setItem(K.intensity, s.intensity);
  setItem(K.cardLayout, s.cardLayout);
  setItem(K.accent, s.accent);
  setItem(K.fontSize, s.fontSize);
  setItem(K.btnStyle, s.btnStyle);
  setItem(K.modalStyle, s.modalStyle);
  setItem(K.modalBgStyle, s.modalBgStyle);
  setItem(K.modalBlurPct, String(s.modalBlurPct));
  setItem(K.highContrast, String(s.highContrast));
  setItem(K.chartTheme, s.chartTheme);
  setItem(K.chartPalette, s.chartPalette);
  setItem(K.tooltipStyle, s.tooltipStyle);
  setItem(K.cardRadius, s.cardRadius);
  setItem(K.tableDensity, s.tableDensity);
  setItem(K.bgLight, s.bgLight);
  setItem(K.bgDark, s.bgDark);
  setItem(K.navWidth, s.navWidth);
  setItem(K.navBg, s.navBg);
  setItem(K.motion, s.motion);
}

// ── pub/sub para o painel reagir ────────────────────────────────────────
type Listener = (s: ThemeState) => void;
const listeners = new Set<Listener>();
export function subscribeTheme(fn: Listener): () => void {
  listeners.add(fn);
  return () => { listeners.delete(fn); };
}
function emit(s: ThemeState): void { listeners.forEach((fn) => fn(s)); }

export function setTheme(partial: Partial<ThemeState>): ThemeState {
  const next = { ...readThemeState(), ...partial };
  applyTheme(next);
  persistTheme(next);
  emit(next);
  return next;
}

export function resetTheme(): ThemeState {
  return setTheme({ ...DEFAULTS });
}

// ── Temas salvos (§9) ────────────────────────────────────────────────────
export function listSavedThemes(): SavedTheme[] {
  try {
    const raw = JSON.parse(getItem(K.savedThemes, "[]"));
    return Array.isArray(raw) ? raw : [];
  } catch { return []; }
}
export function saveTheme(name: string): SavedTheme {
  const list = listSavedThemes();
  const item: SavedTheme = { id: `${name}-${list.length + 1}`, name, state: readThemeState() };
  setItem(K.savedThemes, JSON.stringify([...list, item]));
  return item;
}
export function applySavedTheme(id: string): ThemeState | null {
  const found = listSavedThemes().find((t) => t.id === id);
  return found ? setTheme(found.state) : null;
}
export function deleteSavedTheme(id: string): void {
  setItem(K.savedThemes, JSON.stringify(listSavedThemes().filter((t) => t.id !== id)));
}

// ── Export / Import (§4) ─────────────────────────────────────────────────
export function exportTheme(): string {
  const out: Record<string, string> = {};
  Object.values(K).forEach((key) => {
    const v = localStorage.getItem(key);
    if (v !== null) out[key] = v;
  });
  return JSON.stringify(out, null, 2);
}
export function importTheme(json: string): void {
  const obj = JSON.parse(json) as Record<string, string>;
  Object.entries(obj).forEach(([k, v]) => { if (k.startsWith("app_")) setItem(k, v); });
  const s = readThemeState();
  applyTheme(s);
  emit(s);
}

let mediaBound = false;
export function initThemeFromStorage(): void {
  applyTheme(readThemeState());
  if (!mediaBound) {
    try {
      const mq = window.matchMedia("(prefers-color-scheme: dark)");
      mq.addEventListener?.("change", () => {
        const s = readThemeState();
        if (s.themeMode === "system") { applyTheme(s); emit(s); }
      });
      mediaBound = true;
    } catch { /* matchMedia indisponível */ }
  }
}
