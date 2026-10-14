import sqlite3

import pytest

from flowmate.agent import (
    StepExecutor,
    TaskConfirmationService,
    TaskExecutionError,
    TaskExecutor,
    ToolExecutor,
)
from flowmate.persistence import (
    PersistenceSerializationError,
    SQLiteTaskRepository,
)
from flowmate.schemas import (
    ConfirmationStatus,
    PlanStep,
    RiskLevel,
    Task,
    TaskStatus,
    ToolCall,
    ToolCallStatus,
)
from flowmate.tools import create_default_registry


def create_repository(tmp_path) -> SQLiteTaskRepository:
    return SQLiteTaskRepository(tmp_path / "flowmate_test.db")


def create_weather_step(
    *,
    step_id: str = "step-weather",
    order: int = 1,
    status: ToolCallStatus = ToolCallStatus.PENDING,
    tool_call_status: ToolCallStatus = ToolCallStatus.PENDING,
    result: dict | None = None,
    error: str | None = None,
) -> PlanStep:
    return PlanStep(
        id=step_id,
        order=order,
        description="检查明早天气",
        tool_name="weather_tool",
        status=status,
        tool_call=ToolCall(
            tool_name="weather_tool",
            arguments={"location": "上海", "date": "tomorrow"},
            status=tool_call_status,
            result=result,
            error=error,
        ),
    )


def create_navigation_step(
    *,
    step_id: str = "step-navigation",
    order: int = 2,
) -> PlanStep:
    return PlanStep(
        id=step_id,
        order=order,
        description="计算到公司的通勤时间",
        tool_name="navigation_tool",
        tool_call=ToolCall(
            tool_name="navigation_tool",
            arguments={
                "origin": "home",
                "destination": "company",
                "departure_time": "tomorrow morning",
            },
        ),
    )


def create_task(
    *,
    task_id: str = "task-persistence",
    goal: str = "安排明早通勤",
    status: TaskStatus = TaskStatus.PLANNED,
    risk_level: RiskLevel = RiskLevel.LOW,
    requires_confirmation: bool = False,
    confirmation_status: ConfirmationStatus = ConfirmationStatus.NOT_REQUIRED,
    steps: list[PlanStep] | None = None,
) -> Task:
    return Task(
        id=task_id,
        user_input="明天早上八点半在公司开会，帮我安排好明早出门",
        goal=goal,
        status=status,
        risk_level=risk_level,
        requires_confirmation=requires_confirmation,
        confirmation_status=confirmation_status,
        steps=steps if steps is not None else [create_weather_step(), create_navigation_step()],
    )


def create_executor() -> TaskExecutor:
    return TaskExecutor(StepExecutor(ToolExecutor(create_default_registry())))


def round_trip(repository: SQLiteTaskRepository, task: Task) -> Task:
    repository.save_task(task)
    loaded = repository.get_task(task.id)
    assert loaded is not None
    return loaded


def test_create_schema_and_get_missing_task(tmp_path):
    repository = create_repository(tmp_path)

    assert repository.get_task("missing-task") is None


def test_save_and_load_task_aggregate_round_trip(tmp_path):
    repository = create_repository(tmp_path)
    task = create_task()

    loaded = round_trip(repository, task)

    assert loaded == task


def test_ids_are_preserved(tmp_path):
    repository = create_repository(tmp_path)
    task = create_task(task_id="task-id-preserved")

    loaded = round_trip(repository, task)

    assert loaded.id == "task-id-preserved"
    assert loaded.steps[0].id == "step-weather"


def test_chinese_text_round_trips(tmp_path):
    repository = create_repository(tmp_path)
    task = create_task()

    loaded = round_trip(repository, task)

    assert loaded.user_input == "明天早上八点半在公司开会，帮我安排好明早出门"
    assert loaded.steps[0].description == "检查明早天气"
    assert loaded.steps[0].tool_call.arguments["location"] == "上海"


def test_arguments_result_and_error_round_trip(tmp_path):
    repository = create_repository(tmp_path)
    step = create_weather_step(
        status=ToolCallStatus.FAILED,
        tool_call_status=ToolCallStatus.FAILED,
        result=None,
        error="ValidationError: location is required",
    )
    task = create_task(status=TaskStatus.FAILED, steps=[step])

    loaded = round_trip(repository, task)

    assert loaded.status == TaskStatus.FAILED
    assert loaded.steps[0].tool_call.arguments == {"location": "上海", "date": "tomorrow"}
    assert loaded.steps[0].tool_call.result is None
    assert loaded.steps[0].tool_call.error == "ValidationError: location is required"


