from __future__ import annotations

from pathlib import Path

from flowmate.persistence.repositories import TaskRepository
from flowmate.persistence.sqlite_repository import SQLiteTaskRepository
from flowmate.schemas import Task


class TaskPersistenceService:
    def __init__(self, repository: TaskRepository | None = None, *, db_path: str | Path | None = None) -> None:
        self.repository = repository or SQLiteTaskRepository(db_path)

    def persist(self, task: Task) -> None:
        self.repository.save_task(task)

    def load(self, task_id: str) -> Task | None:
        return self.repository.get_task(task_id)

    def list_history(self, *, limit: int = 50) -> list[Task]:
        return self.repository.list_tasks(limit=limit)
