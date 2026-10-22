import { useEffect, useState } from "react";
import {
  catalog, createRule, deleteRule, listActions, listRules, listTasks, retryAction, toggleRule,
  type ActionDef, type ActionLog, type Rule, type TaskRow,
} from "../../api/actions";
import { getWhatsApp, putWhatsApp, testWhatsApp, type WhatsAppConfig } from "../../api/notify";
import { btnCls, btnPrimaryCls, inputCls, labelCls, selectCls } from "../../lib/ui";

const MSG_TYPES = new Set(["alert_visual", "clipboard", "whatsapp"]);
const NET_TYPES = new Set(["webhook_post", "webhook_slack", "log_external"]);
const STATUS_COLOR: Record<string, string> = { success: "text-ok", error: "text-nok", skipped: "text-muted", pending: "text-warn" };

export function ActionsView() {
  const [tasks, setTasks] = useState<TaskRow[]>([]);
  const [ops, setOps] = useState<string[]>([]);
  const [types, setTypes] = useState<string[]>([]);
  const [taskId, setTaskId] = useState("*");
  const [rules, setRules] = useState<Rule[]>([]);
  const [actions, setActions] = useState<ActionLog[]>([]);

  // form
  const [label, setLabel] = useState("");
  const [field, setField] = useState("veredito");
  const [op, setOp] = useState("==");
  const [value, setValue] = useState("NOK");
  const [minConf, setMinConf] = useState("");
  const [acts, setActs] = useState<ActionDef[]>([{ type: "alert_visual", message: "{value}" }]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    catalog().then((c) => { setOps(c.ops); setTypes(c.action_types); }).catch(() => undefined);
    listTasks().then(setTasks).catch(() => undefined);
  }, []);
  const loadRules = () => listRules(taskId).then(setRules).catch(() => setRules([]));
  const loadActions = () => listActions().then(setActions).catch(() => undefined);
  useEffect(() => { loadRules(); /* eslint-disable-next-line */ }, [taskId]);
  useEffect(() => { loadActions(); const i = window.setInterval(loadActions, 8000); return () => window.clearInterval(i); }, []);

  const setAct = (i: number, patch: Partial<ActionDef>) =>
    setActs((a) => a.map((x, j) => (j === i ? { ...x, ...patch } : x)));

  const save = async () => {
    setErr(null);
    try {
      await createRule(taskId, {
        label: label.trim() || "Regra",
        condition: { field, op, value: op === "present" || op === "absent" ? null : value, min_confidence: minConf ? Number(minConf) : null },
        actions: acts,
      });
      setLabel(""); setActs([{ type: "alert_visual", message: "{value}" }]);
      loadRules();
    } catch (e) { setErr(String((e as Error)?.message ?? e)); }
  };

  return (
    <div className="h-full flex flex-col gap-3 overflow-hidden">
      <div className="flex items-center gap-2 flex-wrap">
        <h2 className="text-lg font-bold">Ações <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent/15 text-accent">AGIR · M5</span></h2>
        <span className="text-xs text-muted">Visão → decisão → ação. Sem código.</span>
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-[1fr_380px] gap-4 overflow-hidden">
        {/* Builder + regras */}
        <div className="overflow-y-auto scroll-thin space-y-4 pr-1">
          <AgirInfoCard />
          <WhatsAppCard />

          <section className="vd-surface border border-edge rounded-card p-4 space-y-3">
            <h3 className="text-xs uppercase tracking-wider text-muted">Nova regra</h3>
            <div className="grid grid-cols-2 gap-2">
              <div><label className={labelCls}>Tarefa</label>
                <select className={selectCls} value={taskId} onChange={(e) => setTaskId(e.target.value)}>
                  <option value="*">★ Qualquer tarefa</option>
                  {tasks.map((t) => <option key={t.task_id} value={t.task_id}>{t.modo} · {t.task_id.slice(0, 10)}</option>)}
                </select>
              </div>
              <div><label className={labelCls}>Nome</label><input className={inputCls} value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Ex.: NOK → Slack" /></div>
            </div>

            <div>
              <label className={labelCls}>Condição (SE)</label>
              <div className="grid grid-cols-[1fr_90px_1fr] gap-2">
                <input className={inputCls} value={field} onChange={(e) => setField(e.target.value)} placeholder="campo (veredito, n_op, total…)" />
                <select className={selectCls} value={op} onChange={(e) => setOp(e.target.value)}>{ops.map((o) => <option key={o}>{o}</option>)}</select>
                <input className={inputCls} value={value} onChange={(e) => setValue(e.target.value)} placeholder="valor"
                  disabled={op === "present" || op === "absent"} />
              </div>
              <input className={inputCls + " mt-2"} value={minConf} onChange={(e) => setMinConf(e.target.value)} placeholder="confiança mínima (0–1, opcional)" />
            </div>

            <div>
              <label className={labelCls}>Ações (ENTÃO)</label>
              <div className="space-y-2">
                {acts.map((a, i) => (
                  <div key={i} className="grid grid-cols-[130px_1fr_28px] gap-2 items-center">
                    <select className={selectCls} value={a.type} onChange={(e) => setAct(i, { type: e.target.value })}>
                      {types.map((t) => <option key={t} value={t}>{t}</option>)}
                    </select>
                    {NET_TYPES.has(a.type) ? (
                      <input className={inputCls} value={a.target ?? ""} onChange={(e) => setAct(i, { target: e.target.value })}
                        placeholder={a.type === "webhook_slack" ? "URL webhook Slack" : a.type === "log_external" ? "caminho .csv (opcional)" : "URL https://…"} />
                    ) : MSG_TYPES.has(a.type) ? (
                      <input className={inputCls} value={a.message ?? ""} onChange={(e) => setAct(i, { message: e.target.value })}
                        placeholder={a.type === "whatsapp" ? "mensagem WhatsApp (use {value})" : "mensagem (use {value}, {timestamp})"} />
                    ) : (
                      <span className="text-[11px] text-warn self-center">não configurado (Fase 5)</span>
                    )}
                    <button className="vd-keep text-muted hover:text-nok" onClick={() => setActs((x) => x.filter((_, j) => j !== i))}>✕</button>
                  </div>
                ))}
              </div>
              <button className={btnCls + " mt-2"} onClick={() => setActs((a) => [...a, { type: "webhook_post", target: "" }])}>+ ação</button>
            </div>

            {err && <p className="text-xs text-nok">{err}</p>}
            <button className={btnPrimaryCls} onClick={save}>Criar regra</button>
          </section>

          <section>
            <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Regras ({rules.length})</h3>
            <div className="space-y-2">
              {rules.length === 0 && <p className="text-xs text-muted">Nenhuma regra para esta seleção.</p>}
              {rules.map((r) => (
                <div key={r.rule_id} className="bg-panel border border-edge rounded-card p-3">
                  <div className="flex items-center gap-2">
                    <span className={"w-2 h-2 rounded-full " + (r.active ? "bg-ok" : "bg-muted")} />
                    <span className="text-sm font-medium">{r.label}</span>
                    <span className="ml-auto flex gap-2">
                      <button className="vd-keep text-xs text-muted hover:text-accent" onClick={async () => { await toggleRule(r.rule_id, !r.active); loadRules(); }}>{r.active ? "pausar" : "ativar"}</button>
                      <button className="vd-keep text-xs text-muted hover:text-nok" onClick={async () => { await deleteRule(r.rule_id); loadRules(); }}>excluir</button>
                    </span>
                  </div>
                  <p className="text-[11px] text-muted mt-1">
                    SE <b className="text-text">{r.condition.field} {r.condition.op} {r.condition.value ?? ""}</b>
                    {r.condition.min_confidence ? ` (conf≥${r.condition.min_confidence})` : ""} ENTÃO {r.actions.map((a) => a.type).join(", ")}
                  </p>
                </div>
              ))}
            </div>
          </section>
        </div>

        {/* Log de ações */}
        <aside className="bg-panel border border-edge rounded-card p-3 overflow-hidden flex flex-col">
          <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Log de ações</h3>
          <div className="flex-1 overflow-y-auto scroll-thin space-y-1.5">
            {actions.length === 0 ? <p className="text-xs text-muted">Sem ações disparadas ainda.</p> :
              actions.map((a) => (
                <div key={a.action_id} className="text-xs border-b border-edge/40 pb-1.5">
                  <div className="flex items-center gap-1.5">
                    <span className={STATUS_COLOR[a.status] ?? "text-muted"}>●</span>
                    <span className="text-text">{a.action_type}</span>
                    {a.http_status && <span className="text-muted">{a.http_status}</span>}
                    <span className="ml-auto text-muted">{new Date(a.timestamp).toLocaleTimeString()}</span>
                  </div>
                  {a.target && <p className="text-muted truncate" title={a.target}>{a.target}</p>}
                  {a.error_message && <p className="text-nok truncate">{a.error_message}</p>}
                  {a.status === "error" && (
                    <button className="vd-keep text-accent hover:underline" onClick={async () => { await retryAction(a.action_id); loadActions(); }}>retentar</button>
                  )}
                </div>
              ))}
          </div>
        </aside>
      </div>
    </div>
  );
}