def test_success_result_round_trips(tmp_path):
    repository = create_repository(tmp_path)
    step = create_weather_step(
        status=ToolCallStatus.SUCCESS,
        tool_call_status=ToolCallStatus.SUCCESS,
        result={"forecast": "sunny", "location": "上海"},
    )
    task = create_task(status=TaskStatus.COMPLETED, steps=[step])

    loaded = round_trip(repository, task)

    assert loaded.steps[0].tool_call.result == {"forecast": "sunny", "location": "上海"}


@pytest.mark.parametrize(
    ("risk_level", "requires_confirmation", "confirmation_status", "status"),
    [
        (RiskLevel.LOW, False, ConfirmationStatus.NOT_REQUIRED, TaskStatus.PLANNED),
        (RiskLevel.MEDIUM, True, ConfirmationStatus.PENDING, TaskStatus.PLANNED),
        (RiskLevel.MEDIUM, True, ConfirmationStatus.CONFIRMED, TaskStatus.PLANNED),
        (RiskLevel.MEDIUM, True, ConfirmationStatus.REJECTED, TaskStatus.CANCELLED),
        (RiskLevel.HIGH, True, ConfirmationStatus.PENDING, TaskStatus.PLANNED),
        (RiskLevel.LOW, False, ConfirmationStatus.NOT_REQUIRED, TaskStatus.COMPLETED),
        (RiskLevel.LOW, False, ConfirmationStatus.NOT_REQUIRED, TaskStatus.FAILED),
    ],
)
def test_status_risk_confirmation_round_trips(
    tmp_path,
    risk_level,
    requires_confirmation,
    confirmation_status,
    status,
):
    repository = create_repository(tmp_path)
    task = create_task(
        risk_level=risk_level,
        requires_confirmation=requires_confirmation,
        confirmation_status=confirmation_status,
        status=status,
    )

    loaded = round_trip(repository, task)

    assert loaded.risk_level == risk_level
    assert loaded.requires_confirmation is requires_confirmation
    assert loaded.confirmation_status == confirmation_status
    assert loaded.status == status


def test_overwrite_updates_task_and_replaces_steps(tmp_path):
    repository = create_repository(tmp_path)
    task = create_task()
    repository.save_task(task)

    task.goal = "更新后的目标"
    task.steps = [create_navigation_step(order=1)]
    repository.save_task(task)
    loaded = repository.get_task(task.id)

    assert loaded.goal == "更新后的目标"
    assert [step.id for step in loaded.steps] == ["step-navigation"]


def test_list_tasks_returns_latest_first_and_honors_limit(tmp_path):
    repository = create_repository(tmp_path)
    repository.save_task(create_task(task_id="task-1"))
    repository.save_task(create_task(task_id="task-2"))
    repository.save_task(create_task(task_id="task-3"))

    listed = repository.list_tasks(limit=2)

    assert [task.id for task in listed] == ["task-3", "task-2"]


def test_corrupted_arguments_json_raises_serialization_error(tmp_path):
    repository = create_repository(tmp_path)
    task = create_task()
    repository.save_task(task)
    with sqlite3.connect(repository.db_path) as connection:
        connection.execute(
            "UPDATE tool_calls SET arguments_json = ? WHERE step_id = ?",
            ("{bad-json", "step-weather"),
        )

    with pytest.raises(PersistenceSerializationError):
        repository.get_task(task.id)


def test_unknown_enum_value_raises_serialization_error(tmp_path):
    repository = create_repository(tmp_path)
    task = create_task()
    repository.save_task(task)
    with sqlite3.connect(repository.db_path) as connection:
        connection.execute(
            "UPDATE tasks SET status = ? WHERE task_id = ?",
            ("UNKNOWN", task.id),
        )

    with pytest.raises(PersistenceSerializationError):
        repository.get_task(task.id)


def test_transaction_rolls_back_when_step_insert_fails(tmp_path):
    repository = create_repository(tmp_path)
    task = create_task()
    repository.save_task(task)

    broken = create_task(
        task_id=task.id,
        goal="should not partially save",
        steps=[
            create_weather_step(step_id="duplicate", order=1),
            create_navigation_step(step_id="duplicate", order=2),
        ],
    )
    with pytest.raises(Exception):
        repository.save_task(broken)

    loaded = repository.get_task(task.id)
    assert loaded.goal == "安排明早通勤"
    assert [step.id for step in loaded.steps] == ["step-weather", "step-navigation"]


def test_foreign_key_prevents_orphan_step(tmp_path):
    repository = create_repository(tmp_path)

    with sqlite3.connect(repository.db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO plan_steps (
                    task_id, step_id, step_order, description,
                    tool_name, status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "missing-task",
                    "orphan-step",
                    1,
                    "orphan",
                    "weather_tool",
                    "PENDING",
                    "2026-01-01T00:00:00Z",
                    "2026-01-01T00:00:00Z",
                ),
            )


