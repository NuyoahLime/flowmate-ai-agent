from flowmate.integrations.notification.provider import NotificationProviderQuery


class FeishuNotificationFormatter:
    def format(self, title: str, message: str) -> str:
        return f"[FlowMate] {title}\n\n{message}"

    def build_payload(self, title: str, message: str, channel: str) -> NotificationProviderQuery:
        return NotificationProviderQuery(title=title, message=message, channel=channel)
