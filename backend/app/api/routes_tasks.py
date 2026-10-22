"""CRUD de tarefas (DIM_TASK)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..db.repository import repository
from ..schemas.tasks import TaskConfig, TaskCreateResponse
from .deps import task_from_row

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=TaskCreateResponse)
def create_task(task: TaskConfig) -> TaskCreateResponse:
    task_id = repository.upsert_task(task)
    return TaskCreateResponse(task_id=task_id)


@router.get("")
def list_tasks() -> list[dict]:
    return repository.list_tasks()


@router.get("/{task_id}", response_model=TaskConfig)
def get_task(task_id: str) -> TaskConfig:
    row = repository.get_task(task_id)
    if not row:
        raise HTTPException(status_code=404, detail="task não encontrada")
    return task_from_row(row)
