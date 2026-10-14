from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel

from flowmate.agent import TaskConfirmationError, TaskConfirmationService, TaskExecutionError
from flowmate.demo import DemoTaskService
from flowmate.cross_device import (
    CrossDeviceAuthorizationError,
    CrossDeviceConflictError,
    CrossDeviceNotFoundError,
    TaskDeviceStateService,
)
from flowmate.persistence import TaskPersistenceService


router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


class CoordinatedConfirmationRequest(BaseModel):
    device_id: str
    expected_version: int


@router.get("")
def list_tasks(limit: int = Query(default=50, ge=1, le=100)):
    return [task.model_dump(mode="json") for task in TaskPersistenceService().list_history(limit=limit)]


@router.get("/{task_id}")
def get_task(task_id: str):
    task = TaskPersistenceService().load(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    return task.model_dump(mode="json")


@router.post("/{task_id}/confirm")
def confirm_task(
    task_id: str,
    request: CoordinatedConfirmationRequest | None = Body(default=None),
):
    persistence = TaskPersistenceService()
    task = persistence.load(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    try:
        if request is None:
            TaskConfirmationService().confirm(task)
        else:
            TaskDeviceStateService().claim_confirmation(
                task_id=task_id,
                device_id=request.device_id,
                expected_version=request.expected_version,
                confirmed=True,
            )
            task = persistence.load(task_id)
            assert task is not None
        executed = DemoTaskService(persistence).create_executor().execute(task)
    except CrossDeviceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CrossDeviceAuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except CrossDeviceConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (TaskConfirmationError, TaskExecutionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    persistence.persist(executed)
    return executed.model_dump(mode="json")


@router.post("/{task_id}/reject")
def reject_task(
    task_id: str,
    request: CoordinatedConfirmationRequest | None = Body(default=None),
):
    persistence = TaskPersistenceService()
    task = persistence.load(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    try:
        if request is None:
            rejected = TaskConfirmationService().reject(task)
        else:
            TaskDeviceStateService().claim_confirmation(
                task_id=task_id,
                device_id=request.device_id,
                expected_version=request.expected_version,
                confirmed=False,
            )
            rejected = persistence.load(task_id)
            assert rejected is not None
    except CrossDeviceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CrossDeviceAuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except CrossDeviceConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except TaskConfirmationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    persistence.persist(rejected)
    return rejected.model_dump(mode="json")
