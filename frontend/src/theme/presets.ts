// ─────────────────────────────────────────────────────────────────────────
// VisionDesk — Theme Engine (presets) — fiel ao spec_aparencia.md §5
// Todos os valores de CSS vars são copiados do spec. O engine (engine.ts) lê
// o snapshot do localStorage (chaves app_*) e escreve estas vars + data-attrs
// no documentElement, propagando para TODOS os elementos do sistema.
// ─────────────────────────────────────────────────────────────────────────

export type ThemeMode = "light" | "dark" | "system";
export type Vars = Record<string, string>;
export interface LightDark { light: Vars; dark: Vars }

// ── Chaves localStorage (prefixo app_, §4) ──────────────────────────────
export const STORAGE_KEYS = {
  themeMode: "app_theme_mode",
  cardStyle: "app_card_style",
  intensity: "app_glass_intensity",
  cardLayout: "app_card_layout",
  accent: "app_accent",
  fontSize: "app_font_size",
  btnStyle: "app_btn_style",
  modalStyle: "app_modal_style",
  modalBgStyle: "app_modal_bg_style",
  modalBlurPct: "app_modal_blur_pct",
  highContrast: "app_high_contrast",
  chartTheme: "app_chart_theme",
  chartPalette: "app_chart_palette",
  tooltipStyle: "app_tooltip_style",
  cardRadius: "app_card_radius",
  tableDensity: "app_table_density",
  bgLight: "app_bg_light",
  bgDark: "app_bg_dark",
  navWidth: "app_nav_width",
  navBg: "app_nav_bg",
  motion: "app_motion",
  savedThemes: "app_saved_themes",
} as const;

