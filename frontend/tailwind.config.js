/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      // Tokens semânticos → CSS variables (escritas pelo theme engine /theme/engine.ts).
      // Cores "sólidas" usam canais RGB (var(--x-rgb)) + <alpha-value> para que
      // modificadores de opacidade do Tailwind (ex. bg-accent/20) funcionem.
      // bg/panel/surface ficam como cor cheia (podem ser rgba/translúcidas).
      colors: {
        bg: "var(--bg)",
        panel: "var(--panel)",
        surface: "var(--surface)",
        edge: "rgb(var(--edge-rgb) / <alpha-value>)",
        text: "rgb(var(--text-rgb) / <alpha-value>)",
        muted: "rgb(var(--muted-rgb) / <alpha-value>)",
        accent: "rgb(var(--accent-rgb) / <alpha-value>)",
        "accent-2": "rgb(var(--accent2-rgb) / <alpha-value>)",
        ok: "rgb(var(--ok-rgb) / <alpha-value>)",
        nok: "rgb(var(--nok-rgb) / <alpha-value>)",
        warn: "rgb(var(--warn-rgb) / <alpha-value>)",
        onaccent: "var(--on-accent)",
        ink: "var(--on-accent)", // texto sobre acento → contraste calculado pelo engine
      },
      borderRadius: {
        card: "var(--radius)",
      },
      transitionDuration: {
        theme: "180ms",
      },
    },
  },
  plugins: [],
};
