from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from flowmate.persistence.database import initialize_schema, resolve_database_path
from flowmate.persistence.errors import PersistenceIntegrityError
from flowmate.persistence.mapper import dumps_json, task_from_rows
from flowmate.schemas import Task


class SQLiteTaskRepository:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = resolve_database_path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            with connection:
                initialize_schema(connection)

    def save_task(self, task: Task) -> None:
        try:
            with closing(self._connect()) as connection:
                with connection:
                    save_task_aggregate(connection, task)
        except sqlite3.IntegrityError as exc:
            raise PersistenceIntegrityError("Task aggregate violates persistence integrity.") from exc

    def get_task(self, task_id: str) -> Task | None:
        with closing(self._connect()) as connection:
            task_row = connection.execute(
                "SELECT * FROM tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            if task_row is None:
                return None

            step_rows = connection.execute(
                "SELECT * FROM plan_steps WHERE task_id = ? ORDER BY step_order ASC",
                (task_id,),
            ).fetchall()
            tool_rows = connection.execute(
                """
                SELECT tool_calls.*
                FROM tool_calls
                JOIN plan_steps
                    ON plan_steps.task_id = tool_calls.task_id
                    AND plan_steps.step_id = tool_calls.step_id
                WHERE plan_steps.task_id = ?
                """,
                (task_id,),
            ).fetchall()
            return task_from_rows(
                task_row,
                step_rows,
                {row["step_id"]: row for row in tool_rows},
            )

    def list_tasks(self, *, limit: int = 50) -> list[Task]:
        if limit <= 0:
            return []
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT task_id FROM tasks ORDER BY updated_at DESC, task_id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [task for row in rows if (task := self.get_task(row["task_id"])) is not None]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def save_task_aggregate(
    connection: sqlite3.Connection,
    task: Task,
    *,
    now: str | None = None,
) -> None:
    now = now or _utc_now()
    existing = connection.execute(
        "SELECT created_at FROM tasks WHERE task_id = ?",
        (task.id,),
    ).fetchone()
    created_at = existing["created_at"] if existing else now

    connection.execute(
        """
        INSERT INTO tasks (
            task_id, user_input, goal, status, risk_level,
            requires_confirmation, confirmation_status,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(task_id) DO UPDATE SET
            user_input = excluded.user_input,
            goal = excluded.goal,
            status = excluded.status,
            risk_level = excluded.risk_level,
            requires_confirmation = excluded.requires_confirmation,
            confirmation_status = excluded.confirmation_status,
            updated_at = excluded.updated_at
        """,
        (
            task.id,
            task.user_input,
            task.goal,
            task.status.value,
            task.risk_level.value,
            1 if task.requires_confirmation else 0,
            task.confirmation_status.value,
            created_at,
            now,
        ),
    )

    connection.execute("DELETE FROM plan_steps WHERE task_id = ?", (task.id,))
    for step in task.steps:
        connection.execute(
            """
            INSERT INTO plan_steps (
                task_id, step_id, step_order, description,
                tool_name, status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task.id,
                step.id,
                step.order,
                step.description,
                step.tool_name,
                step.status.value,
                now,
                now,
            ),
        )
        if step.tool_call is not None:
            connection.execute(
                """
                INSERT INTO tool_calls (
                    task_id, step_id, tool_name, arguments_json, status,
                    result_json, error, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.id,
                    step.id,
                    step.tool_call.tool_name,
                    dumps_json(step.tool_call.arguments),
                    step.tool_call.status.value,
                    dumps_json(step.tool_call.result)
                    if step.tool_call.result is not None
                    else None,
                    step.tool_call.error,
                    now,
                    now,
                ),
            )
