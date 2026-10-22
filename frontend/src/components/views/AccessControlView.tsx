import { useCallback, useEffect, useRef, useState } from "react";
import { useStore } from "../../store/useStore";
import {
  createUser, deleteUser, enrollUserFace, listUsers, matrix, setUserActive, setUserRole,
  type AccessUser, type MatrixRow, type Role,
} from "../../api/auth";
import { captureFrame } from "../../lib/capture";
import { btnCls, btnPrimaryCls, inputCls, selectCls, labelCls } from "../../lib/ui";

const ROLES: Role[] = ["admin", "operador", "view"];
const ROLE_LABEL: Record<Role, string> = { admin: "Admin", operador: "Operador", view: "View (leitura)" };

export function AccessControlView() {
  const auth = useStore((s) => s.auth);
  const [users, setUsers] = useState<AccessUser[]>([]);
  const [mtx, setMtx] = useState<MatrixRow[]>([]);
  const [msg, setMsg] = useState("");
  // novo usuário
  const [name, setName] = useState("");
  const [role, setRole] = useState<Role>("operador");
  const [pin, setPin] = useState("");
  // câmera (cadastro de face)
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [camOn, setCamOn] = useState(false);
  const [enrollTarget, setEnrollTarget] = useState<string | null>(null);  // operator_id sendo cadastrado (existente)

  const load = useCallback(() => {
    listUsers().then(setUsers).catch((e) => setMsg(String(e?.message ?? e)));
    matrix().then((m) => setMtx(m.matrix)).catch(() => undefined);
  }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => () => { streamRef.current?.getTracks().forEach((t) => t.stop()); }, []);

  const startCam = async (target: string | null) => {
    setEnrollTarget(target); setMsg("");
    try {
      let s: MediaStream;
      try { s = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false }); }
      catch { s = await navigator.mediaDevices.getUserMedia({ video: true, audio: false }); }
      streamRef.current = s; setCamOn(true);
    } catch { setMsg("sem câmera"); }
  };
  // anexa o stream ao <video> após montar (evita preview preto)
  useEffect(() => {
    const v = videoRef.current;
    if (camOn && v && streamRef.current) { v.srcObject = streamRef.current; v.play().catch(() => undefined); }
  }, [camOn, enrollTarget]);
  const stopCam = () => { streamRef.current?.getTracks().forEach((t) => t.stop()); streamRef.current = null; setCamOn(false); setEnrollTarget(null); };
  const grab = () => (videoRef.current ? captureFrame(videoRef.current, 640) : null);

  const create = async () => {
    if (!name.trim()) { setMsg("informe o nome"); return; }
    const face_b64 = (camOn && enrollTarget === "__new__") ? (grab() ?? undefined) : undefined;
    const r = await createUser({ name: name.trim(), role, pin: pin || undefined, face_b64 });
    if (r.ok) { setMsg(`✓ ${name} (${role})${face_b64 ? " + face" : ""}`); setName(""); setPin(""); stopCam(); load(); }
    else setMsg(`✗ ${r.message}`);
  };
  const enroll = async (oid: string) => {
    const b = grab(); if (!b) { setMsg("aguarde a câmera"); return; }
    const r = await enrollUserFace(oid, b);
    setMsg(r.ok ? "✓ face cadastrada" : `✗ ${r.message}`); stopCam(); load();
  };
  const chRole = async (oid: string, r: Role) => { await setUserRole(oid, r); load(); };
  const chActive = async (oid: string, a: boolean) => { await setUserActive(oid, a); load(); };
  const remove = async (oid: string) => { if (oid === auth?.operator_id) { setMsg("não remova a si mesmo"); return; } await deleteUser(oid); load(); };

  return (
    <div className="h-full overflow-y-auto scroll-thin pr-1">
      <div className="max-w-4xl mx-auto space-y-4 pb-8">
        <div>
          <h1 className="text-2xl font-bold">🔐 Acesso &amp; Regras</h1>
          <p className="text-sm text-muted mt-1">Usuários, papéis (admin/operador/view) e login por FaceID/PIN. Biometria = template (não foto), consentida e revogável (LGPD).</p>
        </div>

        {/* Novo usuário */}
        <section className="vd-surface border border-edge rounded-card p-4 space-y-3">
          <h2 className="font-bold">Cadastrar usuário</h2>
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-2">
            <div className="sm:col-span-2"><label className={labelCls}>Nome</label><input className={inputCls} value={name} onChange={(e) => setName(e.target.value)} placeholder="Nome do usuário" /></div>
            <div><label className={labelCls}>Papel</label><select className={selectCls} value={role} onChange={(e) => setRole(e.target.value as Role)}>{ROLES.map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}</select></div>
            <div><label className={labelCls}>PIN (fallback)</label><input className={inputCls} type="password" inputMode="numeric" value={pin} onChange={(e) => setPin(e.target.value)} placeholder="opcional" /></div>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {!camOn || enrollTarget !== "__new__"
              ? <button className={btnCls} onClick={() => startCam("__new__")}>📷 Capturar face (opcional)</button>
              : <button className={btnCls} onClick={stopCam}>parar câmera</button>}
            <button className={btnPrimaryCls} onClick={create}>＋ Criar usuário</button>
            {msg && <span className="text-xs text-warn">{msg}</span>}
          </div>
          {camOn && enrollTarget === "__new__" && (
            <div className="aspect-video max-w-xs bg-black rounded-card overflow-hidden"><video ref={videoRef} className="w-full h-full object-cover" playsInline muted /></div>
          )}
          <p className="text-[11px] text-muted">FaceID é opt-in: sem face, o usuário entra por PIN. Papel define o acesso (matriz abaixo).</p>
        </section>

        {/* Lista de usuários */}
        <section className="vd-surface border border-edge rounded-card p-4">
          <h2 className="font-bold mb-2">Usuários ({users.length})</h2>
          <div className="space-y-1">
            {users.map((u) => (
              <div key={u.operator_id} className="flex items-center gap-2 text-sm border-b border-edge/40 py-1.5 flex-wrap">
                <span className={"w-2 h-2 rounded-full " + (u.active ? "bg-ok" : "bg-nok")} />
                <span className="font-medium text-text">{u.name}</span>
                <span className="text-[10px] text-muted font-mono">{u.operator_id}</span>
                {u.has_face && <span className="text-[10px] px-1.5 py-0.5 rounded-full border border-accent/40 text-accent">🙂 face</span>}
                {u.has_pin && <span className="text-[10px] px-1.5 py-0.5 rounded-full border border-edge text-muted">PIN</span>}
                <select className="ml-auto bg-edge border border-edge rounded px-1.5 py-1 text-xs" value={u.role} onChange={(e) => chRole(u.operator_id, e.target.value as Role)}>
                  {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
                </select>
                <button className="text-xs px-2 py-1 rounded border border-edge hover:border-accent" onClick={() => chActive(u.operator_id, !u.active)}>{u.active ? "desativar" : "ativar"}</button>
                {(camOn && enrollTarget === u.operator_id)
                  ? <button className="text-xs px-2 py-1 rounded border border-accent text-accent" onClick={() => enroll(u.operator_id)}>📸 salvar face</button>
                  : <button className="text-xs px-2 py-1 rounded border border-edge hover:border-accent" onClick={() => startCam(u.operator_id)}>face</button>}
                <button className="text-xs text-muted hover:text-nok" onClick={() => remove(u.operator_id)}>✕</button>
              </div>
            ))}
            {users.length === 0 && <p className="text-xs text-muted">Nenhum usuário.</p>}
          </div>
          {camOn && enrollTarget && enrollTarget !== "__new__" && (
            <div className="aspect-video max-w-xs bg-black rounded-card overflow-hidden mt-2"><video ref={videoRef} className="w-full h-full object-cover" playsInline muted /></div>
          )}
        </section>

        {/* Matriz RBAC */}
        <section className="vd-surface border border-edge rounded-card p-4">
          <h2 className="font-bold mb-2">Matriz de permissões</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-muted text-xs uppercase"><th className="text-left py-1">Capacidade</th><th>Admin</th><th>Operador</th><th>View</th></tr></thead>
              <tbody>
                {mtx.map((r, i) => (
                  <tr key={i} className="border-t border-edge/40">
                    <td className="py-1.5 text-text">{r.cap}</td>
                    {(["admin", "operador", "view"] as const).map((k) => (
                      <td key={k} className="text-center">{r[k] ? <span className="text-ok">✓</span> : <span className="text-muted">—</span>}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  );
}
