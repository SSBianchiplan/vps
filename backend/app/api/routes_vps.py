"""VPS — API do Visual Planning System (espinha de rastreabilidade).

Contrato (SPEC_VPS §11.2): capture, resolve, thread (Fio Dourado), board, kpis,
templates, seed. Event Store é a fonte da verdade; demais respostas são projeções.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from ..vps import aps, pcp, phases, bridge, e2e, engine, gold, labels, lgpd, modals, operators, orders, pg_import, planning, rbac, recon, scan as vscan, store, tagid, templates, tree

router = APIRouter(prefix="/vps", tags=["vps"])


class CaptureIn(BaseModel):
    tag_id: str
    action: str
    parent_tag_id: str | None = None
    event_ts: str | None = None
    source_type: str | None = None
    station_id: str | None = None
    operator_id: str | None = None
    vision_mode: str | None = None
    model_version: str | None = None
    confidence: float | None = None
    payload: dict[str, Any] | None = None
    owner: str | None = None
    image_uri: str | None = None


@router.post("/capture")
def capture(body: CaptureIn) -> dict[str, Any]:
    """Edge/visão envia o evento; engine resolve Tag-ID e avança o processo."""
    if not body.tag_id or not body.action:
        raise HTTPException(status_code=400, detail={"code": "missing", "message": "tag_id e action obrigatórios"})
    return engine.capture(body.model_dump(exclude_none=True))


class ResolveIn(BaseModel):
    tag_id: str


@router.post("/resolve")
def resolve(body: ResolveIn) -> dict[str, Any]:
    return engine.resolve(body.tag_id)


@router.get("/thread/{tag_id:path}")
def thread(tag_id: str) -> dict[str, Any]:
    t = engine.thread(tag_id)
    if t is None:
        raise HTTPException(status_code=404, detail={"code": "tag_not_found", "message": "Tag-ID não encontrado"})
    return t


@router.get("/board")
def board(segment: str | None = Query(default=None), entity: str | None = Query(default=None)) -> dict[str, Any]:
    return engine.board(segment, entity)


@router.get("/kpis")
def kpis() -> dict[str, Any]:
    return engine.kpis()


@router.get("/risks")
def risks() -> dict[str, Any]:
    """Inteligência preditiva: Fios em risco de estouro de SLA / bloqueados."""
    return engine.risks()


# ── Ações de governança (cockpit operacional + RBAC §15) ─────────────
@router.post("/pending/{pending_id}/clear")
def clear_pending(pending_id: str, role: str = Depends(rbac.current_role)) -> dict[str, Any]:
    p = store.get_pending(pending_id)
    if p is None:
        raise HTTPException(status_code=404, detail={"code": "pending_not_found", "message": "pendência não encontrada"})
    rbac.require(role, p["tag_id"])
    return engine.clear_pending(pending_id)


@router.post("/occurrence/{occ_id}/resolve")
def resolve_occurrence(occ_id: str, role: str = Depends(rbac.current_role)) -> dict[str, Any]:
    o = store.get_occurrence(occ_id)
    if o is None:
        raise HTTPException(status_code=404, detail={"code": "occ_not_found", "message": "ocorrência não encontrada"})
    rbac.require(role, o["tag_id"])
    return engine.resolve_occurrence(occ_id)


def _actor(x_auth_token: str | None = Header(default=None)) -> str:
    """Quem está agindo: o operador da sessão. Sem sessão, 'cockpit' (dev aberto)."""
    from ..auth import auth
    s = auth.session(x_auth_token)
    return (s or {}).get("operator_id") or "cockpit"


class AdvanceIn(BaseModel):
    reason: str | None = None


@router.post("/thread/{tag_id:path}/advance")
def advance(tag_id: str, body: AdvanceIn | None = None, role: str = Depends(rbac.current_role),
            actor: str = Depends(_actor)) -> dict[str, Any]:
    rbac.require(role, tag_id)
    r = engine.advance(tag_id, (body or AdvanceIn()).reason, actor)
    if r is None:
        raise HTTPException(status_code=404, detail={"code": "tag_not_found", "message": "Tag-ID não encontrado"})
    if not r.get("ok"):
        raise HTTPException(status_code=409, detail={"code": "move_refused", "message": r.get("message")})
    return r


class MoveIn(BaseModel):
    to_phase: str
    reason: str


@router.post("/thread/{tag_id:path}/move")
def move(tag_id: str, body: MoveIn, role: str = Depends(rbac.current_role), actor: str = Depends(_actor)) -> dict[str, Any]:
    """Kanban: mover para uma fase com justificativa obrigatória (adiante, DONE ou retrabalho)."""
    rbac.require(role, tag_id)
    r = engine.move(tag_id, body.to_phase, body.reason, actor)
    if r is None:
        raise HTTPException(status_code=404, detail={"code": "tag_not_found", "message": "Tag-ID não encontrado"})
    if not r.get("ok"):
        raise HTTPException(status_code=409, detail={"code": "move_refused", "message": r.get("message"),
                                                     "phases": r.get("phases")})
    return r


class CorrectIn(BaseModel):
    note: str


@router.post("/thread/{tag_id:path}/correct")
def correct(tag_id: str, body: CorrectIn, role: str = Depends(rbac.current_role), actor: str = Depends(_actor)) -> dict[str, Any]:
    rbac.require(role, tag_id)
    r = engine.correct(tag_id, body.note, actor)
    if r is None:
        raise HTTPException(status_code=404, detail={"code": "tag_not_found", "message": "Tag-ID não encontrado"})
    return r


# ── RBAC + LGPD (governança/segurança §15) ───────────────────────────
@router.get("/roles")
def roles() -> dict[str, Any]:
    return {"roles": rbac.ROLES, "default": rbac.default_role(), "entity_owner": rbac.ENTITY_OWNER}


# ── Operadores (master data + identificação na captura) ──────────────
@router.get("/operators")
def operators_list(status: str | None = Query(default=None)) -> dict[str, Any]:
    return {"operators": operators.list_operators(status), "sessions": operators.sessions(),
            "opcoes": operators.opcoes()}


@router.get("/planning/tree")
def planning_tree(segment: str | None = Query(default=None)) -> dict[str, Any]:
    """Arvore do planejamento: Visual Planning + APS + Fio Dourado, com as bases."""
    return tree.arvore(segment)


@router.get("/operators/options")
def operators_options() -> dict[str, Any]:
    """Valores possíveis por coluna — listas segmentadas em vez de texto livre."""
    return operators.opcoes()


class OperatorIn(BaseModel):
    operator_id: str | None = None
    name: str
    matricula: str | None = None
    badge: str | None = None
    role: str = "Operador"
    stations: str | None = None
    skills: str | None = None
    shift: str | None = None
    status: str = "ativo"


@router.post("/operators")
def operators_upsert(body: OperatorIn) -> dict[str, Any]:
    return operators.upsert_operator(body.model_dump(exclude_none=False))


class StatusIn(BaseModel):
    status: str


@router.post("/operators/{operator_id}/status")
def operators_status(operator_id: str, body: StatusIn) -> dict[str, Any]:
    if not operators.set_status(operator_id, body.status):
        raise HTTPException(status_code=404, detail={"code": "operator_not_found", "message": "operador não encontrado"})
    return {"ok": True}


class IdentifyIn(BaseModel):
    station: str
    operator_id: str | None = None
    badge: str | None = None


@router.post("/operators/identify")
def operators_identify(body: IdentifyIn) -> dict[str, Any]:
    return operators.identify(body.station, body.operator_id, body.badge)


@router.post("/operators/seed")
def operators_seed() -> dict[str, Any]:
    return operators.seed()


# ── APS — Planejamento Avançado (Opcenter-like) ──────────────────────
@router.get("/aps/resources")
def aps_resources() -> dict[str, Any]:
    return {"resources": store.resources()}


class ResourceIn(BaseModel):
    resource_key: str | None = None
    name: str
    capacity: int = 1
    skills: str | None = None
    calendar: str | None = None
    status: str = "ativo"


@router.post("/aps/resources")
def aps_resource_upsert(body: ResourceIn, role: str = Depends(rbac.current_role)) -> dict[str, Any]:
    rbac.require_ctx(role, "APS")
    return store.upsert_resource(body.model_dump(exclude_none=False))


@router.get("/aps/rules")
def aps_rules() -> dict[str, Any]:
    return {"rules": [{"key": k, "label": v} for k, v in aps.RULES.items()]}


@router.post("/aps/schedule")
def aps_generate(scenario: str = Query(default="base"), rule: str = Query(default="prioridade"), role: str = Depends(rbac.current_role)) -> dict[str, Any]:
    """Gera cronograma de capacidade finita (plan); realimenta com actuals da visão."""
    rbac.require_ctx(role, "APS")
    return aps.generate(scenario, rule)


@router.get("/aps/schedule")
def aps_schedule(scenario: str = Query(default="base")) -> dict[str, Any]:
    return {"scenario": scenario, "scenarios": store.scenarios(), "rows": store.schedule(scenario)}


class RescheduleIn(BaseModel):
    planned_start: str
    planned_end: str
    resource_key: str | None = None
    reason: str


@router.post("/aps/schedule/{schedule_id}/move")
def aps_reschedule(schedule_id: str, body: RescheduleIn, role: str = Depends(rbac.current_role),
                   actor: str = Depends(_actor)) -> dict[str, Any]:
    """Arrastar/esticar uma operacao no cronograma (o Gantt e editavel)."""
    rbac.require_ctx(role, "APS")
    r = aps.reschedule(schedule_id, body.planned_start, body.planned_end,
                       body.resource_key, body.reason, actor)
    if r is None:
        raise HTTPException(status_code=404, detail={"code": "schedule_not_found",
                                                     "message": "operacao nao encontrada no cronograma"})
    if not r.get("ok"):
        raise HTTPException(status_code=409, detail={"code": "reschedule_refused",
                                                     "message": r.get("message"),
                                                     "resources": r.get("resources")})
    return r


@router.post("/aps/publish")
def aps_publish(scenario: str = Query(default="base"), role: str = Depends(rbac.current_role)) -> dict[str, Any]:
    rbac.require_ctx(role, "APS")
    return aps.publish(scenario)


@router.get("/aps/kpis")
def aps_kpis(scenario: str = Query(default="base")) -> dict[str, Any]:
    return aps.kpis(scenario)


@router.get("/aps/load")
def aps_load(scenario: str = Query(default="base")) -> dict[str, Any]:
    return {"load": aps.load(scenario)}


@router.get("/aps/compare")
def aps_compare(rules: str = Query(default="prioridade,menor_prazo,fifo")) -> dict[str, Any]:
    return {"comparison": aps.compare([r.strip() for r in rules.split(",") if r.strip()])}


class CtpIn(BaseModel):
    qty: int = 1
    due: str | None = None


@router.post("/aps/ctp")
def aps_ctp(body: CtpIn, role: str = Depends(rbac.current_role)) -> dict[str, Any]:
    rbac.require_ctx(role, "APS")
    return aps.ctp(body.qty, body.due)


@router.post("/aps/expedite")
def aps_expedite(tag_id: str = Query(...), scenario: str = Query(default="base"),
                 rule: str = Query(default="prioridade"), role: str = Depends(rbac.current_role)) -> dict[str, Any]:
    """Prioriza a OP (expedite) e replaneja."""
    rbac.require_ctx(role, "APS")
    aps.expedite(tag_id)
    return aps.generate(scenario, rule)


@router.get("/lgpd")
def lgpd_status() -> dict[str, Any]:
    return lgpd.status()


class LgpdIn(BaseModel):
    blur: bool


# ── Linha do tempo por etapa ─────────────────────────────────────────
@router.get("/phases/{tag_id:path}")
def phases_of(tag_id: str) -> dict[str, Any]:
    return {"tag_id": tag_id, "rows": phases.rows(tag_id), "resumo": phases.resumo(tag_id)}


@router.get("/phases-kpis")
def phases_kpis() -> dict[str, Any]:
    return phases.kpis()


@router.post("/phases/backfill")
def phases_backfill(role: str = Depends(rbac.current_role)) -> dict[str, Any]:
    """Reconstroi o historico de fases das instancias anteriores a tabela."""
    rbac.require_ctx(role, "APS")
    return phases.backfill()


# ── PCP — Planejamento e Controle da Producao ────────────────────────
# A etapa que transforma demanda em material: estrutura do produto (BOM) ->
# demandas de separacao -> o PICKING tem o que buscar.


@router.get("/pcp/bom")
def pcp_bom(product_key: str | None = Query(default=None)) -> dict[str, Any]:
    return {"produtos": pcp.produtos(), "itens": pcp.bom(product_key)}


class BomItemIn(BaseModel):
    bom_id: str | None = None
    product_key: str
    item_key: str
    descricao: str | None = None
    qty: float = 1
    unit: str = "un"
    posicao: int = 0
    lead_time_h: float = 0
    critico: bool = False


@router.post("/pcp/bom")
def pcp_bom_upsert(body: BomItemIn, role: str = Depends(rbac.current_role)) -> dict[str, Any]:
    rbac.require_ctx(role, "PCP")
    try:
        return pcp.upsert_item(body.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=422, detail={"code": "bom_invalido", "message": str(e)}) from e


@router.delete("/pcp/bom/{bom_id}")
def pcp_bom_delete(bom_id: str, role: str = Depends(rbac.current_role)) -> dict[str, Any]:
    rbac.require_ctx(role, "PCP")
    if not pcp.delete_item(bom_id):
        raise HTTPException(status_code=404, detail={"code": "bom_not_found", "message": "item nao encontrado"})
    return {"ok": True}


@router.post("/pcp/bom/seed")
def pcp_bom_seed(role: str = Depends(rbac.current_role)) -> dict[str, Any]:
    rbac.require_ctx(role, "PCP")
    return pcp.seed()


@router.get("/pcp/queue")
def pcp_queue() -> dict[str, Any]:
    return {"fila": pcp.fila(), "kpis": pcp.kpis()}


@router.get("/pcp/demands/{tag_id:path}")
def pcp_demands(tag_id: str) -> dict[str, Any]:
    return {"tag_id": tag_id, "demands": pcp.demands(tag_id)}


class StructureIn(BaseModel):
    qty: float = 1


@router.post("/pcp/structure/{tag_id:path}")
def pcp_structure(tag_id: str, body: StructureIn | None = None, role: str = Depends(rbac.current_role),
                  actor: str = Depends(_actor)) -> dict[str, Any]:
    """Estruturacao do produto: explode a BOM em demandas de separacao."""
    rbac.require_ctx(role, "PCP")
    r = pcp.structure(tag_id, (body or StructureIn()).qty, actor)
    if r is None:
        raise HTTPException(status_code=404, detail={"code": "tag_not_found", "message": "Tag-ID nao encontrado"})
    if not r.get("ok"):
        raise HTTPException(status_code=409, detail={"code": "structure_refused", "message": r.get("message")})
    return r


@router.post("/pcp/clear/{tag_id:path}")
def pcp_clear(tag_id: str, role: str = Depends(rbac.current_role), actor: str = Depends(_actor)) -> dict[str, Any]:
    rbac.require_ctx(role, "PCP")
    return pcp.clear(tag_id, actor)


class DemandIn(BaseModel):
    qty_picked: float


@router.post("/pcp/demand/{demand_id}")
def pcp_demand_set(demand_id: str, body: DemandIn, role: str = Depends(rbac.current_role),
                   actor: str = Depends(_actor)) -> dict[str, Any]:
    """Confirma a separacao de um item (o PICKING responde ao que o PCP pediu)."""
    rbac.require_ctx(role, "STATION")
    r = pcp.set_demand(demand_id, body.qty_picked, actor)
    if r is None:
        raise HTTPException(status_code=404, detail={"code": "demand_not_found", "message": "demanda nao encontrada"})
    return r


@router.post("/lgpd")
def lgpd_set(body: LgpdIn) -> dict[str, Any]:
    lgpd.set_blur(body.blur)
    return lgpd.status()


@router.post("/lgpd/sweep")
def lgpd_sweep() -> dict[str, Any]:
    return lgpd.retention_sweep()


# ── Plataforma de Dados / BI (Gold GLX_) + Auditoria ─────────────────
@router.get("/gold")
def gold_models() -> dict[str, Any]:
    return {"models": [{"key": k, "name": name} for k, (name, _) in gold.MODELS.items()]}


@router.get("/gold/{model}")
def gold_export(model: str, fmt: str = Query(default="json", pattern="^(json|csv)$")):
    m = gold.MODELS.get(model)
    if not m:
        raise HTTPException(status_code=404, detail={"code": "model_not_found", "message": "modelo Gold inexistente"})
    name, fn = m
    rows = fn()
    if fmt == "csv":
        return PlainTextResponse(gold.to_csv(rows), media_type="text/csv",
                                 headers={"Content-Disposition": f'attachment; filename="{name}.csv"'})
    return {"model": name, "rows": rows, "count": len(rows)}


@router.get("/modal/{tag_id:path}")
def modal_bindings(tag_id: str) -> dict[str, Any]:
    """Modais & Vínculos: campos resolvidos das bases (origem MD/TAG/LIN/EVT/...)."""
    r = modals.resolve(tag_id)
    if r is None:
        raise HTTPException(status_code=404, detail={"code": "tag_not_found", "message": "Tag-ID não encontrado"})
    return r


@router.get("/export/thread/{tag_id:path}")
def thread_export(tag_id: str) -> dict[str, Any]:
    """Relatório de auditoria do Fio Dourado (timeline + linhagem + fases + exceções)."""
    t = engine.thread(tag_id)
    if t is None:
        raise HTTPException(status_code=404, detail={"code": "tag_not_found", "message": "Tag-ID não encontrado"})
    phases = [r for r in gold.fact_phase() if r["tag_id"] == tag_id]
    return {"exported_at": store.now_iso(), "thread": t, "phases": phases}


@router.get("/events")
def recent_events(limit: int = Query(default=80, le=1000)) -> dict[str, Any]:
    return {"events": store.recent_events(limit)}


# ── Reconciliação ERP/MES ────────────────────────────────────────────
@router.get("/recon")
def reconciliation() -> dict[str, Any]:
    """Cruza eventos VPS × documentos ERP/MES (idempotente)."""
    return recon.reconcile()


@router.post("/recon/seed")
def reconciliation_seed() -> dict[str, Any]:
    """Carrega docs ERP de demonstração e reconcilia."""
    return recon.seed_docs()


@router.get("/recon/docs")
def recon_docs_list() -> dict[str, Any]:
    return {"docs": recon.docs()}


class ReconDocsIn(BaseModel):
    docs: list[dict[str, Any]]


@router.post("/recon/docs")
def recon_docs_ingest(body: ReconDocsIn) -> dict[str, Any]:
    """Conector ERP/MES: ingere documentos (JSON) e reconcilia."""
    n = recon.load_docs(body.docs)
    return {"ingested": n, **recon.reconcile()}


class ReconCsvIn(BaseModel):
    csv: str


@router.post("/recon/import")
def recon_import_csv(body: ReconCsvIn) -> dict[str, Any]:
    """Conector ERP/MES: importa documentos via CSV (natural_key,doc,qty,value,status)."""
    rows = recon.parse_csv(body.csv)
    recon.load_docs(rows)
    return {"ingested": len(rows), **recon.reconcile()}


@router.delete("/recon/docs")
def recon_docs_clear() -> dict[str, Any]:
    recon.clear()
    return recon.reconcile()


@router.get("/templates")
def list_templates() -> dict[str, Any]:
    return {"templates": [
        {"template_id": t["template_id"], "segment": t["segment"], "label": t.get("label"),
         "phases": [p["id"] for p in t["phases"]]}
        for t in templates.TEMPLATES.values()
    ]}


@router.post("/seed")
def seed(reset: bool = Query(default=True)) -> dict[str, Any]:
    """Popula um Fio Dourado de exemplo (segmento PANEL) p/ demonstrar o cockpit."""
    return engine.seed(reset=reset)


@router.post("/e2e/run")
def e2e_run(reset: bool = Query(default=False), role: str = Depends(rbac.current_role)) -> dict[str, Any]:
    """Executa o teste ponta a ponta REAL (cadastro→DONE) e devolve os passos.

    reset=false (padrao): roda AO LADO dos dados existentes, com chaves proprias
    da rodada, e grava cada passo na trilha de auditoria. reset=true apaga o
    estado VPS antes de rodar — so Admin, porque destroi dados de operacao.
    """
    if reset and role != "Admin":
        raise HTTPException(status_code=403, detail={"code": "rbac_denied",
                            "message": "reset do estado VPS e exclusivo de Admin"})
    return e2e.run(reset=reset, actor=role)


# ── Planejamento (Projetos/Cards) — VPS_Projetos_Planejamento_Cards.md ──
class ProjectIn(BaseModel):
    code: str
    name: str | None = None
    segment: str = "PANEL"
    template_id: str | None = None
    client_key: str | None = None
    resource_pool: str | None = None
    planned_start: str | None = None
    planned_end: str | None = None
    owner: str | None = None


# ── ORDENS DE PRODUÇÃO ───────────────────────────────────────────────
class OpIn(BaseModel):
    code: str | None = None
    segment: str | None = None
    project_id: str | None = None
    product_key: str | None = None
    qty: float = 1
    title: str | None = None
    planned_start: str | None = None
    planned_end: str | None = None
    planned_effort: float | None = None
    resource_key: str | None = None
    instance: str | None = None
    owner: str | None = None


class OpLoteIn(BaseModel):
    itens: list[OpIn]
    comuns: OpIn | None = None


@router.get("/op/proximo-codigo")
def op_proximo(segment: str = "GENERIC") -> dict[str, Any]:
    """Sugestão de número para a tela de abertura — sugestão, não reserva."""
    return {"code": orders.proximo_codigo(segment)}


@router.get("/op/do-projeto/{project_id}")
def op_do_projeto(project_id: str, arquivadas: bool = False) -> dict[str, Any]:
    return {"ordens": orders.do_projeto(project_id, incluir_arquivadas=arquivadas)}


@router.post("/op")
def op_abrir(body: OpIn, role: str = Depends(rbac.current_role),
             actor: str = Depends(_actor)) -> dict[str, Any]:
    rbac.require_ctx(role, "PLANNING")
    d = body.model_dump(exclude_none=True)
    d["code"] = d.get("code") or orders.proximo_codigo(d.get("segment") or "GENERIC")
    r = orders.abrir({**d, "actor": actor})
    if not r.get("ok"):
        raise HTTPException(status_code=409, detail={"code": "op_nao_aberta", "message": r.get("message")})
    return r


@router.post("/op/lote")
def op_abrir_lote(body: OpLoteIn, role: str = Depends(rbac.current_role),
                  actor: str = Depends(_actor)) -> dict[str, Any]:
    """Abre as OPs do assistente numa passada — o que falhar volta identificado."""
    rbac.require_ctx(role, "PLANNING")
    comuns = {**(body.comuns.model_dump(exclude_none=True) if body.comuns else {}), "actor": actor}
    return orders.abrir_lote([i.model_dump(exclude_none=True) for i in body.itens], comuns)


# ── ETAPAS: planejar a janela à mão ──────────────────────────────────
class JanelaIn(BaseModel):
    phase: str
    planned_start: str | None = None
    planned_end: str | None = None
    cascata: bool = True


@router.post("/phases/{tag_id:path}/janela")
def phase_janela(tag_id: str, body: JanelaIn, role: str = Depends(rbac.current_role),
                 actor: str = Depends(_actor)) -> dict[str, Any]:
    """Replaneja a janela VIGENTE de uma etapa. O baseline não se toca."""
    rbac.require(role, tag_id)
    r = phases.set_window(tag_id, body.phase, body.planned_start, body.planned_end,
                          actor=actor, cascata=body.cascata)
    if not r.get("ok"):
        raise HTTPException(status_code=400, detail={"code": "janela_invalida", "message": r.get("message")})
    return r


@router.get("/projects")
def projects_list() -> dict[str, Any]:
    return {"projects": planning.list_projects()}


@router.post("/projects")
def project_create(body: ProjectIn, role: str = Depends(rbac.current_role)) -> dict[str, Any]:
    rbac.require_ctx(role, "PLANNING")
    return planning.create_project(body.model_dump(exclude_none=False))


@router.get("/project/{project_id}")
def project_get(project_id: str) -> dict[str, Any]:
    p = planning.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail={"code": "project_not_found", "message": "projeto não encontrado"})
    p["wbs"] = planning.list_wbs(project_id)
    p["cards"] = planning.list_cards(project_id)
    p["deps"] = planning.list_deps(project_id)
    return p


class WbsIn(BaseModel):
    code: str
    name: str
    parent: str | None = None
    lvl: int = 1


@router.post("/project/{project_id}/wbs")
def project_wbs(project_id: str, body: WbsIn, role: str = Depends(rbac.current_role)) -> dict[str, Any]:
    rbac.require_ctx(role, "PLANNING")
    return planning.add_wbs(project_id, body.code, body.name, body.parent, body.lvl)


class CardIn(BaseModel):
    code: str
    title: str | None = None
    card_type: str = "TASK"
    planned_effort: float = 8
    resource_key: str | None = None
    assigned_operator: str | None = None
    priority: int = 100
    wbs_id: str | None = None


@router.post("/project/{project_id}/card")
def project_card(project_id: str, body: CardIn, role: str = Depends(rbac.current_role)) -> dict[str, Any]:
    rbac.require_ctx(role, "PLANNING")
    return planning.add_card(project_id, body.model_dump(exclude_none=False))


class DepIn(BaseModel):
    pred_card_id: str
    succ_card_id: str
    dep_type: str = "FS"
    lag_min: int = 0


@router.post("/project/{project_id}/dependency")
def project_dep(project_id: str, body: DepIn, role: str = Depends(rbac.current_role)) -> dict[str, Any]:
    rbac.require_ctx(role, "PLANNING")
    r = planning.add_dependency(project_id, body.pred_card_id, body.succ_card_id, body.dep_type, body.lag_min)
    if r is None:
        raise HTTPException(status_code=400, detail={"code": "invalid_dep", "message": "dependência inválida"})
    return r


@router.post("/project/{project_id}/schedule")
def project_schedule(project_id: str, role: str = Depends(rbac.current_role)) -> dict[str, Any]:
    rbac.require_ctx(role, "PLANNING")
    return planning.schedule(project_id)


@router.get("/project/{project_id}/critical-path")
def project_cpm(project_id: str) -> dict[str, Any]:
    return planning.critical_path(project_id)


@router.post("/project/{project_id}/baseline")
def project_baseline(project_id: str, role: str = Depends(rbac.current_role)) -> dict[str, Any]:
    rbac.require_ctx(role, "PLANNING")
    return planning.set_baseline(project_id)


@router.get("/project/{project_id}/plan-vs-actual")
def project_pva(project_id: str) -> dict[str, Any]:
    return planning.plan_vs_actual(project_id)


class AssignIn(BaseModel):
    operator: str | None = None
    resource: str | None = None


@router.post("/card/{card_id}/assign")
def card_assign(card_id: str, body: AssignIn, role: str = Depends(rbac.current_role)) -> dict[str, Any]:
    rbac.require_ctx(role, "PLANNING")
    r = planning.assign_card(card_id, body.operator, body.resource)
    if r is None:
        raise HTTPException(status_code=404, detail={"code": "card_not_found", "message": "card não encontrado"})
    return r


class CardWindowIn(BaseModel):
    planned_start: str
    planned_end: str
    reason: str


@router.post("/card/{card_id}/window")
def card_window(card_id: str, body: CardWindowIn, role: str = Depends(rbac.current_role),
                actor: str = Depends(_actor)) -> dict[str, Any]:
    """Arrastar/esticar um card no cronograma do projeto."""
    rbac.require_ctx(role, "PLANNING")
    r = planning.set_card_window(card_id, body.planned_start, body.planned_end, body.reason, actor)
    if r is None:
        raise HTTPException(status_code=404, detail={"code": "card_not_found", "message": "card nao encontrado"})
    if not r.get("ok"):
        raise HTTPException(status_code=409, detail={"code": "window_refused", "message": r.get("message")})
    return r


class CardStateIn(BaseModel):
    state: str
    reason: str


@router.post("/card/{card_id}/state")
def card_state(card_id: str, body: CardStateIn, role: str = Depends(rbac.current_role),
               actor: str = Depends(_actor)) -> dict[str, Any]:
    """Kanban do projeto: trocar a raia do card com justificativa."""
    rbac.require_ctx(role, "PLANNING")
    r = planning.set_card_state(card_id, body.state, body.reason, actor)
    if r is None:
        raise HTTPException(status_code=404, detail={"code": "card_not_found", "message": "card nao encontrado"})
    if not r.get("ok"):
        raise HTTPException(status_code=409, detail={"code": "state_refused", "message": r.get("message")})
    return r


@router.post("/card/{card_id}/release")
def card_release(card_id: str, role: str = Depends(rbac.current_role)) -> dict[str, Any]:
    rbac.require_ctx(role, "PLANNING")
    r = planning.release_card(card_id)
    if r is None:
        raise HTTPException(status_code=404, detail={"code": "card_not_found", "message": "card não encontrado"})
    return r


@router.post("/planning/seed-gpsis")
def planning_seed_gpsis(role: str = Depends(rbac.current_role), actor: str = Depends(_actor)) -> dict[str, Any]:
    """Projeto demonstrativo GPSIS_001_DEMO, persistido (idempotente)."""
    rbac.require_ctx(role, "PLANNING")
    return planning.seed_gpsis_demo(actor)


@router.post("/planning/seed")
def planning_seed(role: str = Depends(rbac.current_role)) -> dict[str, Any]:
    rbac.require_ctx(role, "PLANNING")
    return planning.seed_demo()


@router.post("/import/teste")
def import_teste() -> dict[str, Any]:
    """Aplica o projeto PostgreSQL 'teste_sistema' ao cockpit (10 OPs visíveis no sistema)."""
    try:
        return pg_import.import_teste()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail={"code": "pg_import_failed", "message": str(exc)})


class ScanIn(BaseModel):
    station: str
    operator_id: str | None = None
    image_b64: str | None = None      # local/mobile (getUserMedia)
    camera_id: str | None = None      # câmera IP salva
    mtx_path: str | None = None       # osmo/drone (MediaMTX)


@router.post("/scan")
async def scan(body: ScanIn) -> dict[str, Any]:
    """📷 APONTAR/ESCANEAR — lê o QR e RESOLVE (sem gravar): devolve a OP + ações válidas."""
    return await vscan.scan(body.station, body.operator_id, body.image_b64, body.camera_id, body.mtx_path)


class StationActionIn(BaseModel):
    tag_id: str
    action: str
    station: str
    operator_id: str | None = None
    payload: dict[str, Any] | None = None


@router.post("/station/action")
async def station_action(body: StationActionIn) -> dict[str, Any]:
    """Registra a ação escolhida pelo operador (após ler o QR)."""
    return await vscan.apply(body.tag_id, body.action, body.station, body.operator_id, body.payload)


# ── Ponte Visão→VPS (gênese/verificação automática) ──────────────────
@router.get("/bridge")
def bridge_status() -> dict[str, Any]:
    return {"auto_capture": bridge.auto_enabled(), "segment": bridge.segment(), "bindings": bridge.bindings()}


@router.get("/segments")
def segments() -> dict[str, Any]:
    return {"segments": templates.segments(), "current": bridge.segment()}


class SegmentIn(BaseModel):
    segment: str


@router.post("/bridge/segment")
def bridge_segment(body: SegmentIn) -> dict[str, Any]:
    bridge.set_segment(body.segment)
    return {"segment": bridge.segment()}


@router.get("/tagid")
def build_tagid(segment: str, entity: str = Query(default="OP"),
                key: str = Query(...), instance: str = Query(default="01")) -> dict[str, Any]:
    """Monta o Tag-ID canônico (p/ etiqueta imprimível antes da gênese)."""
    return {"tag_id": tagid.build(segment, entity, key, instance)}


# ── Gerador de Tags (etiquetas físicas QR — VPS_Gerador_de_Tags.md) ───
@router.get("/qr")
def qr(data: str = Query(...), ec: str = Query(default="Q", pattern="^[LMQH]$")):
    """QR SVG do conteúdo (Tag-ID/deep link). Correção Q = industrial."""
    svg = labels.qr_svg(data, ec)
    if svg is None:
        raise HTTPException(status_code=503, detail={"code": "qr_unavailable", "message": "segno indisponível"})
    return PlainTextResponse(svg, media_type="image/svg+xml")


class TagGenIn(BaseModel):
    type: str = "ENTITY"
    segment: str
    entity_type: str
    natural_key: str
    instance: str = "01"
    parent: str | None = None
    cliente: str | None = None
    lote: str | None = None
    qtd: str | None = None
    estado: str | None = None
    phase: str | None = None
    sla: str | None = None
    template_id: str | None = None
    owner: str | None = None
    station: str | None = None
    emissor: str | None = None
    encode: str = "TAGID"
    size: str = "62x100"
    print_batch: str | None = None


@router.get("/label/prefill/{tag_id:path}")
def label_prefill(tag_id: str) -> dict[str, Any]:
    """Auto-fill dos campos da etiqueta a partir de um Fio existente."""
    r = labels.prefill(tag_id)
    if r is None:
        raise HTTPException(status_code=404, detail={"code": "tag_not_found", "message": "Tag-ID não encontrado"})
    return r


@router.post("/tag/generate")
def tag_generate(body: TagGenIn) -> dict[str, Any]:
    return labels.generate(body.model_dump())


class TagBatchIn(BaseModel):
    items: list[dict[str, Any]]
    defaults: dict[str, Any] | None = None


@router.post("/tag/batch")
def tag_batch(body: TagBatchIn) -> dict[str, Any]:
    return {"labels": labels.batch(body.items, body.defaults)}


class AutoIn(BaseModel):
    on: bool


@router.post("/bridge/auto")
def bridge_auto(body: AutoIn) -> dict[str, Any]:
    bridge.set_auto(body.on)
    return {"auto_capture": bridge.auto_enabled()}


class BindIn(BaseModel):
    source_id: str
    tag_id: str | None = None


@router.post("/bridge/bind")
def bridge_bind(body: BindIn) -> dict[str, Any]:
    """Liga (ou desliga, tag_id=null) uma fonte de visão a um Tag-ID p/ verificação."""
    if body.tag_id:
        bridge.bind(body.source_id, body.tag_id)
    else:
        bridge.unbind(body.source_id)
    return {"bindings": bridge.bindings()}