// ── §5.1 CARD_STYLES ────────────────────────────────────────────────────
export interface CardStyle { key: string; label: string; vars: LightDark }
export const CARD_STYLES: CardStyle[] = [
  {
    key: "liquid_glass", label: "Liquid Glass",
    vars: {
      light: {
        "--glass-bg": "rgba(255,255,255,.65)", "--glass-border": "rgba(255,255,255,.85)",
        "--glass-shadow": "0 4px 20px rgba(45,51,54,.07),inset 0 1px 0 rgba(255,255,255,.95)",
        "--glass-kpi-shadow": "0 2px 12px rgba(45,51,54,.07),inset 0 1px 0 rgba(255,255,255,.95)",
        "--glass-sm": "rgba(255,255,255,.62)", "--glass-sm-border": "rgba(255,255,255,.80)",
        "--card-saturate": "160%", "--in-bg": "rgba(255,255,255,.62)", "--in-border": "rgba(255,255,255,.78)",
        "--modal-bg": "rgba(255,255,255,.74)", "--drawer-bg": "rgba(235,235,235,.92)",
      },
      dark: {
        "--glass-bg": "rgba(255,255,255,.055)", "--glass-border": "rgba(255,255,255,.10)",
        "--glass-shadow": "0 1px 0 rgba(255,255,255,.08) inset,0 8px 32px rgba(0,0,0,.70),0 2px 8px rgba(0,0,0,.55)",
        "--glass-kpi-shadow": "0 1px 0 rgba(255,255,255,.07) inset,0 4px 18px rgba(0,0,0,.60)",
        "--glass-sm": "rgba(255,255,255,.05)", "--glass-sm-border": "rgba(255,255,255,.09)",
        "--card-saturate": "160%", "--in-bg": "rgba(255,255,255,.06)", "--in-border": "rgba(255,255,255,.10)",
        "--modal-bg": "rgba(12,12,16,.92)", "--drawer-bg": "rgba(9,9,12,.94)",
      },
    },
  },
  {
    key: "ultra_glass", label: "Ultra Glass",
    vars: {
      light: {
        "--glass-bg": "rgba(255,255,255,.28)", "--glass-border": "rgba(255,255,255,.52)",
        "--glass-shadow": "0 2px 24px rgba(45,51,54,.05),inset 0 1px 0 rgba(255,255,255,.88)",
        "--glass-sm": "rgba(255,255,255,.20)", "--glass-sm-border": "rgba(255,255,255,.40)",
        "--card-saturate": "200%", "--in-bg": "rgba(255,255,255,.30)", "--in-border": "rgba(255,255,255,.50)",
        "--modal-bg": "rgba(255,255,255,.50)", "--drawer-bg": "rgba(235,235,235,.55)",
      },
      dark: {
        "--glass-bg": "rgba(255,255,255,.022)", "--glass-border": "rgba(255,255,255,.07)",
        "--glass-shadow": "0 1px 0 rgba(255,255,255,.05) inset,0 4px 24px rgba(0,0,0,.82)",
        "--glass-sm": "rgba(255,255,255,.018)", "--glass-sm-border": "rgba(255,255,255,.055)",
        "--card-saturate": "200%", "--in-bg": "rgba(255,255,255,.03)", "--in-border": "rgba(255,255,255,.08)",
        "--modal-bg": "rgba(8,8,12,.88)", "--drawer-bg": "rgba(5,5,8,.92)",
      },
    },
  },
  {
    key: "fosco", label: "Fosco",
    vars: {
      light: {
        "--glass-bg": "rgba(255,255,255,.88)", "--glass-border": "rgba(200,210,220,.65)",
        "--glass-shadow": "0 4px 16px rgba(45,51,54,.09),inset 0 1px 0 rgba(255,255,255,.98)",
        "--glass-sm": "rgba(255,255,255,.78)", "--glass-sm-border": "rgba(200,210,220,.55)",
        "--card-saturate": "120%", "--in-bg": "rgba(255,255,255,.85)", "--in-border": "rgba(200,210,220,.60)",
        "--modal-bg": "rgba(250,250,252,.92)", "--drawer-bg": "rgba(240,242,245,.94)",
      },
      dark: {
        "--glass-bg": "rgba(28,28,36,.90)", "--glass-border": "rgba(255,255,255,.09)",
        "--glass-shadow": "0 1px 0 rgba(255,255,255,.06) inset,0 8px 24px rgba(0,0,0,.65)",
        "--glass-sm": "rgba(30,30,40,.88)", "--glass-sm-border": "rgba(255,255,255,.08)",
        "--card-saturate": "120%", "--in-bg": "rgba(30,30,40,.85)", "--in-border": "rgba(255,255,255,.09)",
        "--modal-bg": "rgba(18,18,24,.95)", "--drawer-bg": "rgba(14,14,20,.96)",
      },
    },
  },
  {
    key: "solido", label: "Sólido",
    vars: {
      light: {
        "--glass-bg": "#FFFFFF", "--glass-border": "#E2E8F0",
        "--glass-shadow": "0 1px 3px rgba(15,23,42,.07),0 4px 16px rgba(15,23,42,.05)",
        "--glass-sm": "#F1F5F9", "--glass-sm-border": "#E2E8F0",
        "--card-saturate": "100%", "--card-blur": "0px", "--in-bg": "#FFFFFF", "--in-border": "#CBD5E1",
        "--modal-bg": "#FFFFFF", "--drawer-bg": "#F8FAFC",
      },
      dark: {
        "--glass-bg": "#18181C", "--glass-border": "rgba(255,255,255,.09)",
        "--glass-shadow": "0 2px 12px rgba(0,0,0,.50)",
        "--glass-sm": "#1E1E24", "--glass-sm-border": "rgba(255,255,255,.08)",
        "--card-saturate": "100%", "--card-blur": "0px", "--in-bg": "#1E1E24", "--in-border": "rgba(255,255,255,.10)",
        "--modal-bg": "#18181C", "--drawer-bg": "#141418",
      },
    },
  },
];

// ── §5.2 INTENSITY_LEVELS ───────────────────────────────────────────────
export const INTENSITY_LEVELS: { key: string; label: string; blur: string }[] = [
  { key: "sutil", label: "Sutil", blur: "8px" },
  { key: "medio", label: "Médio", blur: "24px" },
  { key: "intenso", label: "Intenso", blur: "40px" },
  { key: "maximo", label: "Máximo", blur: "56px" },
];

