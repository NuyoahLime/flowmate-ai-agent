from enum import Enum
from hashlib import sha256

from pydantic import BaseModel, ConfigDict, Field, field_validator

from flowmate.tools.base import BaseTool


class NotificationChannel(str, Enum):
    MOBILE = "mobile"


class NotificationToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    message: str = Field(min_length=1)
    channel: NotificationChannel

    @field_validator("title", "message")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Notification text fields must not be blank.")
        return trimmed


class NotificationToolResult(BaseModel):
    notification_id: str
    channel: NotificationChannel
    status: str
    title: str
    message: str


class NotificationTool(BaseTool[NotificationToolInput, NotificationToolResult]):
    name = "notification_tool"
    description = (
        "Mock notification delivery inside the FlowMate test environment. "
        "Default runtime uses a mock provider; real delivery can be injected."
    )
    input_schema = NotificationToolInput

    def __init__(self, provider: "NotificationProvider | None" = None) -> None:
        if provider is None:
            from flowmate.integrations.notification.mock_provider import (
                MockNotificationProvider,
            )

            provider = MockNotificationProvider()
        self.provider = provider

    def execute(self, input_data: NotificationToolInput) -> NotificationToolResult:
        from flowmate.integrations.notification.provider import (
            NotificationProviderQuery,
        )

        provider = getattr(self, "provider", None)
        if provider is None:
            from flowmate.integrations.notification.mock_provider import (
                MockNotificationProvider,
            )

            provider = MockNotificationProvider()
            self.provider = provider

        return provider.send(
            NotificationProviderQuery(
                title=input_data.title,
                message=input_data.message,
                channel=input_data.channel.value,
            )
        )


from flowmate.integrations.notification.provider import NotificationProvider
