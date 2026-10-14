from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from flowmate.cross_device.errors import (
    CrossDeviceAuthorizationError,
    CrossDeviceConflictError,
    CrossDeviceNotFoundError,
    CrossDeviceValidationError,
)
from flowmate.cross_device.models import (
    Device,
    DeviceCapability,
    DeviceStatus,
    DeviceType,
    Handoff,
    HandoffContext,
    HandoffStatus,
    RoutingDecision,
    TaskDeviceState,
    User,
)
from flowmate.cross_device.repository import SQLiteCrossDeviceRepository, utc_now
from flowmate.persistence import TaskPersistenceService
from flowmate.schemas import Task


class DeviceRegistryService:
    def __init__(
        self,
        repository: SQLiteCrossDeviceRepository | None = None,
        *,
        db_path: str | Path | None = None,
        presence_timeout_seconds: int = 10,
    ) -> None:
        self.repository = repository or SQLiteCrossDeviceRepository(db_path)
        self.presence_timeout = timedelta(seconds=presence_timeout_seconds)

    def register_user(
        self,
        user_id: str,
        display_name: str,
        *,
        now: datetime | None = None,
    ) -> User:
        return self.repository.save_user(
            User(id=user_id, display_name=display_name, created_at=now or utc_now())
        )

    def register_device(
        self,
        *,
        device_id: str,
        user_id: str,
        device_type: DeviceType,
        display_name: str,
        capabilities: list[DeviceCapability],
        now: datetime | None = None,
    ) -> Device:
        if self.repository.get_user(user_id) is None:
            raise CrossDeviceNotFoundError("User not found.")
        created_at = now or utc_now()
        return self.repository.save_device(
            Device(
                id=device_id,
                user_id=user_id,
                device_type=device_type,
                display_name=display_name,
                status=DeviceStatus.OFFLINE,
                created_at=created_at,
            ),
            capabilities,
        )

    def get_device(self, device_id: str, *, now: datetime | None = None) -> Device:
        device = self.repository.get_device(device_id)
        if device is None:
            raise CrossDeviceNotFoundError("Device not found.")
        return self._with_effective_presence(device, now or utc_now())

    def list_user_devices(
        self, user_id: str, *, now: datetime | None = None
    ) -> list[Device]:
        if self.repository.get_user(user_id) is None:
            raise CrossDeviceNotFoundError("User not found.")
        checked_at = now or utc_now()
        return [
            self._with_effective_presence(device, checked_at)
            for device in self.repository.list_user_devices(user_id)
        ]

    def update_presence(
        self, device_id: str, *, now: datetime | None = None
    ) -> Device:
        checked_at = now or utc_now()
        return self._with_effective_presence(
            self.repository.heartbeat(device_id, seen_at=checked_at), checked_at
        )

    def mark_offline(self, device_id: str) -> Device:
        return self.repository.mark_offline(device_id)

    def get_capabilities(self, device_id: str) -> list[DeviceCapability]:
        return self.get_device(device_id).capabilities

    def _with_effective_presence(self, device: Device, now: datetime) -> Device:
        status = device.status
        if (
            status == DeviceStatus.ONLINE
            and (
                device.last_seen_at is None
                or now.astimezone(UTC) - device.last_seen_at.astimezone(UTC)
                > self.presence_timeout
            )
        ):
            status = DeviceStatus.OFFLINE
        return device.model_copy(update={"status": status})


class TaskDeviceStateService:
    def __init__(
        self,
        repository: SQLiteCrossDeviceRepository | None = None,
        *,
        db_path: str | Path | None = None,
    ) -> None:
        self.repository = repository or SQLiteCrossDeviceRepository(db_path)
        self.tasks = TaskPersistenceService(db_path=db_path)

    def initialize(
        self,
        *,
        task_id: str,
        owner_user_id: str,
        origin_device_id: str,
        now: datetime | None = None,
    ) -> TaskDeviceState:
        if self.tasks.load(task_id) is None:
            raise CrossDeviceNotFoundError("Task not found.")
        device = self.repository.get_device(origin_device_id)
        if device is None:
            raise CrossDeviceNotFoundError("Origin device not found.")
        if device.user_id != owner_user_id:
            raise CrossDeviceAuthorizationError(
                "Origin device does not belong to the task owner."
            )
        existing = self.repository.get_task_device_state(task_id)
        if existing is not None:
            if (
                existing.owner_user_id != owner_user_id
                or existing.origin_device_id != origin_device_id
            ):
                raise CrossDeviceConflictError(
                    "Task device state is already initialized with different ownership."
                )
            return existing
        return self.repository.create_task_device_state(
            task_id=task_id,
            owner_user_id=owner_user_id,
            origin_device_id=origin_device_id,
            now=now or utc_now(),
        )

    def get(self, task_id: str) -> TaskDeviceState:
        state = self.repository.get_task_device_state(task_id)
        if state is None:
            raise CrossDeviceNotFoundError("Task device state not found.")
        return state

    def claim_confirmation(
        self,
        *,
        task_id: str,
        device_id: str,
        expected_version: int,
        confirmed: bool,
        now: datetime | None = None,
    ) -> TaskDeviceState:
        return self.repository.claim_confirmation(
            task_id=task_id,
            device_id=device_id,
            expected_version=expected_version,
            confirmed=confirmed,
            now=now or utc_now(),
        )


