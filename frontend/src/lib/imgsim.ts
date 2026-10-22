// Simulações de imagem client-side (canvas) para o Estudo de caso:
//  - modalidades de captura (§3.8): térmica, IR, raio-X, profundidade
//  - augmentations p/ dados sintéticos (§3.7)

function load(src: string): Promise<HTMLImageElement> {
  return new Promise((res, rej) => {
    const im = new Image();
    im.onload = () => res(im);
    im.onerror = rej;
    im.src = src;
  });
}

function ctxOf(w: number, h: number): [HTMLCanvasElement, CanvasRenderingContext2D] {
  const cv = document.createElement("canvas");
  cv.width = w; cv.height = h;
  return [cv, cv.getContext("2d")!];
}

export type Modality = "thermal" | "ir" | "xray" | "depth";

export async function applyModality(src: string, kind: Modality, maxW = 480): Promise<string> {
  const im = await load(src);
  const scale = Math.min(1, maxW / im.naturalWidth);
  const w = Math.round(im.naturalWidth * scale), h = Math.round(im.naturalHeight * scale);
  const [cv, ctx] = ctxOf(w, h);
  ctx.drawImage(im, 0, 0, w, h);
  const img = ctx.getImageData(0, 0, w, h);
  const d = img.data;

  if (kind === "depth") {
    // gradiente (Sobel-lite) → pseudo-profundidade
    const gray = new Float32Array(w * h);
    for (let i = 0; i < w * h; i++) gray[i] = 0.299 * d[i * 4] + 0.587 * d[i * 4 + 1] + 0.114 * d[i * 4 + 2];
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      const i = y * w + x;
      const gx = gray[i] - gray[y * w + Math.max(0, x - 1)];
      const gy = gray[i] - gray[Math.max(0, y - 1) * w + x];
      const g = Math.min(255, Math.hypot(gx, gy) * 3);
      d[i * 4] = d[i * 4 + 1] = d[i * 4 + 2] = g;
    }
  } else {
    for (let i = 0; i < d.length; i += 4) {
      const lum = 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2];
      if (kind === "ir") { const v = Math.min(255, lum * 1.25); d[i] = d[i + 1] = d[i + 2] = v; }
      else if (kind === "xray") { const v = 255 - lum; d[i] = d[i + 1] = d[i + 2] = Math.min(255, v * 1.1); }
      else if (kind === "thermal") { // colormap azul→vermelho por luminância
        const t = lum / 255;
        d[i] = Math.min(255, 255 * Math.max(0, 1.5 * t - 0.3));
        d[i + 1] = Math.min(255, 255 * (1 - Math.abs(t - 0.5) * 2));
        d[i + 2] = Math.min(255, 255 * Math.max(0, 1 - 1.5 * t));
      }
    }
  }
  ctx.putImageData(img, 0, 0);
  return cv.toDataURL("image/jpeg", 0.85);
}

export type Aug = "flip" | "bright" | "dark" | "noise" | "rotate";

export async function augment(src: string, kind: Aug, maxW = 320): Promise<string> {
  const im = await load(src);
  const scale = Math.min(1, maxW / im.naturalWidth);
  const w = Math.round(im.naturalWidth * scale), h = Math.round(im.naturalHeight * scale);
  const [cv, ctx] = ctxOf(w, h);
  ctx.save();
  if (kind === "flip") { ctx.translate(w, 0); ctx.scale(-1, 1); }
  if (kind === "rotate") { ctx.translate(w / 2, h / 2); ctx.rotate(0.12); ctx.translate(-w / 2, -h / 2); }
  if (kind === "bright") ctx.filter = "brightness(1.4)";
  if (kind === "dark") ctx.filter = "brightness(0.6)";
  ctx.drawImage(im, 0, 0, w, h);
  ctx.restore();
  if (kind === "noise") {
    const img = ctx.getImageData(0, 0, w, h); const d = img.data;
    for (let i = 0; i < d.length; i += 4) {
      // ruído determinístico (sem Math.random p/ reprodutibilidade)
      const n = (((i * 1103515245 + 12345) >> 8) % 61) - 30;
      d[i] += n; d[i + 1] += n; d[i + 2] += n;
    }
    ctx.putImageData(img, 0, 0);
  }
  return cv.toDataURL("image/jpeg", 0.8);
}

export const AUG_KINDS: Aug[] = ["flip", "bright", "dark", "noise", "rotate"];
export const MODALITIES: { kind: Modality; label: string; reveals: string }[] = [
  { kind: "thermal", label: "Térmica/IR", reveals: "calor, solda, ponto quente" },
  { kind: "ir", label: "Infravermelho", reveals: "visão noturna, baixa luz" },
  { kind: "xray", label: "Raio-X", reveals: "defeito interno, vazio, BGA" },
  { kind: "depth", label: "3D / Depth", reveals: "geometria, dimensional, bin picking" },
];
