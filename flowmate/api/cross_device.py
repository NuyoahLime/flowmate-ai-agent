from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Query

from flowmate.cross_device import (
    CrossDeviceAuthorizationError,
    CrossDeviceConflictError,
    CrossDeviceNotFoundError,
    CrossDeviceValidationError,
    DeviceCapability,
    DeviceRegistryService,
    DeviceRouter,
    Handoff,
    HandoffService,
    HandoffStatus,
    SQLiteCrossDeviceRepository,
    TaskDeviceStateService,
    seed_demo_devices,
)


router = APIRouter(prefix="/api/v1", tags=["cross-device"])


class TaskDeviceStateRequest(BaseModel):
    owner_user_id: str
    origin_device_id: str


class HandoffCreateRequest(BaseModel):
    user_id: str
    source_device_id: str
    target_device_id: str
    expected_version: int
    required_capability: DeviceCapability = DeviceCapability.NAVIGATION


class HandoffDecisionRequest(BaseModel):
    device_id: str
    expected_version: int


@router.post("/cross-device/demo-seed")
def seed_cross_device_demo():
    repository = SQLiteCrossDeviceRepository()
    user, phone, car = seed_demo_devices(repository)
    return {
        "user": user.model_dump(mode="json"),
        "devices": [
            phone.model_dump(mode="json"),
            car.model_dump(mode="json"),
        ],
        "identity_model": "demo_only_no_production_auth",
    }


@router.get("/users/{user_id}/devices")
def list_user_devices(user_id: str):
    return _call(
        lambda: [
            device.model_dump(mode="json")
            for device in DeviceRegistryService().list_user_devices(user_id)
        ]
    )


@router.get("/devices/{device_id}/handoffs")
def list_incoming_handoffs(
    device_id: str,
    status: HandoffStatus | None = Query(default=None),
):
    return _call(
        lambda: [
            _handoff_payload(handoff)
            for handoff in HandoffService().list_incoming(device_id, status=status)
        ]
    )


@router.get("/devices/{device_id}")
def get_device(device_id: str):
    return _call(
        lambda: DeviceRegistryService().get_device(device_id).model_dump(mode="json")
    )


@router.post("/devices/{device_id}/heartbeat")
def heartbeat_device(device_id: str):
    return _call(
        lambda: DeviceRegistryService()
        .update_presence(device_id)
        .model_dump(mode="json")
    )


@router.post("/tasks/{task_id}/device-state")
def initialize_task_device_state(task_id: str, request: TaskDeviceStateRequest):
    return _call(
        lambda: TaskDeviceStateService()
        .initialize(
            task_id=task_id,
            owner_user_id=request.owner_user_id,
            origin_device_id=request.origin_device_id,
        )
        .model_dump(mode="json")
    )


@router.get("/tasks/{task_id}/device-state")
def get_task_device_state(task_id: str):
    return _call(
        lambda: TaskDeviceStateService().get(task_id).model_dump(mode="json")
    )


@router.get("/tasks/{task_id}/device-route")
def get_task_device_route(task_id: str):
    return _call(
        lambda: DeviceRouter().recommend(task_id).model_dump(mode="json")
    )


@router.post("/tasks/{task_id}/handoffs")
def create_handoff(task_id: str, request: HandoffCreateRequest):
    return _call(
        lambda: _handoff_payload(
            HandoffService().create_handoff(
                task_id=task_id,
                user_id=request.user_id,
                source_device_id=request.source_device_id,
                target_device_id=request.target_device_id,
                required_capability=request.required_capability,
                expected_version=request.expected_version,
            )
        )
    )


@router.get("/tasks/{task_id}/handoffs")
def list_task_handoffs(task_id: str):
    return _call(
        lambda: [
            _handoff_payload(handoff)
            for handoff in HandoffService().list_task_handoffs(task_id)
        ]
    )


@router.post("/handoffs/{handoff_id}/accept")
def accept_handoff(handoff_id: str, request: HandoffDecisionRequest):
    def action():
        handoff, state, changed = HandoffService().accept_handoff(
            handoff_id,
            target_device_id=request.device_id,
            expected_version=request.expected_version,
        )
        return {
            **_handoff_payload(handoff),
            "state_transition_applied": changed,
            "device_state": state.model_dump(mode="json"),
        }

    return _call(action)


@router.post("/handoffs/{handoff_id}/reject")
def reject_handoff(handoff_id: str, request: HandoffDecisionRequest):
    def action():
        handoff, state = HandoffService().reject_handoff(
            handoff_id,
            target_device_id=request.device_id,
            expected_version=request.expected_version,
        )
        return {
            **_handoff_payload(handoff),
            "device_state": state.model_dump(mode="json"),
        }

    return _call(action)


@router.post("/handoffs/{handoff_id}/cancel")
def cancel_handoff(handoff_id: str, request: HandoffDecisionRequest):
    def action():
        handoff, state = HandoffService().cancel_handoff(
            handoff_id,
            source_device_id=request.device_id,
            expected_version=request.expected_version,
        )
        return {
            **_handoff_payload(handoff),
            "device_state": state.model_dump(mode="json"),
        }

    return _call(action)


def _handoff_payload(handoff: Handoff) -> dict:
    return {
        "task_id": handoff.task_id,
        "handoff_id": handoff.id,
        "user_id": handoff.user_id,
        "source_device": handoff.source_device_id,
        "target_device": handoff.target_device_id,
        "required_capability": handoff.required_capability.value,
        "status": handoff.status.value,
        "task_version": handoff.task_version,
        "context": handoff.context.model_dump(mode="json"),
        "created_at": handoff.created_at.isoformat(),
        "accepted_at": handoff.accepted_at.isoformat() if handoff.accepted_at else None,
        "rejected_at": handoff.rejected_at.isoformat() if handoff.rejected_at else None,
        "cancelled_at": handoff.cancelled_at.isoformat() if handoff.cancelled_at else None,
    }


def _call(action):
    try:
        return action()
    except CrossDeviceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CrossDeviceAuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except CrossDeviceConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CrossDeviceValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
