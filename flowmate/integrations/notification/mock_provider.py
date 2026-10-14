from hashlib import sha256

from flowmate.integrations.notification.provider import NotificationProviderQuery
from flowmate.tools.notification import NotificationChannel, NotificationToolResult


class MockNotificationProvider:
    def send(self, query: NotificationProviderQuery) -> NotificationToolResult:
        payload = f"{query.channel}|{query.title}|{query.message}"
        digest = sha256(payload.encode("utf-8")).hexdigest()[:12]
        return NotificationToolResult(
            notification_id=f"mock-notification-{digest}",
            channel=NotificationChannel.MOBILE,
            status="mock_delivered",
            title=query.title,
            message=query.message,
        )
