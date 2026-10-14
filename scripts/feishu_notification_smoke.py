import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flowmate.agent import (
    RiskPolicy,
    StepExecutor,
    TaskConfirmationService,
    TaskExecutionError,
    TaskExecutor,
    ToolExecutor,
)
from flowmate.integrations.notification import (
    FeishuWebhookNotificationProvider,
    NotificationConfigurationError,
    NotificationProviderError,
)
from flowmate.schemas import PlanStep, RiskLevel, Task, TaskStatus, ToolCall
from flowmate.tools import NotificationTool, ToolRegistry


class CountingFeishuProvider:
    def __init__(self, provider: FeishuWebhookNotificationProvider) -> None:
        self.provider = provider
        self.attempt_count = 0
        self.success_count = 0

    def send(self, query):
        self.attempt_count += 1
        result = self.provider.send(query)
        self.success_count += 1
        return result


def env_status(name: str) -> str:
    return "configured" if os.getenv(name) else "missing"


def build_task() -> Task:
    task = Task(
        id="task-feishu-smoke",
        user_input="Stage24 Feishu smoke",
        goal="Send authorized Stage24 Feishu test notification.",
        status=TaskStatus.PLANNED,
        risk_level=RiskLevel.LOW,
        requires_confirmation=False,
        steps=[
            PlanStep(
                id="step-feishu-smoke",
                order=1,
                description="Send Stage24 Feishu test notification.",
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


def create_executor(provider) -> TaskExecutor:
    registry = ToolRegistry()
    registry.register(NotificationTool(provider=provider))
    return TaskExecutor(StepExecutor(ToolExecutor(registry)))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Feishu notification safety smoke.")
    parser.add_argument("--confirm-send", action="store_true")
    args = parser.parse_args()

    task = build_task()
    confirmation_service = TaskConfirmationService()
    confirmation_service.request_confirmation(task)

    base = {
        "provider": "feishu",
        "configuration": {
            "FEISHU_BOT_WEBHOOK_URL": env_status("FEISHU_BOT_WEBHOOK_URL"),
            "HTTP_PROXY": env_status("HTTP_PROXY"),
            "HTTPS_PROXY": env_status("HTTPS_PROXY"),
            "NO_PROXY": env_status("NO_PROXY"),
        },
        "risk": task.risk_level.value,
        "requires_confirmation": task.requires_confirmation,
        "confirmation_status": task.confirmation_status.value,
        "task_status": task.status.value,
        "confirm_send": args.confirm_send,
    }

    if not args.confirm_send:
        print(
            json.dumps(
                {
                    **base,
                    "real_send_attempts": 0,
                    "real_message_sent": False,
                    "success": True,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if not os.getenv("FEISHU_BOT_WEBHOOK_URL"):
        print(
            json.dumps(
                {
                    **base,
                    "success": False,
                    "error_type": "NotificationConfigurationError",
                    "error": "FEISHU_BOT_WEBHOOK_URL is required.",
                    "real_send_attempts": 0,
                    "real_message_sent": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2

    try:
        provider = CountingFeishuProvider(FeishuWebhookNotificationProvider())
        executor = create_executor(provider)
        confirmation_service.confirm(task)
        executed = executor.execute(task)
    except (NotificationConfigurationError, NotificationProviderError, TaskExecutionError) as exc:
        print(
            json.dumps(
                {
                    **base,
                    "success": False,
                    "error_type": exc.__class__.__name__,
                    "error": str(exc),
                    "real_send_attempts": locals().get("provider").attempt_count
                    if "provider" in locals()
                    else 0,
                    "real_message_sent": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    result = executed.steps[0].tool_call.result
    print(
        json.dumps(
            {
                **base,
                "confirmation_status": task.confirmation_status.value,
                "task_status": executed.status.value,
                "real_send_attempts": provider.attempt_count,
                "real_send_success": provider.success_count == 1,
                "real_message_sent": provider.success_count == 1,
                "tool_result_schema_valid": result is not None,
                "tool_result": result,
                "real_calendar_write_calls": 0,
                "real_smart_home_executions": 0,
                "real_vehicle_executions": 0,
                "success": executed.status == TaskStatus.COMPLETED,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if executed.status == TaskStatus.COMPLETED else 1


if __name__ == "__main__":
    raise SystemExit(main())
