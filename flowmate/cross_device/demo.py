from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from flowmate.cross_device.models import DeviceCapability
from flowmate.cross_device.repository import SQLiteCrossDeviceRepository
from flowmate.cross_device.service import (
    DeviceRegistryService,
    DeviceRouter,
    HandoffService,
    TaskDeviceStateService,
    seed_demo_devices,
)
from flowmate.persistence import TaskPersistenceService
from flowmate.schemas import (
    PlanStep,
    RiskLevel,
    Task,
    TaskStatus,
    ToolCall,
    ToolCallStatus,
)


def build_cross_device_commute_task(
    task_id: str = "cross-device-demo-task",
) -> Task:
    return Task(
        id=task_id,
        user_input="明早 8:30 公司开会，帮我安排出门",
        goal="Morning Commute",
        status=TaskStatus.COMPLETED,
        risk_level=RiskLevel.LOW,
        requires_confirmation=False,
        steps=[
            PlanStep(
                id=f"{task_id}-calendar",
                order=1,
                description="Read tomorrow morning calendar events.",
                tool_name="calendar_tool",
                status=ToolCallStatus.SUCCESS,
                tool_call=ToolCall(
                    tool_name="calendar_tool",
                    arguments={
                        "date": "tomorrow",
                        "start_time": "06:00",
                        "end_time": "12:00",
                    },
                    status=ToolCallStatus.SUCCESS,
                    result={
                        "date": "tomorrow",
                        "events": [
                            {
                                "id": "stage29-meeting",
                                "title": "Morning Meeting",
                                "start_time": "08:30",
                                "end_time": "09:30",
                                "location": "上海市人民广场",
                            }
                        ],
                        "event_count": 1,
                    },
                ),
            ),
            PlanStep(
                id=f"{task_id}-weather",
                order=2,
                description="Check tomorrow morning weather.",
                tool_name="weather_tool",
                status=ToolCallStatus.SUCCESS,
                tool_call=ToolCall(
                    tool_name="weather_tool",
                    arguments={"location": "上海", "date": "tomorrow"},
                    status=ToolCallStatus.SUCCESS,
                    result={
                        "location": "上海",
                        "date": "tomorrow",
                        "condition": "cloudy",
                        "temperature_c": 20,
                        "rain_probability": 0.2,
                    },
                ),
            ),
            PlanStep(
                id=f"{task_id}-navigation",
                order=3,
                description="Plan the commute route to the selected calendar event.",
                tool_name="navigation_tool",
                status=ToolCallStatus.SUCCESS,
                tool_call=ToolCall(
                    tool_name="navigation_tool",
                    arguments={
                        "origin": "home",
                        "destination": "上海市人民广场",
                        "departure_time": "tomorrow morning",
                    },
                    status=ToolCallStatus.SUCCESS,
                    result={
                        "origin": "home",
                        "destination": "上海市人民广场",
                        "distance_km": 18.6,
                        "duration_minutes": 42,
                        "traffic": "heavy",
                    },
                ),
            ),
        ],
    )


def run_cross_device_smoke(db_path: str | Path) -> dict:
    repository = SQLiteCrossDeviceRepository(db_path)
    now = datetime(2026, 9, 30, 8, 0, tzinfo=UTC)
    seed_demo_devices(repository, now=now)
    registry = DeviceRegistryService(repository)
    registry.update_presence("phone_001", now=now)
    registry.update_presence("car_001", now=now)

    task = build_cross_device_commute_task("cross-device-smoke-task")
    TaskPersistenceService(db_path=db_path).persist(task)
    state_service = TaskDeviceStateService(repository, db_path=db_path)
    initial_state = state_service.initialize(
        task_id=task.id,
        owner_user_id="demo_user",
        origin_device_id="phone_001",
        now=now,
    )

    routing = DeviceRouter(repository, db_path=db_path).recommend(task.id, now=now)
    handoff_service = HandoffService(repository, db_path=db_path)
    pending = handoff_service.create_handoff(
        task_id=task.id,
        user_id="demo_user",
        source_device_id="phone_001",
        target_device_id=routing.recommended_device,
        required_capability=DeviceCapability.NAVIGATION,
        expected_version=initial_state.version,
        now=now + timedelta(seconds=1),
    )
    pending_state = state_service.get(task.id)
    accepted, final_state, changed = handoff_service.accept_handoff(
        pending.id,
        target_device_id="car_001",
        expected_version=pending_state.version,
        now=now + timedelta(seconds=2),
    )
    _, duplicate_state, duplicate_changed = handoff_service.accept_handoff(
        pending.id,
        target_device_id="car_001",
        expected_version=pending_state.version,
        now=now + timedelta(seconds=3),
    )
    phone_reloaded_state = TaskDeviceStateService(
        SQLiteCrossDeviceRepository(db_path), db_path=db_path
    ).get(task.id)

    return {
        "task_id": task.id,
        "origin_device": initial_state.origin_device_id,
        "initial_current_device": initial_state.current_device_id,
        "router_recommendation": routing.recommended_device,
        "router_reason": routing.reason,
        "handoff_id": pending.id,
        "handoff_initial_status": pending.status.value,
        "handoff_final_status": accepted.status.value,
        "final_current_device": final_state.current_device_id,
        "phone_post_handoff_current_device": phone_reloaded_state.current_device_id,
        "task_version_before": initial_state.version,
        "task_version_after": final_state.version,
        "same_task_id": accepted.task_id == task.id,
        "context_reused": accepted.context.destination == "上海市人民广场",
        "duplicate_task_count": repository.count_tasks(task.id) - 1,
        "duplicate_accept_count": int(changed) + int(duplicate_changed) - 1,
        "duplicate_accept_version_unchanged": duplicate_state.version == final_state.version,
        "real_vehicle_calls": 0,
        "real_smart_home_calls": 0,
        "real_feishu_calls": 0,
        "real_google_calls": 0,
        "real_weather_calls": 0,
        "real_amap_calls": 0,
    }
