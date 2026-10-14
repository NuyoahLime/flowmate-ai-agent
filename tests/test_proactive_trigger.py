from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from flowmate.persistence import SCHEMA_VERSION, SQLiteTaskRepository
from flowmate.persistence.database import _migrate_to_v1
from flowmate.schemas import (
    PlanStep,
    RiskLevel,
    Task,
    TaskStatus,
    ToolCall,
    TriggerStatus,
    TriggerType,
)
from flowmate.tools.calendar import CalendarEvent
from flowmate.triggers import (
    CalendarTriggerRegistrationService,
    CalendarTriggerSourceEvent,
    ProactiveTaskFactory,
    ProactiveTriggerService,
    SQLiteTriggerRepository,
    TriggerEvaluationOutcome,
    TriggerEvaluator,
)


ZONE = ZoneInfo("Asia/Shanghai")
EVENT_START = datetime(2026, 8, 12, 8, 30, tzinfo=ZONE)
DUE_NOW = datetime(2026, 8, 12, 7, 30, tzinfo=ZONE)
PRE_DUE_NOW = datetime(2026, 8, 12, 7, 29, tzinfo=ZONE)
EXPIRED_NOW = datetime(2026, 8, 12, 8, 30, tzinfo=ZONE)


def create_repositories(tmp_path):
    db_path = tmp_path / "flowmate_trigger_test.db"
    return SQLiteTriggerRepository(db_path), SQLiteTaskRepository(db_path)


def source_event(
    *,
    event_id: str = "event-morning-001",
    location: str | None = "人民广场",
    start: datetime | None = EVENT_START,
    all_day: bool = False,
) -> CalendarTriggerSourceEvent:
    return CalendarTriggerSourceEvent(
        id=event_id,
        summary="Morning Meeting",
        start=start,
        location=location,
        all_day=all_day,
    )


def register_due_trigger(tmp_path, *, event_id: str = "event-morning-001"):
    trigger_repository, task_repository = create_repositories(tmp_path)
    service = CalendarTriggerRegistrationService(
        trigger_repository,
        lead_time_minutes=60,
    )
    trigger = service.register_event(source_event(event_id=event_id), now=PRE_DUE_NOW)
    assert trigger is not None
    return trigger_repository, task_repository, trigger


def test_stage25_schema_upgrades_through_current_schema(tmp_path):
    db_path = tmp_path / "stage25.db"
    import sqlite3

    with sqlite3.connect(db_path) as connection:
        _migrate_to_v1(connection)
        connection.execute("PRAGMA user_version = 1")

    SQLiteTriggerRepository(db_path)
    with sqlite3.connect(db_path) as connection:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        triggers = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'triggers'"
        ).fetchone()

    assert version == SCHEMA_VERSION == 3
    assert triggers is not None


def test_trigger_domain_fields_and_type(tmp_path):
    trigger_repository, _, trigger = register_due_trigger(tmp_path)

    assert trigger.trigger_type == TriggerType.CALENDAR_EVENT_LEAD_TIME
    assert trigger.status == TriggerStatus.ACTIVE
    assert trigger.source_event_id == "event-morning-001"
    assert trigger.source_event_location == "人民广场"
    assert trigger.lead_time_minutes == 60
    assert trigger.trigger_at == DUE_NOW
    assert trigger_repository.get(trigger.id).id == trigger.id


def test_register_calendar_event_from_existing_calendar_model(tmp_path):
    trigger_repository, _ = create_repositories(tmp_path)
    service = CalendarTriggerRegistrationService(trigger_repository, lead_time_minutes=60)

    trigger = service.register_calendar_event(
        CalendarEvent(
            id="calendar-event-001",
            title="Morning Meeting",
            start_time="08:30",
            end_time="09:30",
            location="人民广场",
        ),
        event_date=date(2026, 8, 12),
        timezone="Asia/Shanghai",
        now=PRE_DUE_NOW,
    )

    assert trigger is not None
    assert trigger.source_event_start == EVENT_START


def test_missing_location_event_is_not_registered(tmp_path):
    trigger_repository, _ = create_repositories(tmp_path)
    service = CalendarTriggerRegistrationService(trigger_repository, lead_time_minutes=60)

    trigger = service.register_event(source_event(location=None), now=PRE_DUE_NOW)

    assert trigger is None
    assert trigger_repository.list_triggers() == []


def test_all_day_event_is_not_registered(tmp_path):
    trigger_repository, _ = create_repositories(tmp_path)
    service = CalendarTriggerRegistrationService(trigger_repository, lead_time_minutes=60)

    trigger = service.register_event(source_event(start=None, all_day=True), now=PRE_DUE_NOW)

    assert trigger is None
    assert trigger_repository.list_triggers() == []


