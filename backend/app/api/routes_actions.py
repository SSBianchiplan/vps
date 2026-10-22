"""AGIR (M5): regras no-code + auditoria/retry de ações."""
from __future__ import annotations

from typing import Any

from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..actions import engine
from ..db.repository import repository

router = APIRouter(tags=["actions"])

ACTION_TYPES = [
    "whatsapp", "webhook_post", "webhook_slack", "alert_visual", "clipboard",
    "log_external", "snapshot", "mqtt_publish", "email", "alert_push",
]
OPS = ["present", "absent", "==", "!=", ">", "<", ">=", "<=", "contains"]

ActionType = Literal[
    "whatsapp", "webhook_post", "webhook_slack", "alert_visual", "clipboard",
    "log_external", "snapshot", "mqtt_publish", "email", "alert_push",
]
OpType = Literal["present", "absent", "==", "!=", ">", "<", ">=", "<=", "contains"]


class Condition(BaseModel):
    field: str = "veredito"
    op: OpType = "present"
    value: Any = None
    min_confidence: float | None = None


class Action(BaseModel):
    type: ActionType
    target: str | None = None
    message: str | None = None
    payload_template: dict[str, Any] | None = None


class RuleIn(BaseModel):
    label: str = ""
    condition: Condition
    actions: list[Action]


@router.get("/actions/catalog")
def catalog() -> dict[str, Any]:
    return {"action_types": ACTION_TYPES, "ops": OPS}


@router.post("/tasks/{task_id}/rules")
def create_rule(task_id: str, body: RuleIn) -> dict[str, Any]:
    if not body.actions:
        raise HTTPException(status_code=400, detail={"code": "no_actions", "message": "regra sem ações"})
    return repository.create_rule(
        task_id, body.label, body.condition.model_dump(),
        [a.model_dump(exclude_none=True) for a in body.actions],
    )


@router.get("/tasks/{task_id}/rules")
def list_rules(task_id: str) -> list[dict[str, Any]]:
    return repository.list_rules(task_id=task_id)


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: str) -> dict[str, Any]:
    return {"deleted": repository.delete_rule(rule_id)}


@router.post("/rules/{rule_id}/toggle")
def toggle_rule(rule_id: str, active: bool = Query(...)) -> dict[str, Any]:
    repository.set_rule_active(rule_id, active)
    return {"rule_id": rule_id, "active": active}


@router.get("/actions")
def list_actions(status: str | None = Query(default=None), limit: int = Query(default=200, le=2000)) -> dict[str, Any]:
    return {"actions": repository.list_actions(status=status, limit=limit)}


@router.post("/actions/{action_id}/retry")
async def retry(action_id: str) -> dict[str, Any]:
    res = await engine.retry_action(action_id)
    if res is None:
        raise HTTPException(status_code=404, detail={"code": "action_not_found", "message": "ação não encontrada"})
    return res