// ── §5.3 CARD_LAYOUTS ───────────────────────────────────────────────────
export const CARD_LAYOUTS: { key: string; label: string; pad: string; gap: string; title: string }[] = [
  { key: "otc", label: "Padrão OTC", pad: "18px", gap: "14px", title: "15px" },
  { key: "compact", label: "Compacto", pad: "12px", gap: "10px", title: "13px" },
  { key: "executive", label: "Executivo", pad: "22px", gap: "18px", title: "16px" },
];

// ── §5.4 ACCENTS (+ teal nativo do VisionDesk) ──────────────────────────
export const ACCENTS: { label: string; value: string }[] = [
  { label: "Teal (VisionDesk)", value: "#19C3B2" },
  { label: "Grafite", value: "#2D3336" },
  { label: "Azul", value: "#2563EB" },
  { label: "Teal", value: "#0E9C8A" },
  { label: "Violeta", value: "#7C3AED" },
  { label: "Rosa", value: "#DB2777" },
  { label: "Laranja", value: "#EA580C" },
];

// ── Botões (BTN_STYLES) — referenciado no spec (data-btn-style) ──────────
export const BTN_STYLES: { key: string; label: string }[] = [
  { key: "glass", label: "Glass" },
  { key: "outlined", label: "Outlined" },
  { key: "solido", label: "Sólido" },
  { key: "pill", label: "Pill" },
];

// ── §5.5 MODAL_STYLES (forma) ───────────────────────────────────────────
export const MODAL_STYLES: { key: string; label: string; vars: LightDark }[] = [
  {
    key: "glass", label: "Glass",
    vars: {
      light: { "--radius-modal": "20px", "--modal-overlay": "rgba(45,51,54,.30)", "--modal-shadow": "0 32px 64px rgba(45,51,54,.13),0 8px 24px rgba(45,51,54,.08),inset 0 1.5px 0 rgba(255,255,255,.98)" },
      dark: { "--radius-modal": "20px", "--modal-overlay": "rgba(0,0,0,.68)", "--modal-shadow": "0 32px 80px rgba(0,0,0,.72),0 4px 16px rgba(0,0,0,.48),inset 0 1px 0 rgba(255,255,255,.07)" },
    },
  },
  {
    key: "flutuante", label: "Flutuante",
    vars: {
      light: { "--radius-modal": "28px", "--modal-overlay": "rgba(45,51,54,.20)", "--modal-shadow": "0 48px 96px rgba(45,51,54,.20),0 12px 32px rgba(45,51,54,.12),inset 0 1.5px 0 rgba(255,255,255,.98)" },
      dark: { "--radius-modal": "28px", "--modal-overlay": "rgba(0,0,0,.55)", "--modal-shadow": "0 48px 120px rgba(0,0,0,.82),0 8px 24px rgba(0,0,0,.55),inset 0 1px 0 rgba(255,255,255,.09)" },
    },
  },
  {
    key: "solido", label: "Sólido",
    vars: {
      light: { "--radius-modal": "8px", "--modal-overlay": "rgba(0,0,0,.52)", "--modal-shadow": "0 8px 32px rgba(0,0,0,.22),0 2px 8px rgba(0,0,0,.12)" },
      dark: { "--radius-modal": "8px", "--modal-overlay": "rgba(0,0,0,.82)", "--modal-shadow": "0 8px 32px rgba(0,0,0,.55),0 2px 8px rgba(0,0,0,.35)" },
    },
  },
  {
    key: "pill", label: "Pill",
    vars: {
      light: { "--radius-modal": "32px", "--modal-overlay": "rgba(45,51,54,.26)", "--modal-shadow": "0 40px 80px rgba(45,51,54,.16),0 10px 28px rgba(45,51,54,.10),inset 0 1.5px 0 rgba(255,255,255,.98)" },
      dark: { "--radius-modal": "32px", "--modal-overlay": "rgba(0,0,0,.62)", "--modal-shadow": "0 40px 100px rgba(0,0,0,.76),0 6px 20px rgba(0,0,0,.50),inset 0 1px 0 rgba(255,255,255,.08)" },
    },
  },
];

