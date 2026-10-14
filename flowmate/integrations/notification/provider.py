from __future__ import annotations

from typing import Any, Mapping, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from flowmate.tools.notification import NotificationToolResult


class NotificationProviderError(Exception):
    pass


class NotificationConfigurationError(NotificationProviderError):
    pass


class NotificationTransportError(NotificationProviderError):
    pass


class NotificationResponseError(NotificationProviderError):
    pass


class NotificationDeliveryError(NotificationProviderError):
    pass


class NotificationMappingError(NotificationProviderError):
    pass


class NotificationProviderQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    message: str = Field(min_length=1)
    channel: str = Field(min_length=1)

    @field_validator("channel")
    @classmethod
    def validate_channel(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized != "mobile":
            raise ValueError("Only the mobile channel is supported.")
        return normalized


class NotificationHttpClient(Protocol):
    def post_json(
        self,
        url: str,
        *,
        payload: Mapping[str, Any],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        ...


class NotificationProvider(Protocol):
    def send(self, query: NotificationProviderQuery) -> NotificationToolResult:
        ...


class UrllibNotificationHttpClient:
    def post_json(
        self,
        url: str,
        *,
        payload: Mapping[str, Any],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        import json
        import socket
        from urllib.error import HTTPError, URLError
        from urllib.request import Request, urlopen

        request = Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            raise NotificationTransportError(
                f"Feishu webhook request failed with status {exc.code}."
            ) from exc
        except (OSError, TimeoutError, URLError, socket.timeout) as exc:
            raise NotificationTransportError("Feishu webhook request failed.") from exc

        try:
            decoded = json.loads(body)
        except json.JSONDecodeError as exc:
            raise NotificationResponseError("Feishu webhook returned invalid JSON.") from exc
        if not isinstance(decoded, Mapping):
            raise NotificationResponseError("Feishu webhook response must be a mapping.")
        return decoded
