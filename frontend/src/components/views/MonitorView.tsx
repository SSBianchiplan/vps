import { useCallback, useEffect, useRef, useState } from "react";
import {
  getOverview,
  getSeries,
  getSignal,
  type AvailItem,
  type CameraSignal,
  type MetricSample,
  type Overview,
  type Period,
  type SignalStatus,
} from "../../api/monitor";
import { getStreamStats, listSavedCameras, setCameraEnabled } from "../../api/cameras";
import { getAerialStatus, type AerialStatus } from "../../api/aerial";
import { listEvents, type VisionEvent } from "../../api/events";
import { useStore } from "../../store/useStore";

const PERIODS: { key: Period; label: string }[] = [
  { key: "7d", label: "7 D" },
  { key: "30d", label: "30 D" },
  { key: "90d", label: "90 D" },
  { key: "12m", label: "12 M" },
  { key: "tudo", label: "Tudo" },
];

// Dispositivos de stream do sistema (MediaMTX) — monitorados junto às câmeras IP.
const DEVICES = [
  { icon: "🛸", name: "Drone — Visão Aérea", path: "drone_neo2", view: "aerea" as const },
  { icon: "📷", name: "Vídeo Osmo", path: "osmo_pocket", view: "osmo" as const },
];

type Tab = "painel" | "sinal" | "alertas";

// ── Helpers visuais ───────────────────────────────────────────────────────
function Kpi({ label, value, accent, disabled, note, onClick }: {
  label: string; value: string; accent?: string; disabled?: boolean; note?: string; onClick?: () => void;
}) {
  return (
    <button type="button" onClick={onClick} disabled={!onClick}
      className={"text-left bg-panel border border-edge rounded-card p-4 transition-colors " +
        (disabled ? "opacity-50 " : "") + (onClick ? "hover:border-accent cursor-pointer" : "cursor-default")}>
      <div className="flex items-center justify-between">
        <span className="text-[11px] uppercase tracking-wider text-muted">{label}</span>
        {onClick ? <span className="text-accent text-xs">→</span> : <span className="text-muted text-xs" title={note}>ⓘ</span>}
      </div>
      <p className="text-3xl font-extrabold mt-1" style={{ color: accent ?? "var(--text)" }}>{value}</p>
      {note && <p className="text-[10px] text-muted mt-0.5">{note}</p>}
    </button>
  );
}

// KPI de vazão ao vivo (deriva Mbps do total cumulativo dos streams ativos).
function VazaoKpi() {
  const [mbps, setMbps] = useState<number | null>(null);
  const [streams, setStreams] = useState(0);
  const prev = useRef<{ bytes: number; t: number } | null>(null);
  useEffect(() => {
    let on = true;
    const tick = async () => {
      const s = await getStreamStats();
      const t = performance.now();
      if (!on) return;
      setStreams(s.streams);
      const p = prev.current;
      if (p && t > p.t) {
        const rate = ((s.bytes - p.bytes) * 8) / ((t - p.t) / 1000) / 1e6; // Mbps
        setMbps(Math.max(0, rate));
      }
      prev.current = { bytes: s.bytes, t };
    };
    tick(); const id = window.setInterval(tick, 2000); return () => { on = false; window.clearInterval(id); };
  }, []);
  return (
    <Kpi label="Vazão ao vivo" accent="var(--accent)"
      value={mbps == null ? "—" : `${mbps.toFixed(1)} Mb/s`}
      note={`${streams} stream(s) ativo(s)`} />
  );
}

function SignalBars({ bars }: { bars: number }) {
  const color = bars >= 3 ? "var(--ok)" : bars === 2 ? "var(--warn)" : bars === 1 ? "var(--nok)" : "var(--edge)";
  return (
    <span className="flex items-end gap-0.5 h-4">
      {[1, 2, 3, 4].map((i) => (
        <span key={i} className="w-1 rounded-sm" style={{ height: `${i * 25}%`, background: i <= bars ? color : "var(--edge)" }} />
      ))}
    </span>
  );
}

