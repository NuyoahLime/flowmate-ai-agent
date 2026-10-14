import pytest

from flowmate.agent import (
    RiskPolicy,
    StepExecutor,
    TaskConfirmationService,
    TaskExecutionError,
    TaskExecutor,
    ToolExecutor,
)
from flowmate.integrations.notification import NotificationProviderQuery
from flowmate.schemas import (
    ConfirmationStatus,
    PlanStep,
    RiskLevel,
    Task,
    TaskStatus,
    ToolCall,
)
from flowmate.tools import NotificationTool, ToolRegistry
from flowmate.tools.notification import NotificationChannel, NotificationToolResult


class CountingNotificationProvider:
    def __init__(self) -> None:
        self.attempt_count = 0
        self.successful_send_count = 0
        self.last_payload: NotificationProviderQuery | None = None

    def send(self, query: NotificationProviderQuery) -> NotificationToolResult:
        self.attempt_count += 1
        self.successful_send_count += 1
        self.last_payload = query
        return NotificationToolResult(
            notification_id="counting-notification-1",
            channel=query.channel,
            status="counting_delivered",
            title=query.title,
            message=query.message,
        )


def create_notification_task() -> Task:
    task = Task(
        id="task-notification-safety",
        user_input="send me a notification now",
        goal="Send immediate notification.",
        status=TaskStatus.PLANNED,
        risk_level=RiskLevel.LOW,
        requires_confirmation=False,
        steps=[
            PlanStep(
                id="step-notification",
                order=1,
                description="Send notification.",
                tool_name="notification_tool",
                tool_call=ToolCall(
                    tool_name="notification_tool",
                    arguments={
                        "title": "Stage24 Test",
                        "message": "Real notification delivery test completed successfully.",
                        "channel": "mobile",
                    },
                ),
            )
        ],
    )
    return RiskPolicy().apply_to_task(task)


def create_executor(provider: CountingNotificationProvider) -> TaskExecutor:
    registry = ToolRegistry()
    registry.register(NotificationTool(provider=provider))
    return TaskExecutor(StepExecutor(ToolExecutor(registry)))


def test_pending_notification_task_has_zero_provider_attempts():
    provider = CountingNotificationProvider()
    task = create_notification_task()
    executor = create_executor(provider)

    assert task.risk_level == RiskLevel.MEDIUM
    assert task.requires_confirmation is True
    assert task.confirmation_status == ConfirmationStatus.PENDING
    with pytest.raises(TaskExecutionError):
        executor.execute(task)

    assert provider.attempt_count == 0


def test_rejected_notification_task_has_zero_provider_attempts():
    provider = CountingNotificationProvider()
    task = create_notification_task()
    service = TaskConfirmationService()
    executor = create_executor(provider)

    service.request_confirmation(task)
    service.reject(task)
    with pytest.raises(TaskExecutionError):
        executor.execute(task)

    assert task.status == TaskStatus.CANCELLED
    assert task.confirmation_status == ConfirmationStatus.REJECTED
    assert provider.attempt_count == 0


def test_confirmed_notification_task_has_one_provider_attempt():
    provider = CountingNotificationProvider()
    task = create_notification_task()
    service = TaskConfirmationService()
    executor = create_executor(provider)

    service.request_confirmation(task)
    service.confirm(task)
    executed = executor.execute(task)

    assert executed.status == TaskStatus.COMPLETED
    assert provider.attempt_count == 1
    assert provider.successful_send_count == 1
    assert provider.last_payload.title == "Stage24 Test"
    assert provider.last_payload.channel == NotificationChannel.MOBILE


def test_completed_notification_task_rerun_remains_one_provider_attempt():
    provider = CountingNotificationProvider()
    task = create_notification_task()
    service = TaskConfirmationService()
    executor = create_executor(provider)

    service.request_confirmation(task)
    service.confirm(task)
    executor.execute(task)
    with pytest.raises(TaskExecutionError):
        executor.execute(task)

    assert task.status == TaskStatus.COMPLETED
    assert provider.attempt_count == 1