def test_duplicate_registration_returns_one_trigger(tmp_path):
    trigger_repository, _ = create_repositories(tmp_path)
    service = CalendarTriggerRegistrationService(trigger_repository, lead_time_minutes=60)

    first = service.register_event(source_event(), now=PRE_DUE_NOW)
    second = service.register_event(source_event(), now=PRE_DUE_NOW)

    assert first.id == second.id
    assert len(trigger_repository.list_triggers()) == 1


def test_event_without_id_uses_deterministic_fingerprint(tmp_path):
    trigger_repository, _ = create_repositories(tmp_path)
    service = CalendarTriggerRegistrationService(trigger_repository, lead_time_minutes=60)

    first = service.register_event(source_event(event_id=None), now=PRE_DUE_NOW)
    second = service.register_event(source_event(event_id=None), now=PRE_DUE_NOW)

    assert first.source_event_id.startswith("event-fingerprint-")
    assert first.id == second.id
    assert len(trigger_repository.list_triggers()) == 1


def test_evaluator_pre_due_due_and_expired(tmp_path):
    _, _, trigger = register_due_trigger(tmp_path)
    evaluator = TriggerEvaluator()

    assert (
        evaluator.evaluate(trigger, now=PRE_DUE_NOW)
        == TriggerEvaluationOutcome.NOT_DUE
    )
    assert evaluator.evaluate(trigger, now=DUE_NOW) == TriggerEvaluationOutcome.DUE
    assert (
        evaluator.evaluate(trigger, now=EXPIRED_NOW)
        == TriggerEvaluationOutcome.EXPIRED
    )


def test_repository_list_due(tmp_path):
    trigger_repository, _, trigger = register_due_trigger(tmp_path)

    assert trigger_repository.list_due(now=PRE_DUE_NOW) == []
    assert [item.id for item in trigger_repository.list_due(now=DUE_NOW)] == [trigger.id]


def test_tick_fires_due_trigger_and_persists_task(tmp_path):
    trigger_repository, task_repository, trigger = register_due_trigger(tmp_path)

    result = ProactiveTriggerService(trigger_repository).tick(now=DUE_NOW)
    fired = trigger_repository.get(trigger.id)
    task = task_repository.get_task(result.generated_task_ids[0])

    assert result.generated_task_ids == [fired.generated_task_id]
    assert fired.status == TriggerStatus.FIRED
    assert fired.fired_at == DUE_NOW.astimezone(UTC)
    assert task is not None
    assert task.status == TaskStatus.PLANNED
    assert task.risk_level == RiskLevel.LOW


def test_proactive_task_uses_trigger_location_for_navigation(tmp_path):
    trigger_repository, task_repository, _ = register_due_trigger(tmp_path)

    result = ProactiveTriggerService(trigger_repository).tick(now=DUE_NOW)
    task = task_repository.get_task(result.generated_task_ids[0])
    navigation_steps = [step for step in task.steps if step.tool_name == "navigation_tool"]

    assert navigation_steps
    assert navigation_steps[0].tool_call.arguments["destination"] == "人民广场"


def test_proactive_task_includes_weather_and_no_notification(tmp_path):
    trigger_repository, task_repository, _ = register_due_trigger(tmp_path)

    result = ProactiveTriggerService(trigger_repository).tick(now=DUE_NOW)
    task = task_repository.get_task(result.generated_task_ids[0])

    assert "weather_tool" in [step.tool_name for step in task.steps]
    assert "notification_tool" not in [step.tool_name for step in task.steps]


def test_pre_due_tick_creates_no_task(tmp_path):
    trigger_repository, task_repository, trigger = register_due_trigger(tmp_path)

    result = ProactiveTriggerService(trigger_repository).tick(now=PRE_DUE_NOW)

    assert result.generated_task_ids == []
    assert trigger_repository.get(trigger.id).status == TriggerStatus.ACTIVE
    assert task_repository.list_tasks() == []


def test_expired_tick_marks_trigger_expired_and_creates_no_task(tmp_path):
    trigger_repository, task_repository, trigger = register_due_trigger(tmp_path)

    result = ProactiveTriggerService(trigger_repository).tick(now=EXPIRED_NOW)

    assert result.expired_trigger_ids == [trigger.id]
    assert trigger_repository.get(trigger.id).status == TriggerStatus.EXPIRED
    assert task_repository.list_tasks() == []


def test_duplicate_fire_prevention_on_repeated_tick(tmp_path):
    trigger_repository, task_repository, trigger = register_due_trigger(tmp_path)
    service = ProactiveTriggerService(trigger_repository)

    first = service.tick(now=DUE_NOW)
    second = service.tick(now=DUE_NOW + timedelta(minutes=1))
    third = service.tick(now=DUE_NOW + timedelta(minutes=2))

    assert len(first.generated_task_ids) == 1
    assert second.generated_task_ids == []
    assert third.generated_task_ids == []
    assert len(task_repository.list_tasks()) == 1
    assert trigger_repository.get(trigger.id).generated_task_id == first.generated_task_ids[0]


