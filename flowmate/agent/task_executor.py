from flowmate.agent.step_executor import StepExecutor
from flowmate.schemas import ConfirmationStatus, Task, TaskStatus, ToolCallStatus


class TaskExecutionError(Exception):
    pass


class TaskExecutor:
    def __init__(self, step_executor: StepExecutor) -> None:
        self.step_executor = step_executor

    def execute(self, task: Task) -> Task:
        self._ensure_executable(task)

        task.status = TaskStatus.EXECUTING

        for step in sorted(task.steps, key=lambda item: item.order):
            executed_step = self.step_executor.execute(step)
            if executed_step.status != ToolCallStatus.SUCCESS:
                task.status = TaskStatus.FAILED
                return task

        task.status = TaskStatus.COMPLETED
        return task

    def _ensure_executable(self, task: Task) -> None:
        if task.status == TaskStatus.WAITING_CONFIRMATION:
            raise TaskExecutionError("Task is waiting for confirmation and cannot be executed.")

        if task.status != TaskStatus.PLANNED:
            raise TaskExecutionError(f"Task status is not executable: {task.status.value}")

        if (
            task.requires_confirmation
            and task.confirmation_status != ConfirmationStatus.CONFIRMED
        ):
            raise TaskExecutionError("Task requires confirmation before execution.")

        if not task.steps:
            raise TaskExecutionError("Task has no steps and cannot be executed.")
