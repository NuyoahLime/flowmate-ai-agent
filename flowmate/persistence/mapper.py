from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from flowmate.persistence.errors import PersistenceSerializationError
from flowmate.schemas import ConfirmationStatus, PlanStep, RiskLevel, Task, TaskStatus, ToolCall, ToolCallStatus


def dumps_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise PersistenceSerializationError("Value cannot be serialized as JSON.") from exc


def loads_json(value: str | None, *, allow_none: bool = False) -> Any:
    if value is None:
        if allow_none:
            return None
        raise PersistenceSerializationError("Expected JSON text, got None.")
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise PersistenceSerializationError("Stored JSON is corrupted.") from exc


def task_from_rows(
    task_row: Any,
    step_rows: list[Any],
    tool_call_rows: dict[str, Any],
) -> Task:
    try:
        steps: list[PlanStep] = []
        for row in step_rows:
            tool_call = None
            tool_call_row = tool_call_rows.get(row["step_id"])
            if tool_call_row is not None:
                tool_call = ToolCall(
                    tool_name=tool_call_row["tool_name"],
                    arguments=loads_json(tool_call_row["arguments_json"]),
                    status=ToolCallStatus(tool_call_row["status"]),
                    result=loads_json(tool_call_row["result_json"], allow_none=True),
                    error=tool_call_row["error"],
                )

            steps.append(
                PlanStep(
                    id=row["step_id"],
                    order=row["step_order"],
                    description=row["description"],
                    tool_name=row["tool_name"],
                    status=ToolCallStatus(row["status"]),
                    tool_call=tool_call,
                )
            )

        return Task.model_validate(
            {
                "id": task_row["task_id"],
                "user_input": task_row["user_input"],
                "goal": task_row["goal"],
                "status": TaskStatus(task_row["status"]),
                "risk_level": RiskLevel(task_row["risk_level"]),
                "requires_confirmation": bool(task_row["requires_confirmation"]),
                "confirmation_status": ConfirmationStatus(task_row["confirmation_status"]),
                "steps": steps,
            }
        )
    except (ValueError, TypeError, ValidationError) as exc:
        raise PersistenceSerializationError("Stored task aggregate is invalid.") from exc