class DeviceRouter:
    def __init__(
        self,
        repository: SQLiteCrossDeviceRepository | None = None,
        *,
        db_path: str | Path | None = None,
        presence_timeout_seconds: int = 10,
    ) -> None:
        self.repository = repository or SQLiteCrossDeviceRepository(db_path)
        self.registry = DeviceRegistryService(
            self.repository, presence_timeout_seconds=presence_timeout_seconds
        )
        self.tasks = TaskPersistenceService(db_path=db_path)

    def recommend(
        self, task_id: str, *, now: datetime | None = None
    ) -> RoutingDecision:
        state = self.repository.get_task_device_state(task_id)
        if state is None:
            raise CrossDeviceNotFoundError("Task device state not found.")
        task = self.tasks.load(task_id)
        if task is None:
            raise CrossDeviceNotFoundError("Task not found.")
        if not self._has_navigation_context(task):
            return RoutingDecision(
                task_id=task_id,
                recommended_device=state.current_device_id,
                reason="The task has no reusable navigation context; keep it on the current device.",
                capability=DeviceCapability.NAVIGATION,
                available=False,
            )
        candidates = [
            device
            for device in self.registry.list_user_devices(
                state.owner_user_id, now=now or utc_now()
            )
            if device.device_type == DeviceType.CAR
            and device.status == DeviceStatus.ONLINE
            and DeviceCapability.NAVIGATION in device.capabilities
        ]
        if not candidates:
            return RoutingDecision(
                task_id=task_id,
                recommended_device=state.current_device_id,
                reason=(
                    "No online CAR device with NAVIGATION capability is available; "
                    "keep the task on the current device."
                ),
                capability=DeviceCapability.NAVIGATION,
                available=False,
            )
        target = sorted(candidates, key=lambda item: item.id)[0]
        return RoutingDecision(
            task_id=task_id,
            recommended_device=target.id,
            reason=(
                f"{target.id} is online and provides NAVIGATION capability "
                "for the current commute task."
            ),
            capability=DeviceCapability.NAVIGATION,
            available=True,
        )

    @staticmethod
    def _has_navigation_context(task: Task) -> bool:
        return any(
            step.tool_name == "navigation_tool"
            and step.tool_call is not None
            and bool(
                (step.tool_call.result or {}).get("destination")
                or step.tool_call.arguments.get("destination")
            )
            for step in task.steps
        )