function Meter({ pct, color }: { pct: number; color: string }) {
  return (
    <div className="h-1.5 rounded-full bg-edge overflow-hidden">
      <div className="h-full rounded-full transition-all" style={{ width: `${Math.max(2, Math.min(100, pct))}%`, background: color }} />
    </div>
  );
}

// Botão liga/desliga (raiz). Reflete em todo o sistema.
function PowerBtn({ enabled, onToggle }: { enabled: boolean; onToggle: () => void }) {
  return (
    <button onClick={(e) => { e.stopPropagation(); onToggle(); }}
      title={enabled ? "Desligar câmera (todo o sistema)" : "Ligar câmera"}
      className={"w-7 h-7 grid place-items-center rounded border text-xs shrink-0 transition-colors " +
        (enabled ? "border-ok/50 text-ok hover:bg-ok/10" : "border-edge text-muted hover:border-accent")}>
      ⏻
    </button>
  );
}

function CameraSignalCard({ c, onOpen, onToggle }: { c: CameraSignal; onOpen: () => void; onToggle: () => void }) {
  const enabled = c.enabled !== false;
  return (
    <div className="bg-panel border border-edge rounded-card p-3">
      <div className="flex items-center gap-2 mb-2">
        <span className={"w-2 h-2 rounded-full " + (!enabled ? "bg-muted" : c.online ? "bg-ok" : "bg-nok")} />
        <button onClick={onOpen} className="text-sm font-medium truncate flex-1 text-left hover:text-accent" title={c.name}>{c.name}</button>
        {!enabled ? <span className="text-[10px] text-muted">○ desligada</span> : <SignalBars bars={c.bars} />}
        <PowerBtn enabled={enabled} onToggle={onToggle} />
      </div>
      <div className={"grid grid-cols-3 gap-2 text-center mb-2 " + (enabled ? "" : "opacity-40")}>
        <div><p className="text-lg font-bold text-text">{c.latency_ms ?? "—"}<span className="text-[10px] text-muted">ms</span></p><p className="text-[10px] text-muted">latência</p></div>
        <div><p className="text-lg font-bold text-text">{c.jitter_ms}<span className="text-[10px] text-muted">ms</span></p><p className="text-[10px] text-muted">jitter</p></div>
        <div><p className="text-lg font-bold text-text">{c.packet_loss_pct}<span className="text-[10px] text-muted">%</span></p><p className="text-[10px] text-muted">perda</p></div>
      </div>
      <div className={"space-y-1.5 " + (enabled ? "" : "opacity-40")}>
        <div className="flex items-center justify-between text-[10px] text-muted"><span>Buffer do sinal (est.)</span><span>{c.buffer_pct}%</span></div>
        <Meter pct={c.buffer_pct} color={c.buffer_pct > 70 ? "var(--nok)" : c.buffer_pct > 40 ? "var(--warn)" : "var(--ok)"} />
        <div className="flex items-center justify-between text-[10px] text-muted pt-0.5">
          <span>{enabled ? c.quality : "desligada"}</span>
          <span>~{c.fps_est} fps</span>
        </div>
      </div>
    </div>
  );
}

// Card de dispositivo de stream (drone/osmo) — status ao vivo via MediaMTX.
function DeviceSignalCard({ icon, name, path, view }: { icon: string; name: string; path: string; view: "aerea" | "osmo" }) {
  const setView = useStore((s) => s.setView);
  const [st, setSt] = useState<AerialStatus | null>(null);
  useEffect(() => {
    let on = true;
    const tick = () => getAerialStatus(path).then((s) => on && setSt(s)).catch(() => undefined);
    tick(); const id = window.setInterval(tick, 4000); return () => { on = false; window.clearInterval(id); };
  }, [path]);
  const online = !!st?.online;
  return (
    <button onClick={() => setView(view)} className="bg-panel border border-edge rounded-card p-3 text-left hover:border-accent transition-colors">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-lg">{icon}</span>
        <span className="text-sm font-medium truncate flex-1" title={name}>{name}</span>
        <span className={"w-2 h-2 rounded-full " + (online ? "bg-ok" : "bg-muted")} />
      </div>
      <div className="flex items-center justify-between text-[11px] text-muted">
        <span>{online ? "● transmitindo" : "○ offline"}</span>
        <span>{st?.readers ? `${st.readers} leitor(es)` : "abrir →"}</span>
      </div>
    </button>
  );
}