function AgirInfoCard() {
  return (
    <section className="vd-surface border border-edge rounded-card p-4 space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-xl">⚡</span>
        <h3 className="font-bold text-base">AGIR — Vision-Language-Action <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent/15 text-accent">M5</span></h3>
      </div>
      <p className="text-sm text-muted">
        Fecha o ciclo <b className="text-text">visão → decisão → ação</b> sem código. Cada inferência (Estúdio,
        câmera ou worker) é avaliada por regras <b className="text-text">SE → ENTÃO</b>: quando um campo do
        resultado bate a condição, as ações disparam (WhatsApp, webhook, Slack, alerta visual, copiar, log CSV) —
        tudo auditado, com retry.
      </p>

      <div className="bg-panel border border-edge rounded-card p-3">
        <div className="text-[10px] uppercase tracking-wider text-muted mb-1">Exemplo de regra</div>
        <p className="text-sm">
          <span className="text-muted">SE</span> <code className="text-text">veredito == NOK</code>
          <span className="text-muted"> (conf ≥ 0.8) </span><span className="text-muted">ENTÃO</span>
          <span className="text-ok"> WhatsApp</span> <span className="text-muted">+</span> <span className="text-ok">webhook Slack</span>
        </p>
        <p className="text-[11px] text-muted mt-1">
          Outros campos úteis: <code>contagens.person &gt; 0</code> (intrusão), <code>total &gt;= 10</code> (lote),
          <code> anomalia presente</code>. Atalho: no modo DETECTAR marque <b className="text-text">🔔 Notificar</b>.
        </p>
      </div>

      <div>
        <div className="text-[10px] uppercase tracking-wider text-muted mb-1">O que são Tasks</div>
        <ul className="text-sm text-muted space-y-1 list-disc pl-5">
          <li><b className="text-text">Task</b> = uma configuração de inferência salva (modo + parâmetros + ROI) — corresponde a <code>DIM_TASK</code>. É criada ao rodar uma análise no Estúdio.</li>
          <li>Cada regra mira <b className="text-text">uma Task</b> específica ou <b className="text-text">★ Qualquer Task</b> (global).</li>
          <li>A condição lê o <code>result_json</code> da Task: <code>veredito</code>, <code>total</code>, <code>contagens.&lt;classe&gt;</code>, <code>n_op</code>, <code>confidence</code>…</li>
        </ul>
      </div>
    </section>
  );
}

