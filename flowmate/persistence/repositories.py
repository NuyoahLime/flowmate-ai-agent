from typing import Protocol

from flowmate.schemas import Task


class TaskRepository(Protocol):
    def save_task(self, task: Task) -> None:
        ...

    def get_task(self, task_id: str) -> Task | None:
        ...

    def list_tasks(self, *, limit: int = 50) -> list[Task]:
        ...