def test_pending_restart_scenario_preserves_confirmation(tmp_path):
    repository = create_repository(tmp_path)
    task = create_task(
        risk_level=RiskLevel.MEDIUM,
        requires_confirmation=True,
        confirmation_status=ConfirmationStatus.PENDING,
    )
    TaskConfirmationService().request_confirmation(task)

    repository.save_task(task)
    reloaded = repository.get_task(task.id)

    assert reloaded.status == TaskStatus.WAITING_CONFIRMATION
    assert reloaded.confirmation_status == ConfirmationStatus.PENDING


def test_confirmed_restart_scenario_preserves_confirmation(tmp_path):
    repository = create_repository(tmp_path)
    task = create_task(
        risk_level=RiskLevel.MEDIUM,
        requires_confirmation=True,
        confirmation_status=ConfirmationStatus.PENDING,
    )
    service = TaskConfirmationService()
    service.request_confirmation(task)
    service.confirm(task)
    repository.save_task(task)

    reloaded = repository.get_task(task.id)

    assert reloaded.status == TaskStatus.PLANNED
    assert reloaded.confirmation_status == ConfirmationStatus.CONFIRMED


def test_confirmation_service_works_after_reload(tmp_path):
    repository = create_repository(tmp_path)
    task = create_task(
        risk_level=RiskLevel.MEDIUM,
        requires_confirmation=True,
        confirmation_status=ConfirmationStatus.PENDING,
    )
    TaskConfirmationService().request_confirmation(task)
    repository.save_task(task)

    reloaded = repository.get_task(task.id)
    TaskConfirmationService().confirm(reloaded)
    repository.save_task(reloaded)
    confirmed = repository.get_task(task.id)

    assert confirmed.confirmation_status == ConfirmationStatus.CONFIRMED


def test_completed_reload_cannot_execute_again(tmp_path):
    repository = create_repository(tmp_path)
    task = create_task(status=TaskStatus.COMPLETED)
    repository.save_task(task)

    reloaded = repository.get_task(task.id)
    with pytest.raises(TaskExecutionError):
        create_executor().execute(reloaded)


def test_dynamic_task_like_aggregate_persists(tmp_path):
    repository = create_repository(tmp_path)
    task = create_task(
        task_id="task-dynamic",
        steps=[
            PlanStep(
                id="step-calendar",
                order=1,
                description="读取日历事件",
                tool_name="calendar_tool",
                tool_call=ToolCall(
                    tool_name="calendar_tool",
                    arguments={"date": "tomorrow"},
                    status=ToolCallStatus.SUCCESS,
                    result={"events": [{"title": "面试", "location": "公司"}]},
                ),
                status=ToolCallStatus.SUCCESS,
            ),
            create_weather_step(status=ToolCallStatus.SUCCESS, tool_call_status=ToolCallStatus.SUCCESS),
            create_navigation_step(),
        ],
    )

    loaded = round_trip(repository, task)

    assert [step.tool_name for step in loaded.steps] == [
        "calendar_tool",
        "weather_tool",
        "navigation_tool",
    ]
    assert loaded.steps[0].tool_call.result["events"][0]["title"] == "面试"


def test_notification_pending_persistence_without_webhook(tmp_path):
    repository = create_repository(tmp_path)
    task = create_task(
        task_id="task-notification",
        risk_level=RiskLevel.MEDIUM,
        requires_confirmation=True,
        confirmation_status=ConfirmationStatus.PENDING,
        steps=[
            PlanStep(
                id="step-notification",
                order=1,
                description="发送通知",
                tool_name="notification_tool",
                tool_call=ToolCall(
                    tool_name="notification_tool",
                    arguments={
                        "title": "Stage25 Test",
                        "message": "Persistence only.",
                        "channel": "mobile",
                    },
                ),
            )
        ],
    )

    loaded = round_trip(repository, task)

    assert loaded.confirmation_status == ConfirmationStatus.PENDING
    assert loaded.steps[0].tool_call.arguments["title"] == "Stage25 Test"


def test_secret_values_are_not_introduced_by_persistence(tmp_path):
    repository = create_repository(tmp_path)
    task = create_task()
    repository.save_task(task)

    db_bytes = repository.db_path.read_bytes()

    assert b"LLM_API_KEY" not in db_bytes
    assert b"GOOGLE_CALENDAR_TOKEN" not in db_bytes
    assert b"AMAP_WEB_SERVICE_KEY" not in db_bytes
    assert b"FEISHU_BOT_WEBHOOK_URL" not in db_bytes
