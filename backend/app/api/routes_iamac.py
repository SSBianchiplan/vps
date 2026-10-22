"""iaMAC — copiloto RAG (grounding/citações), flywheel/eval e status Mac/MLX."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, Header, HTTPException, UploadFile
from pydantic import BaseModel

from ..iamac import engine, providers

router = APIRouter(prefix="/iamac", tags=["iamac"])


class AskIn(BaseModel):
    question: str


class FeedbackIn(BaseModel):
    id: int
    vote: int


class ModelIn(BaseModel):
    model_id: str


@router.get("/models")
def models() -> dict[str, Any]:
    return {"models": providers.catalog(), "current": providers.current_id()}


@router.post("/model")
def set_model(body: ModelIn) -> dict[str, Any]:
    return providers.set_current(body.model_id)


@router.get("/status")
def status() -> dict[str, Any]:
    return engine.status()


@router.post("/ask")
def ask(body: AskIn) -> dict[str, Any]:
    return engine.ask(body.question)


@router.post("/feedback")
def feedback(body: FeedbackIn) -> dict[str, Any]:
    return engine.feedback(body.id, body.vote)


@router.get("/interactions")
def interactions() -> dict[str, Any]:
    return {"interactions": engine.interactions()}


@router.post("/eval")
def run_eval() -> dict[str, Any]:
    return engine.run_eval()


@router.get("/eval/history")
def eval_history() -> dict[str, Any]:
    return {"history": engine.eval_history()}


@router.get("/insights")
def insights() -> dict[str, Any]:
    return {"insights": engine.insights()}


@router.post("/reindex")
def reindex() -> dict[str, Any]:
    return {"chunks": engine.reindex()}


# ── Leitor de documentos + biblioteca gerenciável ────────────────────
def _exige_sessao(token: str | None) -> None:
    """Upload/remoção mudam a base que a IA lê: exigem sessão (admin ou operador)."""
    from ..auth import auth
    s = auth.session(token)
    if not s or s.get("role") not in ("admin", "operador"):
        raise HTTPException(status_code=403, detail={"code": "forbidden", "message": "requer sessão de admin ou operador"})


@router.get("/documents")
def documents() -> dict[str, Any]:
    """Inventário de TUDO que a IA vê: lidos e não lidos, com o motivo."""
    from ..iamac import leitor
    inv = engine.inventario()
    return {"documents": inv, "total": len(inv), "indexados": sum(1 for i in inv if i["ok"]),
            "supported": sorted(leitor.SUPORTADOS)}


@router.get("/library")
def library() -> dict[str, Any]:
    from ..iamac import leitor
    return {"dir": str(engine.biblioteca_dir()), "files": engine.biblioteca_listar(),
            "supported": sorted(leitor.SUPORTADOS)}


@router.post("/library/upload")
async def library_upload(files: list[UploadFile] = File(...), x_auth_token: str | None = Header(default=None)) -> dict[str, Any]:
    _exige_sessao(x_auth_token)
    out = []
    for f in files:
        dados = await f.read()
        out.append({"file": f.filename, **engine.biblioteca_salvar(f.filename or "documento", dados)})
    return {"results": out, "files": engine.biblioteca_listar()}


@router.delete("/library/{name}")
def library_delete(name: str, x_auth_token: str | None = Header(default=None)) -> dict[str, Any]:
    _exige_sessao(x_auth_token)
    r = engine.biblioteca_remover(name)
    if not r.get("ok"):
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": r.get("message")})
    return {**r, "files": engine.biblioteca_listar()}
