"""Helpers compartilhados pela API."""
from __future__ import annotations

import json
from typing import Any

from ..schemas.enums import Mode
from ..schemas.tasks import TaskConfig


def task_from_row(row: dict[str, Any]) -> TaskConfig:
    """Reconstrói uma TaskConfig a partir de uma linha de dim_task."""
    params = json.loads(row["parametros_json"]) if row.get("parametros_json") else {}
    roi = json.loads(row["roi_json"]) if row.get("roi_json") else None
    return TaskConfig.model_validate(
        {
            "task_id": row["task_id"],
            "mode": Mode(row["modo"]),
            "prompt": row.get("prompt"),
            "params": params,
            "roi": roi,
        }
    )