// ── Fundo dos modais (reusa as superfícies dos cards) ───────────────────
export const MODAL_BG_STYLES: { key: string; label: string; vars: LightDark }[] =
  CARD_STYLES.map((c) => ({
    key: c.key,
    label: c.label,
    vars: {
      light: { "--modal-bg": c.vars.light["--modal-bg"], "--modal-border": c.vars.light["--glass-border"] },
      dark: { "--modal-bg": c.vars.dark["--modal-bg"], "--modal-border": c.vars.dark["--glass-border"] },
    },
  }));

// ── §5.6 CHART_THEMES (light/dark; "mesmo" => igual ao light) ───────────
export const CHART_THEMES: { key: string; label: string; vars: LightDark }[] = [
  {
    key: "padrao_flcx", label: "Padrão FL.CX",
    vars: {
      light: { "--chart-bg": "#F8FAFC", "--chart-grid": "#EEF2F7", "--chart-axis": "#94A3B8", "--chart-tooltip-bg": "#0F172A", "--chart-tooltip-border": "#334155" },
      dark: { "--chart-bg": "rgba(15,23,42,.88)", "--chart-grid": "rgba(255,255,255,.07)", "--chart-axis": "rgba(148,163,184,.65)", "--chart-tooltip-bg": "#0F172A", "--chart-tooltip-border": "#334155" },
    },
  },
  {
    key: "scada_dark", label: "Industrial SCADA",
    vars: {
      light: { "--chart-bg": "rgba(8,10,18,.97)", "--chart-grid": "rgba(255,255,255,.065)", "--chart-axis": "rgba(255,255,255,.40)", "--chart-tooltip-bg": "rgba(8,10,18,.97)", "--chart-tooltip-border": "rgba(255,255,255,.12)" },
      dark: { "--chart-bg": "rgba(8,10,18,.97)", "--chart-grid": "rgba(255,255,255,.065)", "--chart-axis": "rgba(255,255,255,.40)", "--chart-tooltip-bg": "rgba(8,10,18,.97)", "--chart-tooltip-border": "rgba(255,255,255,.12)" },
    },
  },
  {
    key: "glass_adaptive", label: "Glass Adaptativo",
    vars: {
      light: { "--chart-bg": "rgba(255,255,255,.65)", "--chart-grid": "rgba(15,23,42,.07)", "--chart-axis": "rgba(15,23,42,.38)", "--chart-tooltip-bg": "rgba(255,255,255,.74)", "--chart-tooltip-border": "rgba(255,255,255,.85)" },
      dark: { "--chart-bg": "rgba(255,255,255,.055)", "--chart-grid": "rgba(255,255,255,.08)", "--chart-axis": "rgba(255,255,255,.35)", "--chart-tooltip-bg": "rgba(12,12,16,.92)", "--chart-tooltip-border": "rgba(255,255,255,.10)" },
    },
  },
  {
    key: "minimal_light", label: "Minimal Claro",
    vars: {
      light: { "--chart-bg": "#FFFFFF", "--chart-grid": "rgba(15,23,42,.065)", "--chart-axis": "rgba(15,23,42,.38)", "--chart-tooltip-bg": "#FFFFFF", "--chart-tooltip-border": "#E2E8F0" },
      dark: { "--chart-bg": "#FFFFFF", "--chart-grid": "rgba(15,23,42,.065)", "--chart-axis": "rgba(15,23,42,.38)", "--chart-tooltip-bg": "#FFFFFF", "--chart-tooltip-border": "#E2E8F0" },
    },
  },
  {
    key: "neon_dark", label: "Neon",
    vars: {
      light: { "--chart-bg": "rgba(2,4,12,.98)", "--chart-grid": "rgba(99,102,241,.14)", "--chart-axis": "rgba(165,180,252,.50)", "--chart-tooltip-bg": "rgba(2,4,12,.98)", "--chart-tooltip-border": "rgba(99,102,241,.35)" },
      dark: { "--chart-bg": "rgba(2,4,12,.98)", "--chart-grid": "rgba(99,102,241,.14)", "--chart-axis": "rgba(165,180,252,.50)", "--chart-tooltip-bg": "rgba(2,4,12,.98)", "--chart-tooltip-border": "rgba(99,102,241,.35)" },
    },
  },
];

