import { useEffect, useRef } from "react";
import type { RefObject } from "react";
import { useStore } from "../store/useStore";
import type { Point, ROI } from "../types";

type Media = HTMLVideoElement | HTMLImageElement;

interface Props {
  mediaRef: RefObject<Media>;
}

interface Pending {
  dragStart: Point | null;
  preview: Point | null;
  zonePts: Point[];
}

function intrinsicSize(el: Media): [number, number] {
  const v = el as HTMLVideoElement;
  if (v.videoWidth && v.videoHeight) return [v.videoWidth, v.videoHeight];
  const i = el as HTMLImageElement;
  return [i.naturalWidth || 0, i.naturalHeight || 0];
}

export function CanvasOverlay({ mediaRef }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const pending = useRef<Pending>({ dragStart: null, preview: null, zonePts: [] });
  const drawActive = useStore((s) => s.draw); // re-render do cursor

  useEffect(() => {
    const canvas = canvasRef.current;
    const media = mediaRef.current;
    if (!canvas || !media) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let raf = 0;

    // Retângulo do CONTEÚDO (object-contain): a mídia é letterboxed dentro do box.
    const contentRect = () => {
      const ew = canvas.clientWidth;
      const eh = canvas.clientHeight;
      const [vw, vh] = intrinsicSize(media);
      if (!vw || !vh) return { ox: 0, oy: 0, cw: ew, ch: eh };
      const scale = Math.min(ew / vw, eh / vh);
      const cw = vw * scale;
      const ch = vh * scale;
      return { ox: (ew - cw) / 2, oy: (eh - ch) / 2, cw, ch };
    };

    const norm = (e: PointerEvent | MouseEvent): Point => {
      const r = canvas.getBoundingClientRect();
      const { ox, oy, cw, ch } = contentRect();
      const x = (e.clientX - r.left - ox) / (cw || 1);
      const y = (e.clientY - r.top - oy) / (ch || 1);
      return [Math.min(1, Math.max(0, x)), Math.min(1, Math.max(0, y))];
    };

    const px = (p: Point): [number, number] => {
      const { ox, oy, cw, ch } = contentRect();
      return [ox + p[0] * cw, oy + p[1] * ch];
    };

    const commit = (roi: ROI) => {
      const draw = useStore.getState().draw;
      if (!draw) return;
      if (draw.target === "counting") useStore.getState().setCountingRoi(roi);
      else useStore.getState().setRoi(roi);
      useStore.getState().setDraw(null);
      pending.current = { dragStart: null, preview: null, zonePts: [] };
    };

    const onDown = (e: PointerEvent) => {
      const draw = useStore.getState().draw;
      if (!draw) return;
      canvas.setPointerCapture?.(e.pointerId);
      const p = norm(e);
      if (draw.shape === "zone") {
        pending.current.zonePts.push(p);
        pending.current.preview = p;
      } else {
        pending.current.dragStart = p;
        pending.current.preview = p;
      }
    };
    const onMove = (e: PointerEvent) => {
      if (!useStore.getState().draw) return;
      pending.current.preview = norm(e);
    };
    const onUp = (e: PointerEvent) => {
      const draw = useStore.getState().draw;
      canvas.releasePointerCapture?.(e.pointerId);
      if (!draw) return;
      const end = norm(e);
      const start = pending.current.dragStart;
      if (draw.shape === "rect" && start) {
        const x = Math.min(start[0], end[0]);
        const y = Math.min(start[1], end[1]);
        const w = Math.abs(end[0] - start[0]);
        const h = Math.abs(end[1] - start[1]);
        if (w > 0.01 && h > 0.01) commit({ shape: "rect", points: [[x, y], [w, h]] });
      } else if (draw.shape === "line" && start) {
        commit({ shape: "line", points: [start, end] });
      }
      pending.current.dragStart = null;
    };
    const onDbl = () => {
      const draw = useStore.getState().draw;
      if (draw?.shape === "zone" && pending.current.zonePts.length >= 3) {
        commit({ shape: "zone", points: [...pending.current.zonePts] });
      }
    };

    canvas.addEventListener("pointerdown", onDown);
    canvas.addEventListener("pointermove", onMove);
    canvas.addEventListener("pointerup", onUp);
    canvas.addEventListener("dblclick", onDbl);

    function rect(b: number[], color: string, label?: string) {
      const [x, y, w, h] = b;
      const [sx, sy] = px([x, y]);
      const { cw, ch } = contentRect();
      ctx!.strokeStyle = color;
      ctx!.lineWidth = 2;
      ctx!.strokeRect(sx, sy, w * cw, h * ch);
      if (label) {
        ctx!.font = "12px ui-sans-serif, system-ui";
        const tw = ctx!.measureText(label).width + 8;
        ctx!.fillStyle = color;
        ctx!.fillRect(sx, sy - 16, tw, 16);
        ctx!.fillStyle = "#0b0f14";
        ctx!.fillText(label, sx + 4, sy - 4);
      }
    }
    function line(pts: Point[], color: string) {
      if (pts.length < 2) return;
      ctx!.strokeStyle = color;
      ctx!.lineWidth = 2;
      ctx!.beginPath();
      const [x0, y0] = px(pts[0]);
      ctx!.moveTo(x0, y0);
      for (const p of pts.slice(1)) {
        const [x, y] = px(p);
        ctx!.lineTo(x, y);
      }
      ctx!.stroke();
    }
    function polygon(pts: Point[], color: string) {
      if (pts.length < 2) return;
      line([...pts, pts[0]], color);
    }

    function drawRoi(roi: ROI | null, color: string) {
      if (!roi || roi.points.length === 0) return;
      if (roi.shape === "rect" && roi.points.length >= 2) {
        rect([roi.points[0][0], roi.points[0][1], roi.points[1][0], roi.points[1][1]], color);
      } else if (roi.shape === "line") {
        line(roi.points, color);
      } else {
        polygon(roi.points, color);
      }
    }

    const render = () => {
      const w = media.clientWidth;
      const h = media.clientHeight;
      if (w && h && (canvas.width !== w || canvas.height !== h)) {
        canvas.width = w;
        canvas.height = h;
      }
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const st = useStore.getState();
      drawRoi(st.roi, "#f5a623");
      const countingRoi = st.mode === "RASTREAR" ? st.params.RASTREAR.counting_roi : st.params.CONTAR.counting_roi;
      drawRoi(countingRoi, "#3da9fc");

      const res = st.lastResult;
      if (res) {
        if (res.mode === "RASTREAR") {
          // trajetórias (caminho de cada track) — fluxo observado
          for (const t of res.result.trajectories ?? []) {
            if ((t.points?.length ?? 0) > 1) line(t.points as Point[], "#9b5de5");
          }
          for (const d of res.result.detections ?? []) {
            rect(d.bbox, "#2ecc71", `${d.classe}${d.track_id != null ? " T-" + d.track_id : ""}`);
          }
        } else if (res.mode === "CONTAR" || res.mode === "DETECTAR") {
          for (const d of res.result.detections ?? []) {
            const lbl = `${d.classe}${d.track_id != null ? " #" + d.track_id : ""} ${Math.round(
              d.confianca * 100,
            )}%`;
            rect(d.bbox, "#2ecc71", lbl);
          }
        } else if (res.mode === "LER") {
          for (const l of res.result.leituras ?? []) {
            if (!l.bbox) continue;
            const color = l.valido === false ? "#ff5c5c" : "#3da9fc";
            rect(l.bbox, color, l.texto);
          }
        }
      }

      const draw = st.draw;
      const pd = pending.current;
      if (draw) {
        if (draw.shape === "rect" && pd.dragStart && pd.preview) {
          const x = Math.min(pd.dragStart[0], pd.preview[0]);
          const y = Math.min(pd.dragStart[1], pd.preview[1]);
          rect([x, y, Math.abs(pd.preview[0] - pd.dragStart[0]), Math.abs(pd.preview[1] - pd.dragStart[1])], "#ffffff");
        } else if (draw.shape === "line" && pd.dragStart && pd.preview) {
          line([pd.dragStart, pd.preview], "#ffffff");
        } else if (draw.shape === "zone" && pd.zonePts.length) {
          line(pd.preview ? [...pd.zonePts, pd.preview] : pd.zonePts, "#ffffff");
        }
      }

      raf = requestAnimationFrame(render);
    };
    raf = requestAnimationFrame(render);

    return () => {
      cancelAnimationFrame(raf);
      canvas.removeEventListener("pointerdown", onDown);
      canvas.removeEventListener("pointermove", onMove);
      canvas.removeEventListener("pointerup", onUp);
      canvas.removeEventListener("dblclick", onDbl);
    };
  }, [mediaRef]);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 w-full h-full"
      style={{ cursor: drawActive ? "crosshair" : "default", touchAction: "none" }}
    />
  );
}
