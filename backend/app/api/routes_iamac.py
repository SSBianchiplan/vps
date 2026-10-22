"""iaMAC — copiloto RAG (grounding/citações), flywheel/eval e status Mac/MLX."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
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
