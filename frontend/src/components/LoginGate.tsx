import { useEffect, useRef, useState } from "react";
import { useStore } from "../store/useStore";
import { authState, bootstrap, loginFace, loginPin } from "../api/auth";
import { captureFrame } from "../lib/capture";
import { btnPrimaryCls, inputCls } from "../lib/ui";

const SCAN_CSS = `
@keyframes vdpulse{0%,100%{opacity:.45}50%{opacity:.12}}
@keyframes vdscan{0%{top:14%}50%{top:80%}100%{top:14%}}
.vd-ring{animation:vdpulse 1.8s ease-in-out infinite}
.vd-scan{animation:vdscan 2.1s ease-in-out infinite}
`;
const ghostBtn = "w-full px-3 py-2.5 rounded-card border border-edge text-sm font-semibold hover:border-accent transition-colors disabled:opacity-40";

/** Login do sistema (padrão landing) — FaceID (câmera, auto), PIN/crachá ou bootstrap. */
export function LoginGate() {
  const setAuth = useStore((s) => s.setAuth);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [needBoot, setNeedBoot] = useState<boolean | null>(null);
  const [mode, setMode] = useState<"face" | "pin">("face");
  const [camOn, setCamOn] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [name, setName] = useState("");
  const [pin, setPin] = useState("");
  const [opId, setOpId] = useState("");

  const startCam = async () => {
    if (streamRef.current) return;
    setMsg("");
    try {
      let s: MediaStream;
      try { s = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false }); }
      catch { s = await navigator.mediaDevices.getUserMedia({ video: true, audio: false }); }
      streamRef.current = s; setCamOn(true);
    } catch {
      setMsg(window.isSecureContext === false ? "Câmera exige HTTPS/localhost — use PIN." : "Sem acesso à câmera — use PIN.");
    }
  };
  const stopCam = () => { streamRef.current?.getTracks().forEach((t) => t.stop()); streamRef.current = null; setCamOn(false); };

  useEffect(() => {
    authState().then((s) => { setNeedBoot(s.bootstrap_needed); if (!s.bootstrap_needed) void startCam(); }).catch(() => setNeedBoot(false));
    return () => { streamRef.current?.getTracks().forEach((t) => t.stop()); streamRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    const v = videoRef.current;
    if (camOn && v && streamRef.current) { v.srcObject = streamRef.current; v.play().catch(() => undefined); }
  }, [camOn, mode]);

  const doFace = async () => {
    const v = videoRef.current;
    if (!v || !v.videoWidth) { setMsg("aguarde a câmera focar…"); return; }
    const b = captureFrame(v, 640);
    if (!b) { setMsg("aguarde a câmera"); return; }
    setBusy(true); setMsg("");
    try { const r = await loginFace(b); if (r.ok && r.user) { stopCam(); setAuth(r.user); } else setMsg(r.message || "rosto não reconhecido"); }
    catch { setMsg("erro de conexão com o servidor — recarregue a página (Ctrl/Cmd+R)"); }
    finally { setBusy(false); }
  };
  const doPin = async () => {
    if (!opId.trim()) { setMsg("informe o ID do operador (ex.: op_operador)"); return; }
    setBusy(true); setMsg("");
    try { const r = await loginPin(opId.trim(), pin); if (r.ok && r.user) { stopCam(); setAuth(r.user); } else setMsg(r.message || "falhou"); }
    catch { setMsg("erro de conexão com o servidor — recarregue a página (Ctrl/Cmd+R)"); }
    finally { setBusy(false); }
  };
  const doBoot = async () => {
    if (!name.trim() || pin.length < 4) { setMsg("nome + PIN (≥4 dígitos)"); return; }
    setBusy(true); setMsg("");
    try { const r = await bootstrap(name.trim(), pin); if (r.ok && r.user) setAuth(r.user); else setMsg(r.message || "falhou"); }
    catch { setMsg("erro de conexão com o servidor — recarregue a página (Ctrl/Cmd+R)"); }
    finally { setBusy(false); }
  };

  const prompt = busy ? "Identificando… verificando vivacidade (liveness)" : camOn ? "Posicione o rosto para identificar" : "Permita a câmera para identificar";

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center p-4 backdrop-blur-sm" style={{ background: "rgba(20,22,24,.86)" }}>
      <style>{SCAN_CSS}</style>
      <div className="vd-surface border border-edge rounded-2xl w-full max-w-sm p-6 text-center shadow-2xl"
        style={{ background: "linear-gradient(170deg,var(--card-bg),color-mix(in srgb,var(--card-bg) 80%,#000))" }}>
        <div className="font-extrabold text-base">Vision<span className="text-text">Desk</span> <span className="text-accent">+ VPS</span> <span className="text-muted font-semibold">· Acesso</span></div>

        {needBoot ? (
          <div className="space-y-2 mt-5 text-left">
            <p className="text-xs text-muted text-center mb-1">Primeira configuração — crie o administrador</p>
            <input className={inputCls} placeholder="Seu nome (admin)" value={name} onChange={(e) => setName(e.target.value)} />
            <input className={inputCls} type="password" inputMode="numeric" placeholder="PIN (≥4 dígitos)" value={pin} onChange={(e) => setPin(e.target.value)} />
            <button className={btnPrimaryCls + " w-full"} onClick={doBoot} disabled={busy}>Criar admin &amp; entrar</button>
            <p className="text-[11px] text-muted">Depois cadastre operadores e habilite o FaceID em <b>Administração › Acesso &amp; Regras</b>.</p>
          </div>
        ) : mode === "face" ? (
          <>
            <div className="relative mx-auto my-5 w-[190px] h-[190px]">
              <div className="absolute inset-0 rounded-2xl overflow-hidden bg-black">
                <video ref={videoRef} className={"w-full h-full object-cover " + (camOn ? "" : "opacity-0")} playsInline autoPlay muted />
                {!camOn && <div className="absolute inset-0 flex items-center justify-center text-muted text-[11px] text-center px-3">📷 abrindo a câmera do dispositivo…</div>}
              </div>
              <svg viewBox="0 0 100 100" fill="none" stroke="var(--accent)" strokeWidth="2.4" strokeLinecap="round" className="absolute inset-0 w-full h-full pointer-events-none">
                <path d="M14 30 V16 H28 M72 16 H86 V30 M86 70 V84 H72 M28 84 H14 V70" />
              </svg>
              {camOn && <div className="vd-ring absolute inset-0 rounded-2xl border-2 border-accent pointer-events-none" />}
              {camOn && !busy && <div className="vd-scan absolute left-[12%] right-[12%] h-0.5 rounded bg-accent pointer-events-none" style={{ boxShadow: "0 0 10px var(--accent)" }} />}
            </div>

            <div className={"font-mono text-[13px] min-h-[20px] " + (msg && !busy ? "text-warn" : "text-accent")}>{msg && !busy ? msg : prompt}</div>

            <div className="flex flex-col gap-2 mt-4">
              {!camOn
                ? <button className={btnPrimaryCls + " w-full py-2.5"} onClick={startCam}>📷 Permitir câmera</button>
                : <>
                    <button className={btnPrimaryCls + " w-full py-2.5"} onClick={doFace} disabled={busy}>{busy ? "Identificando…" : "Entrar com Face ID →"}</button>
                    <button className={ghostBtn} onClick={doFace} disabled={busy}>Reconhecer novamente</button>
                  </>}
            </div>
            <div className="text-xs text-muted mt-3">Não usa biometria? <button className="text-accent hover:underline" onClick={() => { stopCam(); setMode("pin"); setMsg(""); }}>Entrar com PIN / crachá</button></div>
          </>
        ) : (
          <div className="space-y-2 mt-5 text-left">
            <input className={inputCls} placeholder="ID do operador (ex.: op_maria)" value={opId} onChange={(e) => setOpId(e.target.value)} />
            <input className={inputCls} type="password" inputMode="numeric" placeholder="PIN / crachá" value={pin} onChange={(e) => setPin(e.target.value)} />
            <button className={btnPrimaryCls + " w-full py-2.5"} onClick={doPin} disabled={busy}>Entrar →</button>
            {msg && <p className="text-xs text-warn text-center">{msg}</p>}
            <div className="text-xs text-muted text-center pt-1">Tem câmera? <button className="text-accent hover:underline" onClick={() => { setMode("face"); setMsg(""); void startCam(); }}>Usar Face ID</button></div>
          </div>
        )}

        <p className="text-[10.5px] text-muted mt-4 leading-relaxed">🔒 Identificação no dispositivo (edge). Template criptografado, nunca a foto. Uso opcional e consentido — LGPD.</p>
      </div>
    </div>
  );
}