// Card "este dispositivo" — câmera local (getUserMedia) do navegador atual.
function LocalDeviceCard() {
  const stream = useStore((s) => s.activeStream);
  const setView = useStore((s) => s.setView);
  const online = !!stream;
  return (
    <button onClick={() => setView("painel")} className="bg-panel border border-edge rounded-card p-3 text-left hover:border-accent transition-colors">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-lg">💻</span>
        <span className="text-sm font-medium truncate flex-1">Este dispositivo</span>
        <span className={"w-2 h-2 rounded-full " + (online ? "bg-ok" : "bg-muted")} />
      </div>
      <div className="flex items-center justify-between text-[11px] text-muted">
        <span>{online ? "● câmera ativa" : "○ câmera fechada"}</span>
        <span>abrir →</span>
      </div>
    </button>
  );
}

// ── Gráficos (consomem tokens --chart-*) ──────────────────────────────────
function AvailabilityChart({ data, onChanged }: { data: AvailItem[]; onChanged: () => void }) {
  const setView = useStore((s) => s.setView);
  const setDetail = useStore((s) => s.setDetailCameraId);
  const setSaved = useStore((s) => s.setSavedCameras);
  const open = (id: string | null) => { if (id) { setDetail(id); setView("cameras"); } };
  const toggle = async (id: string | null, enabled: boolean) => {
    if (!id) return;
    await setCameraEnabled(id, !enabled);
    setSaved(await listSavedCameras());
    onChanged();
  };
  return (
    <div className="rounded-card border border-edge p-3" style={{ background: "var(--chart-bg)" }}>
      <p className="text-xs font-semibold mb-2" style={{ color: "var(--chart-axis)" }}>Disponibilidade das câmeras</p>
      {data.length === 0 ? (
        <p className="text-xs text-muted">Sem câmeras.</p>
      ) : (
        <div className="space-y-2">
          {data.map((c, i) => {
            const pct = c.enabled ? (c.online ? Math.round((c.bars / 4) * 100) : 0) : 0;
            const barColor = !c.enabled ? "var(--chart-grid)" : c.online ? `var(--chart-c${(i % 6) + 1})` : "var(--nok)";
            const right = !c.enabled ? "desligada" : c.online ? `${pct}%` : "offline";
            return (
              <div key={c.name} className="flex items-center gap-2">
                <button onClick={() => open(c.id)} className="text-[10px] w-28 truncate text-left hover:text-accent"
                  style={{ color: "var(--chart-axis)" }} title={c.name}>{c.name}</button>
                <div className="flex-1 h-3 rounded" style={{ background: "var(--chart-grid)" }}>
                  <div className="h-full rounded transition-all" style={{ width: `${Math.max(2, pct)}%`, background: barColor }} />
                </div>
                <span className="text-[10px] w-12 text-right" style={{ color: c.enabled ? "var(--chart-axis)" : "var(--muted)" }}>{right}</span>
                <PowerBtn enabled={c.enabled} onToggle={() => toggle(c.id, c.enabled)} />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function EventsChart({ data }: { data: { day: string; count: number }[] }) {
  const max = Math.max(1, ...data.map((d) => d.count));
  return (
    <div className="rounded-card border border-edge p-3" style={{ background: "var(--chart-bg)" }}>
      <p className="text-xs font-semibold mb-2" style={{ color: "var(--chart-axis)" }}>Eventos por período</p>
      {data.length === 0 ? (
        <p className="text-xs text-muted">Sem eventos no período.</p>
      ) : (
        <div className="flex items-end gap-0.5 h-32">
          {data.map((d) => (
            <div key={d.day} className="flex-1 min-w-[2px] rounded-t" title={`${d.day}: ${d.count}`}
              style={{ height: `${(d.count / max) * 100}%`, minHeight: 2, background: "var(--chart-c3)" }} />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Gráfico de rede em tempo real (latência/jitter/buffer/throughput) ──────
function poly(vals: (number | null)[], w: number, h: number, max: number): string {
  const n = vals.length;
  if (n < 2 || max <= 0) return "";
  return vals.map((v, i) => {
    const x = (i / (n - 1)) * w;
    const y = h - (Math.max(0, Math.min(max, v ?? 0)) / max) * h;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
}

function movingAvg(vals: (number | null)[], win = 7): (number | null)[] {
  const r = Math.floor(win / 2);
  return vals.map((_, i) => {
    let sum = 0, c = 0;
    for (let j = i - r; j <= i + r; j++) {
      const v = vals[j];
      if (j >= 0 && j < vals.length && v != null) { sum += v; c++; }
    }
    return c ? sum / c : null;
  });
}

const SERIES_DEF = [
  { key: "latency_ms", label: "Latência", unit: "ms", color: "var(--chart-c1)" },
  { key: "jitter_ms", label: "Jitter", unit: "ms", color: "var(--chart-c2)" },
  { key: "buffer_pct", label: "Buffer", unit: "%", color: "var(--chart-c4)" },
  { key: "throughput_kbps", label: "Throughput", unit: "kB/s", color: "var(--chart-c3)" },
] as const;

function RealtimeNetChart({ pin }: { pin?: string }) {
  const saved = useStore((s) => s.savedCameras);
  const [samples, setSamples] = useState<MetricSample[]>([]);
  const [src, setSrc] = useState<string>("");
  const [metric, setMetric] = useState<"todos" | (typeof SERIES_DEF)[number]["key"]>("todos");

  useEffect(() => {
    const load = () => getSeries(pin || src || undefined, 240).then((r) => setSamples(r.samples)).catch(() => undefined);
    load(); const id = window.setInterval(load, 3000); return () => window.clearInterval(id);
  }, [src, pin]);

  const nameOf = (id: string) => saved.find((c) => c.ip === id)?.name ?? id;
  const sources = Array.from(new Set(samples.map((s) => s.source_id)));
  const cur = pin || src || sources[0] || "";
  const series = samples.filter((s) => !cur || s.source_id === cur);
  const W = 600, H = 120;
  const showAll = metric === "todos";
  const active = showAll ? SERIES_DEF : SERIES_DEF.filter((d) => d.key === metric);

  const lineFor = (d: (typeof SERIES_DEF)[number]) => {
    const vals = series.map((s) => s[d.key] as number | null);
    const nums = vals.filter((v): v is number => v != null);
    const max = Math.max(1, ...nums) * 1.15;
    const last = nums.length ? nums[nums.length - 1] : null;
    const avg = nums.length ? nums.reduce((a, b) => a + b, 0) / nums.length : null;
    return { d, vals, nums, max, last, avg };
  };
  const lines = active.map(lineFor);
  const enough = lines.some((l) => l.nums.length >= 2);

  return (
    <div className="rounded-card border border-edge p-3" style={{ background: "var(--chart-bg)" }}>
      <div className="flex items-center gap-2 mb-2 flex-wrap">
        <p className="text-xs font-semibold" style={{ color: "var(--chart-axis)" }}>📈 Rede & buffer em tempo real</p>
        <span className="flex items-center gap-1 ml-1"><span className="w-1.5 h-1.5 rounded-full bg-ok animate-pulse" /><span className="text-[10px] text-muted">ao vivo · 3s</span></span>
        <div className="ml-auto flex gap-1 flex-wrap items-center">
          {!pin && (
            <select className="bg-edge border border-edge rounded px-1.5 py-0.5 text-[11px]" value={cur} onChange={(e) => setSrc(e.target.value)}>
              {sources.length === 0 && <option value="">—</option>}
              {sources.map((s) => <option key={s} value={s}>{nameOf(s)}</option>)}
            </select>
          )}
          <button onClick={() => setMetric("todos")}
            className={"px-2 py-0.5 rounded text-[10px] border font-semibold " + (showAll ? "border-accent text-accent bg-accent/10" : "border-edge text-muted")}>
            Todos
          </button>
          {SERIES_DEF.map((d) => (
            <button key={d.key} onClick={() => setMetric(d.key)}
              className={"px-2 py-0.5 rounded text-[10px] border " + (metric === d.key ? "border-accent text-accent" : "border-edge text-muted")}>
              {d.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-3 mb-1 flex-wrap">
        {lines.map((l) => (
          <span key={l.d.key} className="flex items-center gap-1.5">
            <span className="w-2.5 h-0.5 rounded" style={{ background: l.d.color }} />
            <span className="text-[11px] text-muted">{l.d.label}</span>
            <span className="text-sm font-bold" style={{ color: l.d.color }}>{l.last != null ? l.last.toFixed(1) : "—"}<span className="text-[10px] text-muted font-normal"> {l.d.unit}</span></span>
          </span>
        ))}
        <span className="text-[11px] text-muted ml-auto">{series.length} amostras · {cur ? nameOf(cur) : "—"}</span>
      </div>

      {!enough ? (
        <p className="text-xs text-muted py-6 text-center">Coletando amostras… (abra a aba Sinal p/ gerar medições)</p>
      ) : (
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: 130 }} preserveAspectRatio="none">
          {[0.25, 0.5, 0.75].map((g) => <line key={g} x1={0} x2={W} y1={H * g} y2={H * g} stroke="var(--chart-grid)" strokeWidth={0.5} />)}
          {lines.map((l) => <polyline key={l.d.key + "-t"} points={poly(movingAvg(l.vals), W, H, l.max)} fill="none" stroke={l.d.color} strokeOpacity={0.3} strokeWidth={4} strokeLinecap="round" />)}
          {lines.map((l) => <polyline key={l.d.key} points={poly(l.vals, W, H, l.max)} fill="none" stroke={l.d.color} strokeWidth={1.5} />)}
        </svg>
      )}
      {showAll && <p className="text-[10px] text-muted mt-1">Linha sólida = valor instantâneo · faixa translúcida (mesma cor) = tendência/média móvel. Cada métrica normalizada ao próprio máximo (ms, %, kB/s).</p>}
      {!showAll && lines[0] && <p className="text-[10px] text-muted mt-1">Sólida = instantâneo · translúcida = tendência (média móvel ~{lines[0].avg != null ? lines[0].avg.toFixed(1) : "—"} {lines[0].d.unit}).</p>}
    </div>
  );
}

// Dispositivos & streams do sistema (drone/osmo/este dispositivo).
function DevicesSection() {
  return (
    <section>
      <div className="flex items-center gap-2 mb-2">
        <h3 className="text-xs uppercase tracking-wider text-muted">Dispositivos & streams</h3>
        <span className="text-[10px] text-muted">status ao vivo</span>
      </div>
      <div className="grid gap-3 grid-cols-1 sm:grid-cols-3">
        <LocalDeviceCard />
        {DEVICES.map((d) => <DeviceSignalCard key={d.path} {...d} />)}
      </div>
    </section>
  );
}

// ── View ──────────────────────────────────────────────────────────────────
export function MonitorView() {
  const saved = useStore((s) => s.savedCameras);
  const [period, setPeriod] = useState<Period>("12m");
  const [tab, setTab] = useState<Tab>("painel");
  const [camFilter, setCamFilter] = useState<string>("");   // "" = todas (valor = ip)
  const [ov, setOv] = useState<Overview | null>(null);
  const [sig, setSig] = useState<SignalStatus | null>(null);

  const loadOv = useCallback(() => getOverview(period).then(setOv).catch(() => undefined), [period]);
  useEffect(() => { loadOv(); const id = window.setInterval(loadOv, 12000); return () => window.clearInterval(id); }, [loadOv]);
  useEffect(() => {
    const load = () => getSignal().then(setSig).catch(() => undefined);
    load(); const id = window.setInterval(load, 6000); return () => window.clearInterval(id);
  }, []);

  const k = ov?.kpis;
  const avail = (ov?.availability_series ?? []).filter((c) => !camFilter || c.host === camFilter);
  const filterName = saved.find((c) => c.ip === camFilter)?.name;

  return (
    <div className="flex flex-col gap-3 min-h-full">
      {/* Cabeçalho do módulo + tabs */}
      <div className="flex items-center gap-3 flex-wrap border-b border-edge pb-2">
        <h2 className="text-base font-bold flex items-center gap-2">📶 Monitoramento do Sistema <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent/15 text-accent">IoT</span></h2>
        <div className="ml-auto flex gap-1">
          {([["painel", "Painel"], ["sinal", "Sinal"], ["alertas", `Alertas${k ? ` (${k.alertas_detectados})` : ""}`]] as [Tab, string][]).map(([key, label]) => (
            <button key={key} onClick={() => setTab(key)}
              className={"px-3 py-1.5 text-sm rounded-card border-b-2 transition-colors " +
                (tab === key ? "border-accent text-accent" : "border-transparent text-muted hover:text-text")}>
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Período + filtro de câmera */}
      <div className="flex items-center gap-2 flex-wrap text-xs">
        <span className="text-muted uppercase tracking-wider">Período</span>
        <div className="flex rounded-card border border-edge overflow-hidden">
          {PERIODS.map((p) => (
            <button key={p.key} onClick={() => setPeriod(p.key)}
              className={"px-3 py-1.5 transition-colors " + (period === p.key ? "bg-accent text-onaccent" : "bg-edge text-muted hover:text-text")}>
              {p.label}
            </button>
          ))}
        </div>
        <span className="text-muted ml-1">· Câmera</span>
        <select value={camFilter} onChange={(e) => setCamFilter(e.target.value)}
          className="bg-edge border border-edge rounded px-2 py-1 text-xs">
          <option value="">Todas</option>
          {saved.map((c) => <option key={c.id} value={c.ip}>{c.name}</option>)}
        </select>
      </div>

      <div className="flex-1 scroll-thin space-y-4 pr-1">
        {/* KPIs (sempre visíveis) */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <Kpi label="Disponib. média" accent="var(--ok)"
            value={k ? (k.disponibilidade_media == null ? "—" : `${k.disponibilidade_media}%`) : "—"}
            note="câmeras ligadas alcançáveis" />
          <Kpi label="Câmeras online" accent="var(--text)"
            value={k ? `${k.cameras_online}/${k.cameras_enabled}` : "—"}
            note={k ? `${k.cameras} salvas no total` : "salvas/monitoradas"}
            onClick={() => useStore.getState().setView("cameras")} />
          <VazaoKpi />
          <Kpi label="Alertas detectados" accent="var(--warn)"
            value={k ? String(k.alertas_detectados) : "—"} note="no período · ver detalhe"
            onClick={() => setTab("alertas")} />
        </div>

        {tab === "painel" && (
          <>
            <RealtimeNetChart pin={camFilter || undefined} />
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              <AvailabilityChart data={avail} onChanged={loadOv} />
              <EventsChart data={ov?.events_by_day ?? []} />
            </div>
            <DevicesSection />
          </>
        )}

        {tab === "sinal" && (
          <>
            <RealtimeNetChart pin={camFilter || undefined} />
            <DevicesSection />
            <SignalSection sig={sig} camFilter={camFilter} filterName={filterName} onChanged={loadOv} full />
          </>
        )}

        {tab === "alertas" && <AlertsTab camFilter={camFilter} />}
      </div>
    </div>
  );
}

function SignalSection({ sig, camFilter, filterName, onChanged, full }: {
  sig: SignalStatus | null; camFilter: string; filterName?: string; onChanged: () => void; full?: boolean;
}) {
  const wifi = sig?.wifi;
  const setView = useStore((s) => s.setView);
  const setDetail = useStore((s) => s.setDetailCameraId);
  const setSaved = useStore((s) => s.setSavedCameras);
  const cams = (sig?.cameras ?? []).filter((c) => !camFilter || c.host === camFilter);
  const open = (id?: string | null) => { if (id) { setDetail(id); setView("cameras"); } };
  const toggle = async (host: string, enabled: boolean) => {
    const cam = useStore.getState().savedCameras.find((s) => s.ip === host);
    if (!cam) return;
    await setCameraEnabled(cam.id, !enabled);
    setSaved(await listSavedCameras());
    onChanged();
  };
  const idOf = (host: string) => useStore.getState().savedCameras.find((s) => s.ip === host)?.id ?? null;

  return (
    <section>
      <div className="flex items-center gap-2 mb-2">
        <h3 className="text-xs uppercase tracking-wider text-muted">Sinal de transmissão (Wi-Fi)</h3>
        <span className="text-[10px] text-muted">leitura ao vivo · latência/jitter/buffer{filterName ? ` · ${filterName}` : ""}</span>
      </div>

      <div className="bg-panel border border-edge rounded-card p-3 mb-3 flex items-center gap-3 flex-wrap">
        <span className="text-lg">📡</span>
        {wifi?.available ? (
          <>
            <span className="text-sm font-medium">{wifi.ssid ?? "Wi-Fi local"}</span>
            <SignalBars bars={wifi.bars ?? 0} />
            <span className="text-xs text-muted">RSSI {wifi.rssi_dbm} dBm · SNR {wifi.snr_db} dB{wifi.tx_rate_mbps ? ` · ${wifi.tx_rate_mbps} Mbps` : ""}</span>
          </>
        ) : (
          <span className="text-xs text-muted">Wi-Fi local: leitura de RSSI indisponível neste host (sem permissão/airport). O sinal por câmera abaixo é medido pelo enlace real.</span>
        )}
      </div>

      <div className={"grid gap-3 " + (full ? "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3" : "grid-cols-1 sm:grid-cols-2")}>
        {cams.map((c) => <CameraSignalCard key={c.host} c={c} onOpen={() => open(idOf(c.host))} onToggle={() => toggle(c.host, c.enabled !== false)} />)}
        {cams.length === 0 && (
          <div className="text-xs text-muted col-span-full">{camFilter ? "Câmera filtrada sem medição." : "Nenhuma câmera salva para medir sinal."}</div>
        )}
      </div>
    </section>
  );
}

function AlertsTab({ camFilter }: { camFilter: string }) {
  const setView = useStore((s) => s.setView);
  const [items, setItems] = useState<VisionEvent[]>([]);
  useEffect(() => {
    listEvents({ limit: 200 })
      .then((evs) => setItems(evs.filter((e) => e.severidade === "alerta" || e.severidade === "nok")))
      .catch(() => undefined);
  }, []);
  // filtro por câmera: source_id == "cam:<id>" ou label contendo o host
  const saved = useStore((s) => s.savedCameras);
  const cam = saved.find((c) => c.ip === camFilter);
  const shown = items.filter((a) => !cam || a.source_id === `cam:${cam.id}` || a.source_label?.includes(cam.name));

  return (
    <section>
      <div className="flex items-center gap-2 mb-2">
        <h3 className="text-xs uppercase tracking-wider text-muted">Alertas recentes {shown.length ? `(${shown.length})` : ""}</h3>
        <button onClick={() => setView("eventos")} className="ml-auto text-xs text-accent hover:underline">ver todos →</button>
      </div>
      {shown.length === 0 ? (
        <p className="text-xs text-muted">Sem alertas no momento.</p>
      ) : (
        <div className="space-y-1.5">
          {shown.map((a) => (
            <button key={a.detection_id} onClick={() => setView("eventos")}
              className="w-full flex items-start gap-2 text-xs bg-panel border border-edge rounded-card p-2 text-left hover:border-accent transition-colors">
              <span className={"w-2 h-2 rounded-full mt-1 shrink-0 " + (a.severidade === "nok" ? "bg-nok" : "bg-warn")} />
              <p className="flex-1 text-text">{a.source_label} — {a.titulo}</p>
              <span className="text-muted whitespace-nowrap">{new Date(a.timestamp).toLocaleString()}</span>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
