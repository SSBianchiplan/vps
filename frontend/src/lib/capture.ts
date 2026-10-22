// Captura um frame do <video> para JPEG base64 (sem prefixo data:),
// reduzindo a resolução de inferência (≠ resolução de preview).

let scratch: HTMLCanvasElement | null = null;

export function captureFrame(video: HTMLVideoElement, maxSide = 960, quality = 0.92): string | null {
  const vw = video.videoWidth;
  const vh = video.videoHeight;
  if (!vw || !vh) return null;

  const scale = Math.min(1, maxSide / Math.max(vw, vh));
  const w = Math.round(vw * scale);
  const h = Math.round(vh * scale);

  if (!scratch) scratch = document.createElement("canvas");
  scratch.width = w;
  scratch.height = h;
  const ctx = scratch.getContext("2d");
  if (!ctx) return null;
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";   // downscale mais nítido (alta resolução)
  ctx.drawImage(video, 0, 0, w, h);
  const dataUrl = scratch.toDataURL("image/jpeg", quality);
  return dataUrl.split(",")[1] ?? null;
}

// ── Detecção de mudança (captura de tela, spec §6) ───────────────────
// Miniatura em escala de cinza p/ comparar frames; processa só quando a tela muda.
let thumbCanvas: HTMLCanvasElement | null = null;

export function frameThumb(video: HTMLVideoElement, w = 48): Uint8Array | null {
  const vw = video.videoWidth, vh = video.videoHeight;
  if (!vw || !vh) return null;
  const h = Math.max(1, Math.round((w * vh) / vw));
  if (!thumbCanvas) thumbCanvas = document.createElement("canvas");
  thumbCanvas.width = w; thumbCanvas.height = h;
  const ctx = thumbCanvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) return null;
  ctx.drawImage(video, 0, 0, w, h);
  const d = ctx.getImageData(0, 0, w, h).data;
  const out = new Uint8Array(w * h);
  for (let i = 0, j = 0; i < d.length; i += 4, j++) out[j] = (d[i] + d[i + 1] + d[i + 2]) / 3;
  return out;
}

/** Diferença média (0..1) entre duas miniaturas. < limiar ⇒ tela não mudou. */
export function thumbDiff(a: Uint8Array, b: Uint8Array): number {
  if (a.length !== b.length || !a.length) return 1;
  let s = 0;
  for (let i = 0; i < a.length; i++) s += Math.abs(a[i] - b[i]);
  return s / a.length / 255;
}