def test_restart_duplicate_prevention(tmp_path):
    trigger_repository, task_repository, trigger = register_due_trigger(tmp_path)
    first = ProactiveTriggerService(trigger_repository).tick(now=DUE_NOW)

    restarted_trigger_repository = SQLiteTriggerRepository(trigger_repository.db_path)
    second = ProactiveTriggerService(restarted_trigger_repository).tick(
        now=DUE_NOW + timedelta(minutes=1)
    )

    assert len(first.generated_task_ids) == 1
    assert second.generated_task_ids == []
    assert len(task_repository.list_tasks()) == 1
    assert restarted_trigger_repository.get(trigger.id).generated_task_id == first.generated_task_ids[0]


class BrokenTaskFactory(ProactiveTaskFactory):
    def create_task(self, trigger):
        return Task(
            id="task-broken",
            user_input="broken proactive task",
            goal="broken",
            status=TaskStatus.PLANNED,
            steps=[
                PlanStep(
                    id="duplicate-step",
                    order=1,
                    description="broken one",
                    tool_name="weather_tool",
                    tool_call=ToolCall(
                        tool_name="weather_tool",
                        arguments={"location": "上海", "date": "tomorrow"},
                    ),
                ),
                PlanStep(
                    id="duplicate-step",
                    order=2,
                    description="broken two",
                    tool_name="navigation_tool",
                    tool_call=ToolCall(
                        tool_name="navigation_tool",
                        arguments={
                            "origin": "home",
                            "destination": "人民广场",
                            "departure_time": "tomorrow morning",
                        },
                    ),
                ),
            ],
        )


def test_task_creation_failure_rolls_back_trigger_fire(tmp_path):
    trigger_repository, task_repository, trigger = register_due_trigger(tmp_path)

    result = ProactiveTriggerService(
        trigger_repository,
        task_factory=BrokenTaskFactory(),
    ).tick(now=DUE_NOW)

    assert result.generated_task_ids == []
    assert result.errors
    assert trigger_repository.get(trigger.id).status == TriggerStatus.ACTIVE
    assert trigger_repository.get(trigger.id).generated_task_id is None
    assert task_repository.get_task("task-broken") is None


def test_fail_isolation_keeps_other_due_trigger_working(tmp_path):
    trigger_repository, task_repository, _ = register_due_trigger(
        tmp_path,
        event_id="event-broken",
    )
    service = CalendarTriggerRegistrationService(trigger_repository, lead_time_minutes=60)
    service.register_event(
        source_event(event_id="event-good", location="公司"),
        now=PRE_DUE_NOW,
    )

    class SometimesBrokenFactory(ProactiveTaskFactory):
        def create_task(self, trigger):
            if trigger.source_event_id == "event-broken":
                return BrokenTaskFactory().create_task(trigger)
            return super().create_task(trigger)

    result = ProactiveTriggerService(
        trigger_repository,
        task_factory=SometimesBrokenFactory(),
    ).tick(now=DUE_NOW)

    assert len(result.errors) == 1
    assert len(result.generated_task_ids) == 1
    assert len(task_repository.list_tasks()) == 1


def test_trigger_history_query_by_status(tmp_path):
    trigger_repository, _, trigger = register_due_trigger(tmp_path)
    ProactiveTriggerService(trigger_repository).tick(now=EXPIRED_NOW)

    assert trigger_repository.list_triggers(status=TriggerStatus.ACTIVE) == []
    expired = trigger_repository.list_triggers(status=TriggerStatus.EXPIRED)
    assert [item.id for item in expired] == [trigger.id]


def test_trigger_api_list_get_and_tick(monkeypatch, tmp_path):
    db_path = tmp_path / "flowmate_trigger_api.db"
    monkeypatch.setenv("FLOWMATE_DB_PATH", str(db_path))
    trigger_repository = SQLiteTriggerRepository(db_path)
    service = CalendarTriggerRegistrationService(trigger_repository, lead_time_minutes=60)
    trigger = service.register_event(source_event(), now=PRE_DUE_NOW)

    from main import app

    client = TestClient(app)
    listed = client.get("/api/v1/triggers")
    detail = client.get(f"/api/v1/triggers/{trigger.id}")
    safe_now = DUE_NOW.astimezone(UTC).isoformat().replace("+00:00", "Z")
    tick = client.post(f"/api/v1/triggers/tick?now={safe_now}")

    assert listed.status_code == 200
    assert listed.json()[0]["id"] == trigger.id
    assert detail.status_code == 200
    assert detail.json()["id"] == trigger.id
    assert tick.status_code == 200
    assert tick.json()["generated_task_ids"]
