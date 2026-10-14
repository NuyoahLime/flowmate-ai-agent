from __future__ import annotations

import json
import os
import socket
from hashlib import sha256
from typing import Any, Mapping

from flowmate.integrations.notification.formatter import FeishuNotificationFormatter
from flowmate.integrations.notification.provider import (
    NotificationConfigurationError,
    NotificationDeliveryError,
    NotificationMappingError,
    NotificationProviderQuery,
    NotificationHttpClient,
    NotificationResponseError,
    NotificationTransportError,
    UrllibNotificationHttpClient,
)
from flowmate.tools.notification import NotificationChannel, NotificationToolResult


class FeishuWebhookNotificationProvider:
    def __init__(
        self,
        *,
        webhook_url: str | None = None,
        timeout_seconds: float | None = None,
        formatter: FeishuNotificationFormatter | None = None,
        http_client: NotificationHttpClient | None = None,
    ) -> None:
        resolved_url = webhook_url if webhook_url is not None else os.getenv("FEISHU_BOT_WEBHOOK_URL")
        if resolved_url is None or not resolved_url.strip():
            raise NotificationConfigurationError("FEISHU_BOT_WEBHOOK_URL is required.")
        self.webhook_url = resolved_url
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else self._default_timeout()
        self.formatter = formatter or FeishuNotificationFormatter()
        self.http_client = http_client or UrllibNotificationHttpClient()

    def send(self, query: NotificationProviderQuery) -> NotificationToolResult:
        payload = {
            "msg_type": "text",
            "content": {"text": self.formatter.format(query.title, query.message)},
        }
        response = self.http_client.post_json(
            self.webhook_url,
            payload=payload,
            timeout_seconds=self.timeout_seconds,
        )
        self._ensure_success(response)
        return NotificationToolResult(
            notification_id=self._notification_id(query),
            channel=NotificationChannel.MOBILE,
            status="feishu_delivered",
            title=query.title,
            message=query.message,
        )

    def _ensure_success(self, response: Mapping[str, Any]) -> None:
        code = response.get("code")
        if code != 0:
            msg = response.get("msg")
            detail = "Feishu webhook delivery failed."
            if isinstance(msg, str) and msg:
                detail = f"{detail} msg={msg}"
            raise NotificationDeliveryError(detail)

    def _notification_id(self, query: NotificationProviderQuery) -> str:
        payload = f"{query.channel}|{query.title}|{query.message}"
        digest = sha256(payload.encode("utf-8")).hexdigest()[:12]
        return f"feishu-notification-{digest}"

    def _default_timeout(self) -> float:
        value = os.getenv("FEISHU_TIMEOUT_SECONDS")
        if value is None or value.strip() == "":
            return 10.0
        try:
            timeout = float(value)
        except ValueError as exc:
            raise NotificationConfigurationError(
                "FEISHU_TIMEOUT_SECONDS must be numeric."
            ) from exc
        if timeout <= 0:
            raise NotificationConfigurationError(
                "FEISHU_TIMEOUT_SECONDS must be greater than 0."
            )
        return timeout