class HandoffService:
    def __init__(
        self,
        repository: SQLiteCrossDeviceRepository | None = None,
        *,
        db_path: str | Path | None = None,
        presence_timeout_seconds: int = 10,
    ) -> None:
        self.repository = repository or SQLiteCrossDeviceRepository(db_path)
        self.registry = DeviceRegistryService(
            self.repository, presence_timeout_seconds=presence_timeout_seconds
        )
        self.tasks = TaskPersistenceService(db_path=db_path)

    def create_handoff(
        self,
        *,
        task_id: str,
        user_id: str,
        source_device_id: str,
        target_device_id: str,
        required_capability: DeviceCapability,
        expected_version: int,
        now: datetime | None = None,
    ) -> Handoff:
        checked_at = now or utc_now()
        task = self.tasks.load(task_id)
        if task is None:
            raise CrossDeviceNotFoundError("Task not found.")
        state = self.repository.get_task_device_state(task_id)
        if state is None:
            raise CrossDeviceNotFoundError("Task device state not found.")
        if state.owner_user_id != user_id:
            raise CrossDeviceAuthorizationError("User does not own this task.")
        if state.current_device_id != source_device_id:
            raise CrossDeviceConflictError(
                "Source device does not own the current task surface."
            )
        source = self.registry.get_device(source_device_id, now=checked_at)
        target = self.registry.get_device(target_device_id, now=checked_at)
        if source.user_id != user_id or target.user_id != user_id:
            raise CrossDeviceAuthorizationError(
                "Source and target devices must belong to the task owner."
            )
        if target.status != DeviceStatus.ONLINE:
            raise CrossDeviceConflictError("Target device is offline.")
        if required_capability not in target.capabilities:
            raise CrossDeviceValidationError(
                f"Target device lacks {required_capability.value} capability."
            )
        handoff = Handoff(
            id=f"handoff-{uuid4().hex}",
            task_id=task_id,
            user_id=user_id,
            source_device_id=source_device_id,
            target_device_id=target_device_id,
            required_capability=required_capability,
            status=HandoffStatus.PENDING,
            context=build_handoff_context(task),
            created_at=checked_at,
            task_version=expected_version + 1,
        )
        return self.repository.create_handoff(
            handoff, expected_version=expected_version, now=checked_at
        )

    def accept_handoff(
        self,
        handoff_id: str,
        *,
        target_device_id: str,
        expected_version: int,
        now: datetime | None = None,
    ) -> tuple[Handoff, TaskDeviceState, bool]:
        checked_at = now or utc_now()
        handoff = self.get_handoff(handoff_id)
        if handoff.target_device_id != target_device_id:
            raise CrossDeviceAuthorizationError(
                "Only the target device can accept this handoff."
            )
        target = self.registry.get_device(target_device_id, now=checked_at)
        if target.user_id != handoff.user_id:
            raise CrossDeviceAuthorizationError("Target device belongs to another user.")
        if target.status != DeviceStatus.ONLINE:
            raise CrossDeviceConflictError("Target device is offline.")
        if handoff.required_capability not in target.capabilities:
            raise CrossDeviceValidationError(
                f"Target device lacks {handoff.required_capability.value} capability."
            )
        return self.repository.accept_handoff(
            handoff_id, expected_version=expected_version, now=checked_at
        )

    def reject_handoff(
        self,
        handoff_id: str,
        *,
        target_device_id: str,
        expected_version: int,
        now: datetime | None = None,
    ) -> tuple[Handoff, TaskDeviceState]:
        handoff = self.get_handoff(handoff_id)
        if handoff.target_device_id != target_device_id:
            raise CrossDeviceAuthorizationError(
                "Only the target device can reject this handoff."
            )
        return self.repository.close_handoff(
            handoff_id,
            expected_version=expected_version,
            status=HandoffStatus.REJECTED,
            now=now or utc_now(),
        )

    def cancel_handoff(
        self,
        handoff_id: str,
        *,
        source_device_id: str,
        expected_version: int,
        now: datetime | None = None,
    ) -> tuple[Handoff, TaskDeviceState]:
        handoff = self.get_handoff(handoff_id)
        if handoff.source_device_id != source_device_id:
            raise CrossDeviceAuthorizationError(
                "Only the source device can cancel this handoff."
            )
        return self.repository.close_handoff(
            handoff_id,
            expected_version=expected_version,
            status=HandoffStatus.CANCELLED,
            now=now or utc_now(),
        )

    def get_handoff(self, handoff_id: str) -> Handoff:
        handoff = self.repository.get_handoff(handoff_id)
        if handoff is None:
            raise CrossDeviceNotFoundError("Handoff not found.")
        return handoff

    def list_task_handoffs(self, task_id: str) -> list[Handoff]:
        return self.repository.list_handoffs(task_id=task_id)

    def list_incoming(
        self, device_id: str, *, status: HandoffStatus | None = None
    ) -> list[Handoff]:
        self.registry.get_device(device_id)
        return self.repository.list_handoffs(
            target_device_id=device_id, status=status
        )


def build_handoff_context(task: Task) -> HandoffContext:
    meeting_summary = None
    meeting_start = None
    destination = None
    navigation_summary = None
    for step in task.steps:
        if step.tool_call is None:
            continue
        result = step.tool_call.result or {}
        if step.tool_name == "calendar_tool":
            events = result.get("events") or []
            if events:
                event = events[0]
                meeting_summary = event.get("title")
                meeting_start = event.get("start_time")
                destination = event.get("location")
        elif step.tool_name == "navigation_tool":
            destination = result.get("destination") or step.tool_call.arguments.get(
                "destination", destination
            )
            if result:
                navigation_summary = (
                    f"{result.get('distance_km', '-')} km, "
                    f"{result.get('duration_minutes', '-')} min, "
                    f"traffic {result.get('traffic', 'unknown')}"
                )
    return HandoffContext(
        goal=task.goal,
        meeting_summary=meeting_summary,
        meeting_start=meeting_start,
        destination=destination,
        navigation_summary=navigation_summary,
        risk_level=task.risk_level.value,
        confirmation_status=task.confirmation_status.value,
    )


def seed_demo_devices(
    repository: SQLiteCrossDeviceRepository,
    *,
    now: datetime | None = None,
) -> tuple[User, Device, Device]:
    created_at = now or utc_now()
    registry = DeviceRegistryService(repository)
    user = registry.register_user("demo_user", "FlowMate Demo User", now=created_at)
    phone = registry.register_device(
        device_id="phone_001",
        user_id=user.id,
        device_type=DeviceType.PHONE,
        display_name="Demo Phone",
        capabilities=[
            DeviceCapability.CALENDAR,
            DeviceCapability.WEATHER,
            DeviceCapability.NAVIGATION_VIEW,
            DeviceCapability.NOTIFICATION,
        ],
        now=created_at,
    )
    car = registry.register_device(
        device_id="car_001",
        user_id=user.id,
        device_type=DeviceType.CAR,
        display_name="Car Simulator",
        capabilities=[
            DeviceCapability.NAVIGATION,
            DeviceCapability.VEHICLE_STATUS,
        ],
        now=created_at,
    )
    return user, phone, car


__all__ = [
    "CrossDeviceAuthorizationError",
    "CrossDeviceConflictError",
    "CrossDeviceNotFoundError",
    "CrossDeviceValidationError",
    "DeviceRegistryService",
    "DeviceRouter",
    "HandoffService",
    "TaskDeviceStateService",
    "build_handoff_context",
    "seed_demo_devices",
]
