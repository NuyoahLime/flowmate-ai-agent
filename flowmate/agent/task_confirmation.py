from flowmate.schemas import ConfirmationStatus, Task, TaskStatus


class TaskConfirmationError(Exception):
    pass


class TaskConfirmationService:
    def request_confirmation(self, task: Task) -> Task:
        if not task.requires_confirmation:
            raise TaskConfirmationError("Task does not require confirmation.")

        if task.status != TaskStatus.PLANNED:
            raise TaskConfirmationError(
                f"Task status cannot request confirmation: {task.status.value}"
            )

        if task.confirmation_status == ConfirmationStatus.CONFIRMED:
            raise TaskConfirmationError("Task is already confirmed.")

        if task.confirmation_status == ConfirmationStatus.REJECTED:
            raise TaskConfirmationError("Task has already been rejected.")

        task.status = TaskStatus.WAITING_CONFIRMATION
        task.confirmation_status = ConfirmationStatus.PENDING
        return task

    def confirm(self, task: Task) -> Task:
        if task.status != TaskStatus.WAITING_CONFIRMATION:
            raise TaskConfirmationError(
                f"Task status cannot be confirmed: {task.status.value}"
            )

        if task.confirmation_status != ConfirmationStatus.PENDING:
            raise TaskConfirmationError(
                "Task confirmation status must be PENDING before confirm."
            )

        task.confirmation_status = ConfirmationStatus.CONFIRMED
        task.status = TaskStatus.PLANNED
        return task

    def reject(self, task: Task) -> Task:
        if task.status != TaskStatus.WAITING_CONFIRMATION:
            raise TaskConfirmationError(
                f"Task status cannot be rejected: {task.status.value}"
            )

        if task.confirmation_status != ConfirmationStatus.PENDING:
            raise TaskConfirmationError(
                "Task confirmation status must be PENDING before reject."
            )

        task.confirmation_status = ConfirmationStatus.REJECTED
        task.status = TaskStatus.CANCELLED
        return task