function WhatsAppCard() {
  const [cfg, setCfg] = useState<WhatsAppConfig | null>(null);
  const [token, setToken] = useState("");
  const [phone, setPhone] = useState("");
  const [recips, setRecips] = useState("");
  const [tplName, setTplName] = useState("");
  const [tplLang, setTplLang] = useState("en_US");
  const [tplParam, setTplParam] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  const load = () => getWhatsApp().then((c) => {
    setCfg(c); setPhone(c.phone_number_id ?? ""); setRecips(c.recipients.join(", "));
    setTplName(c.template_name ?? ""); setTplLang(c.template_lang || "en_US"); setTplParam(c.template_param);
  }).catch(() => undefined);
  useEffect(() => { load(); }, []);

  const save = async () => {
    setMsg(null);
    try {
      const body: Parameters<typeof putWhatsApp>[0] = {
        phone_number_id: phone.trim() || undefined,
        recipients: recips.split(",").map((x) => x.trim()).filter(Boolean),
        template_name: tplName.trim(), template_lang: tplLang.trim() || "en_US", template_param: tplParam,
      };
      if (token.trim()) body.token = token.trim();
      setCfg(await putWhatsApp(body)); setToken(""); setMsg("✓ salvo");
    } catch (e) { setMsg(String((e as Error)?.message ?? e)); }
  };
  const test = async () => {
    setMsg("enviando (template)…");
    const r = await testWhatsApp("VisionDesk: teste", { use_template: true })
      .catch((e) => ({ ok: false, error: String(e), skipped: false }));
    setMsg(r.ok ? (("skipped" in r && r.skipped) ? "throttle (aguarde)" : "✓ enviado (template)") : `falha: ${("error" in r && r.error) || "?"}`);
  };

  return (
    <section className="vd-surface border border-edge rounded-card p-4">
      <button className="vd-keep w-full flex items-center gap-2" onClick={() => setOpen((v) => !v)}>
        <span className="text-lg">🟢</span>
        <h3 className="text-xs uppercase tracking-wider text-muted">Notificações — WhatsApp</h3>
        <span className={"ml-auto text-[10px] px-2 py-0.5 rounded-full " + (cfg?.configured ? "bg-ok/20 text-ok" : "bg-warn/20 text-warn")}>
          {cfg?.configured ? "configurado" : "não configurado"}
        </span>
        <span className="text-muted">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="space-y-2 mt-3">
          <p className="text-[11px] text-muted">WhatsApp Cloud API (Meta). O token fica só no backend.</p>
          <div>
            <label className={labelCls}>Token{cfg?.has_token ? " (salvo — deixe vazio p/ manter)" : ""}</label>
            <input className={inputCls} type="password" value={token} onChange={(e) => setToken(e.target.value)} placeholder="EAAB..." />
          </div>
          <div>
            <label className={labelCls}>Phone Number ID</label>
            <input className={inputCls + " font-mono"} value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="123456789012345" />
          </div>
          <div>
            <label className={labelCls}>Destinatários (E.164, vírgula)</label>
            <input className={inputCls + " font-mono"} value={recips} onChange={(e) => setRecips(e.target.value)} placeholder="5547999998888, 5511988887777" />
          </div>
          <div className="grid grid-cols-[1fr_90px] gap-2">
            <div>
              <label className={labelCls}>Template (notif. fora da janela 24h)</label>
              <input className={inputCls + " font-mono"} value={tplName} onChange={(e) => setTplName(e.target.value)} placeholder="hello_world ou seu_template" />
            </div>
            <div>
              <label className={labelCls}>Idioma</label>
              <input className={inputCls + " font-mono"} value={tplLang} onChange={(e) => setTplLang(e.target.value)} placeholder="en_US" />
            </div>
          </div>
          <label className="flex items-center gap-2 text-xs text-muted cursor-pointer">
            <input type="checkbox" checked={tplParam} onChange={(e) => setTplParam(e.target.checked)} />
            Template tem variável de corpo {"{{1}}"} (recebe o resumo)
          </label>
          <p className="text-[11px] text-muted">
            Notificação iniciada pela empresa exige <b>template aprovado</b> (Meta). Sem template, o
            texto só chega na janela de 24h após o usuário responder.
          </p>
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input type="checkbox" checked={cfg?.enabled ?? true}
              onChange={async (e) => setCfg(await putWhatsApp({ enabled: e.target.checked }))} />
            Notificações ativas
          </label>
          <div className="flex gap-2">
            <button className={btnPrimaryCls} onClick={save}>Salvar</button>
            <button className={btnCls} onClick={test} disabled={!cfg?.configured}>Testar</button>
            {msg && <span className="text-xs text-muted self-center">{msg}</span>}
          </div>
        </div>
      )}
    </section>
  );
}
