// Classes Tailwind reutilizadas pelos formulários/controles.

export const labelCls = "block text-xs font-medium text-muted mb-1";
export const inputCls =
  "w-full bg-edge border border-edge rounded px-2 py-1.5 text-sm text-text " +
  "focus:outline-none focus:border-accent";
export const selectCls = inputCls + " appearance-none";
export const btnCls =
  "px-3 py-1.5 rounded text-sm font-medium border border-edge bg-edge " +
  "hover:border-accent transition-colors disabled:opacity-40 disabled:cursor-not-allowed";
export const btnPrimaryCls =
  "px-3 py-1.5 rounded text-sm font-semibold bg-accent text-onaccent hover:brightness-110 " +
  "transition disabled:opacity-40 disabled:cursor-not-allowed";

export function csvToList(s: string): string[] {
  return s
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);
}

export function linesToList(s: string): string[] {
  return s
    .split("\n")
    .map((x) => x.trim())
    .filter(Boolean);
}
