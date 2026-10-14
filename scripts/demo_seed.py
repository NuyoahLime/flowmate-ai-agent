import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flowmate.agent import RiskPolicy, TaskConfirmationService
from flowmate.persistence import TaskPersistenceService
from flowmate.schemas import PlanStep, RiskLevel, Task, TaskStatus, ToolCall, ToolCallStatus
from flowmate.triggers import (
    CalendarTriggerRegistrationService,
    CalendarTriggerSourceEvent,
    SQLiteTriggerRepository,
)


def main() -> int:
    persistence = TaskPersistenceService()
    persistence.persist(_completed_commute_task())
    notification_task = _pending_notification_task()
    persistence.persist(notification_task)
    persistence.persist(_high_risk_vehicle_task())
    _seed_triggers()
    print("Demo seed completed.")
    return 0


def _completed_commute_task() -> Task:
    return Task(
        id="demo-seed-task-morning-commute",
        user_input="明早 8:30 公司开会，帮我安排好出门并提醒我。",
        goal="Completed demo morning commute plan.",
        status=TaskStatus.COMPLETED,
        risk_level=RiskLevel.LOW,
        requires_confirmation=False,
        steps=[
            PlanStep(
                id="demo-seed-step-calendar",
                order=1,
                description="Read tomorrow morning calendar events.",
                tool_name="calendar_tool",
                status=ToolCallStatus.SUCCESS,
                tool_call=ToolCall(
                    tool_name="calendar_tool",
                    arguments={"date": "tomorrow", "start_time": "06:00", "end_time": "12:00"},
                    status=ToolCallStatus.SUCCESS,
                    result={
                        "events": [
                            {
                                "id": "demo-event-morning-meeting",
                                "title": "Morning Meeting",
                                "start_time": "08:30",
                                "end_time": "09:30",
                                "location": "人民广场",
                            }
                        ],
                        "event_count": 1,
                    },
                ),
            ),
            PlanStep(
                id="demo-seed-step-weather",
                order=2,
                description="Check weather.",
                tool_name="weather_tool",
                status=ToolCallStatus.SUCCESS,
                tool_call=ToolCall(
                    tool_name="weather_tool",
                    arguments={"location": "current_city", "date": "tomorrow"},
                    status=ToolCallStatus.SUCCESS,
                    result={
                        "location": "current_city",
                        "date": "tomorrow",
                        "condition": "rain",
                        "temperature_c": 18,
                        "rain_probability": 0.8,
                    },
                ),
            ),
            PlanStep(
                id="demo-seed-step-navigation",
                order=3,
                description="Plan route.",
                tool_name="navigation_tool",
                status=ToolCallStatus.SUCCESS,
                tool_call=ToolCall(
                    tool_name="navigation_tool",
                    arguments={
                        "origin": "home",
                        "destination": "人民广场",
                        "departure_time": "tomorrow morning",
                    },
                    status=ToolCallStatus.SUCCESS,
                    result={
                        "origin": "home",
                        "destination": "人民广场",
                        "distance_km": 18.6,
                        "duration_minutes": 42,
                        "traffic": "heavy",
                    },
                ),
            ),
        ],
    )


def _pending_notification_task() -> Task:
    task = Task(
        id="demo-seed-task-notification-pending",
        user_input="提醒我通勤方案已经准备好。",
        goal="Pending mock notification.",
        status=TaskStatus.PLANNED,
        risk_level=RiskLevel.LOW,
        requires_confirmation=False,
        steps=[
            PlanStep(
                id="demo-seed-step-notification",
                order=1,
                description="Send mock notification.",
                tool_name="notification_tool",
                tool_call=ToolCall(
                    tool_name="notification_tool",
                    arguments={
                        "title": "Route ready",
                        "message": "Your commute route is ready.",
                        "channel": "mobile",
                    },
                ),
            )
        ],
    )
    RiskPolicy().apply_to_task(task)
    TaskConfirmationService().request_confirmation(task)
    return task


def _high_risk_vehicle_task() -> Task:
    task = Task(
        id="demo-seed-task-vehicle-high-risk",
        user_input="解锁我的车",
        goal="High-risk mock vehicle unlock.",
        status=TaskStatus.PLANNED,
        risk_level=RiskLevel.LOW,
        requires_confirmation=False,
        steps=[
            PlanStep(
                id="demo-seed-step-vehicle",
                order=1,
                description="Unlock mock vehicle.",
                tool_name="vehicle_tool",
                tool_call=ToolCall(
                    tool_name="vehicle_tool",
                    arguments={"vehicle_id": "my-car", "action": "unlock"},
                ),
            )
        ],
    )
    RiskPolicy().apply_to_task(task)
    TaskConfirmationService().request_confirmation(task)
    return task


def _seed_triggers() -> None:
    repository = SQLiteTriggerRepository()
    service = CalendarTriggerRegistrationService(repository, lead_time_minutes=60)
    active = service.register_event(
        CalendarTriggerSourceEvent(
            id="demo-seed-active-event",
            summary="Morning Meeting",
            start=datetime.fromisoformat("2026-08-12T09:00:00+08:00"),
            location="人民广场",
        ),
        now=datetime.fromisoformat("2026-08-12T07:29:00+08:00"),
    )
    fired = service.register_event(
        CalendarTriggerSourceEvent(
            id="demo-seed-fired-event",
            summary="Interview",
            start=datetime.fromisoformat("2026-08-12T08:30:00+08:00"),
            location="公司",
        ),
        now=datetime.fromisoformat("2026-08-12T07:29:00+08:00"),
    )
    if fired is not None:
        from flowmate.triggers import ProactiveTriggerService

        ProactiveTriggerService(repository).tick(now=datetime.fromisoformat("2026-08-12T07:30:00+08:00"))
    assert active is not None


if __name__ == "__main__":
    raise SystemExit(main())
