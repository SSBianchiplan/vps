import { Children, useState, type ReactNode } from "react";

// Carrossel (Onda 5): visualizador horizontal de cartões/banners.
export function Carousel({ children, height = 160 }: { children: ReactNode; height?: number }) {
  const slides = Children.toArray(children);
  const [i, setI] = useState(0);
  const n = slides.length || 1;
  const go = (d: number) => setI((x) => (x + d + n) % n);
  return (
    <div className="relative rounded-card border border-edge overflow-hidden" style={{ height }}>
      <div className="flex h-full transition-transform duration-300" style={{ transform: `translateX(-${i * 100}%)` }}>
        {slides.map((s, k) => <div key={k} className="w-full h-full shrink-0">{s}</div>)}
      </div>
      {n > 1 && <>
        <button onClick={() => go(-1)} className="absolute left-1 top-1/2 -translate-y-1/2 w-7 h-7 rounded-full bg-black/40 text-white hover:bg-black/60">‹</button>
        <button onClick={() => go(1)} className="absolute right-1 top-1/2 -translate-y-1/2 w-7 h-7 rounded-full bg-black/40 text-white hover:bg-black/60">›</button>
        <div className="absolute bottom-1.5 left-0 right-0 flex justify-center gap-1.5">
          {slides.map((_, k) => <button key={k} onClick={() => setI(k)} className={"w-1.5 h-1.5 rounded-full " + (k === i ? "bg-accent" : "bg-white/50")} />)}
        </div>
      </>}
    </div>
  );
}