// ── §5.7 CHART_PALETTES ─────────────────────────────────────────────────
export const CHART_PALETTES: { key: string; label: string; colors: string[] }[] = [
  { key: "industrial", label: "Industrial", colors: ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#06B6D4"] },
  { key: "vivid", label: "Vívida", colors: ["#6366F1", "#EC4899", "#14B8A6", "#F97316", "#84CC16", "#A855F7"] },
  { key: "corporate", label: "Corporate", colors: ["#2563EB", "#0E9C8A", "#D97706", "#DC2626", "#7C3AED", "#0891B2"] },
  { key: "pastel", label: "Pastel", colors: ["#93C5FD", "#6EE7B7", "#FCD34D", "#FCA5A5", "#C4B5FD", "#67E8F9"] },
  { key: "monochrome", label: "Monocromática", colors: ["#F8FAFC", "#CBD5E1", "#94A3B8", "#64748B", "#475569", "#334155"] },
];

// ── §5.8 TOOLTIP_STYLES ─────────────────────────────────────────────────
export const TOOLTIP_STYLES: { key: string; label: string; vars: Vars }[] = [
  { key: "dark", label: "Escura", vars: { "--tip-bg": "#0F172A", "--tip-border": "#334155", "--tip-color": "#E2E8F0", "--tip-shadow": "0 10px 30px rgba(0,0,0,.45)", "--tip-radius": "10px", "--tip-blur": "0px" } },
  { key: "light", label: "Clara", vars: { "--tip-bg": "#FFFFFF", "--tip-border": "#E2E8F0", "--tip-color": "#1E293B", "--tip-shadow": "0 8px 28px rgba(15,23,42,.14)", "--tip-radius": "10px", "--tip-blur": "0px" } },
  { key: "glass", label: "Vidro", vars: { "--tip-bg": "rgba(15,23,42,.72)", "--tip-border": "rgba(255,255,255,.18)", "--tip-color": "#F1F5F9", "--tip-shadow": "0 12px 36px rgba(0,0,0,.35)", "--tip-radius": "12px", "--tip-blur": "18px" } },
  { key: "accent", label: "Destaque", vars: { "--tip-bg": "#2D3336", "--tip-border": "rgba(255,255,255,.14)", "--tip-color": "#FFFFFF", "--tip-shadow": "0 8px 24px rgba(45,51,54,.40)", "--tip-radius": "9px", "--tip-blur": "0px" } },
];

// ── §5.9 SIDEBAR_THEMES ─────────────────────────────────────────────────
export const SIDEBAR_THEMES: { label: string; value: string }[] = [
  { label: "Padrão", value: "linear-gradient(170deg,#383d41 0%,#2D3336 100%)" },
  { label: "Preto", value: "linear-gradient(170deg,#1A1A1F 0%,#0D0D0D 100%)" },
  { label: "Azul", value: "linear-gradient(170deg,#1E3A5F 0%,#0F2040 100%)" },
  { label: "Slate", value: "linear-gradient(170deg,#1E293B 0%,#0F172A 100%)" },
  { label: "Teal", value: "linear-gradient(170deg,#134E4A 0%,#0D3B36 100%)" },
  { label: "Violeta", value: "linear-gradient(170deg,#312E81 0%,#1E1B4B 100%)" },
  { label: "Cobre", value: "linear-gradient(170deg,#431407 0%,#292524 100%)" },
];

// ── Tipografia / raio / densidade / nav / motion / fundo ────────────────
export const FONT_SIZES: { key: string; label: string; value: string }[] = [
  { key: "pequeno", label: "Pequena", value: "13px" },
  { key: "medio", label: "Média", value: "14px" },
  { key: "grande", label: "Grande", value: "16px" },
];

export const CARD_RADII: { key: string; label: string; value: string }[] = [
  { key: "reto", label: "Reto", value: "4px" },
  { key: "suave", label: "Suave", value: "8px" },
  { key: "medio", label: "Médio", value: "14px" },
  { key: "redondo", label: "Redondo", value: "20px" },
  { key: "circulo", label: "Círculo", value: "28px" },
];

export const DENSITIES: { key: string; label: string }[] = [
  { key: "compact", label: "Compacto" },
  { key: "default", label: "Padrão" },
  { key: "comfortable", label: "Confortável" },
];

export const NAV_WIDTHS: { key: string; label: string; value: string }[] = [
  { key: "compacta", label: "Compacta", value: "220px" },
  { key: "padrao", label: "Padrão", value: "278px" },
  { key: "large", label: "Large", value: "320px" },
];

export const MOTIONS: { key: string; label: string }[] = [
  { key: "off", label: "Desativar" },
  { key: "fast", label: "Rápida" },
  { key: "normal", label: "Normal" },
  { key: "slow", label: "Lenta" },
];

export const BG_LIGHTS: { label: string; value: string }[] = [
  { label: "Pérola", value: "#EBEBEB" },
  { label: "Branco", value: "#F7F8FA" },
  { label: "Bege", value: "#EFEAE2" },
  { label: "Azulado", value: "#E8EDF3" },
];
export const BG_DARKS: { label: string; value: string }[] = [
  { label: "Grafite", value: "#090909" },
  { label: "Petróleo", value: "#0B0F14" },
  { label: "Slate", value: "#0F172A" },
  { label: "Carvão", value: "#141418" },
];

// ── Princípios (texto do painel) ────────────────────────────────────────
export const PRINCIPLES: string[] = [
  "Superfícies em vidro fluido (backdrop blur) com profundidade sem peso visual.",
  "Tokens CSS semânticos — cada cor é uma variável reutilizada em todo o sistema.",
  "Modo claro/escuro via data-theme, com a hierarquia de leitura preservada.",
  "Tipografia Inter/Franklin (display/UI) e SF Mono/Menlo para números.",
  "Movimento opcional e acessível — respeite preferências de redução de animação.",
  "Grade e espaçamento consistentes (densidade configurável).",
];

// ── Estado completo do tema ─────────────────────────────────────────────
export interface ThemeState {
  themeMode: ThemeMode;
  cardStyle: string;
  intensity: string;
  cardLayout: string;
  accent: string;
  fontSize: string;     // valor px
  btnStyle: string;
  modalStyle: string;
  modalBgStyle: string;
  modalBlurPct: number;
  highContrast: boolean;
  chartTheme: string;
  chartPalette: string;
  tooltipStyle: string;
  cardRadius: string;   // valor px
  tableDensity: string;
  bgLight: string;
  bgDark: string;
  navWidth: string;     // valor px
  navBg: string;
  motion: string;
}

export const DEFAULTS: ThemeState = {
  themeMode: "dark",          // VisionDesk: monitoramento de vídeo prefere escuro
  cardStyle: "liquid_glass",
  intensity: "medio",
  cardLayout: "otc",
  accent: "#19C3B2",          // teal nativo
  fontSize: "14px",
  btnStyle: "glass",
  modalStyle: "glass",
  modalBgStyle: "liquid_glass",
  modalBlurPct: 75,
  highContrast: false,
  chartTheme: "padrao_flcx",
  chartPalette: "industrial",
  tooltipStyle: "dark",
  cardRadius: "14px",
  tableDensity: "default",
  bgLight: "#EBEBEB",
  bgDark: "#0B0F14",
  navWidth: "278px",
  navBg: SIDEBAR_THEMES[0].value,
  motion: "normal",
};

export interface SavedTheme {
  id: string;
  name: string;
  state: ThemeState;
}
