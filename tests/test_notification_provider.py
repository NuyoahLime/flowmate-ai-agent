import pytest

from flowmate.integrations.notification import (
    FeishuNotificationFormatter,
    FeishuWebhookNotificationProvider,
    MockNotificationProvider,
    NotificationConfigurationError,
    NotificationDeliveryError,
    NotificationProviderQuery,
    NotificationResponseError,
    NotificationTransportError,
)
from flowmate.tools import NotificationTool
from flowmate.tools.notification import (
    NotificationChannel,
    NotificationToolInput,
    NotificationToolResult,
)


class FakeNotificationHttpClient:
    def __init__(self, response=None, exc: Exception | None = None) -> None:
        self.response = response
        self.exc = exc
        self.calls = []

    def post_json(self, url, *, payload, timeout_seconds):
        self.calls.append((url, payload, timeout_seconds))
        if self.exc is not None:
            raise self.exc
        return self.response


def query(
    title: str = "Stage24 Test",
    message: str = "Real notification delivery test completed successfully.",
) -> NotificationProviderQuery:
    return NotificationProviderQuery(
        title=title,
        message=message,
        channel="mobile",
    )


def create_feishu_provider(
    client: FakeNotificationHttpClient,
    *,
    webhook_url: str = "https://open.feishu.cn/open-apis/bot/v2/hook/TEST_SECRET_WEBHOOK_ID",
) -> FeishuWebhookNotificationProvider:
    return FeishuWebhookNotificationProvider(
        webhook_url=webhook_url,
        timeout_seconds=1,
        http_client=client,
    )


def test_mock_notification_provider_preserves_existing_behavior():
    provider = MockNotificationProvider()

    result = provider.send(
        NotificationProviderQuery(
            title="Morning commute",
            message="Your route is ready.",
            channel="mobile",
        )
    )

    assert result.status == "mock_delivered"
    assert result.notification_id.startswith("mock-notification-")
    assert result.title == "Morning commute"
    assert result.message == "Your route is ready."


def test_notification_tool_defaults_to_mock_provider():
    tool = NotificationTool()

    result = tool.run(
        {
            "title": "Morning commute",
            "message": "Your route is ready.",
            "channel": "mobile",
        }
    )

    assert result.status == "mock_delivered"
    assert result.notification_id.startswith("mock-notification-")


def test_same_input_returns_same_mock_result():
    tool = NotificationTool()
    arguments = {
        "title": "Morning commute",
        "message": "Your route is ready.",
        "channel": "mobile",
    }

    assert tool.run(arguments) == tool.run(arguments)


def test_feishu_formatter_is_deterministic_and_contains_flowmate_keyword():
    formatter = FeishuNotificationFormatter()

    text = formatter.format(
        "Stage24 Test",
        "Real notification delivery test completed successfully.",
    )

    assert text == (
        "[FlowMate] Stage24 Test\n\n"
        "Real notification delivery test completed successfully."
    )


def test_feishu_provider_requires_webhook_url(monkeypatch):
    monkeypatch.delenv("FEISHU_BOT_WEBHOOK_URL", raising=False)

    with pytest.raises(NotificationConfigurationError):
        FeishuWebhookNotificationProvider()


def test_feishu_provider_rejects_invalid_timeout(monkeypatch):
    monkeypatch.setenv("FEISHU_BOT_WEBHOOK_URL", "https://example.invalid/hook/secret")
    monkeypatch.setenv("FEISHU_TIMEOUT_SECONDS", "0")

    with pytest.raises(NotificationConfigurationError):
        FeishuWebhookNotificationProvider()


def test_feishu_provider_posts_text_payload():
    client = FakeNotificationHttpClient(response={"code": 0, "msg": "ok"})
    provider = create_feishu_provider(client)

    result = provider.send(query())

    assert result.status == "feishu_delivered"
    assert result.notification_id.startswith("feishu-notification-")
    assert len(client.calls) == 1
    _, payload, timeout_seconds = client.calls[0]
    assert payload == {
        "msg_type": "text",
        "content": {
            "text": (
                "[FlowMate] Stage24 Test\n\n"
                "Real notification delivery test completed successfully."
            )
        },
    }
    assert timeout_seconds == 1


def test_feishu_provider_supports_chinese_unicode_payload():
    client = FakeNotificationHttpClient(response={"code": 0, "msg": "ok"})
    provider = create_feishu_provider(client)

    provider.send(query(title="阶段24测试", message="真实通知发送验证完成。"))

    assert "[FlowMate] 阶段24测试" in client.calls[0][1]["content"]["text"]
    assert "真实通知发送验证完成。" in client.calls[0][1]["content"]["text"]


def test_feishu_provider_business_failure_does_not_leak_webhook_secret():
    client = FakeNotificationHttpClient(response={"code": 19020, "msg": "invalid token"})
    provider = create_feishu_provider(client)

    with pytest.raises(NotificationDeliveryError) as exc_info:
        provider.send(query())

    assert "invalid token" in str(exc_info.value)
    assert "TEST_SECRET_WEBHOOK_ID" not in str(exc_info.value)


def test_feishu_provider_transport_error_does_not_leak_webhook_secret():
    client = FakeNotificationHttpClient(exc=NotificationTransportError("timeout"))
    provider = create_feishu_provider(client)

    with pytest.raises(NotificationTransportError) as exc_info:
        provider.send(query())

    assert "TEST_SECRET_WEBHOOK_ID" not in str(exc_info.value)


def test_feishu_provider_response_error_is_wrapped():
    client = FakeNotificationHttpClient(response={"msg": "missing code"})
    provider = create_feishu_provider(client)

    with pytest.raises(NotificationDeliveryError):
        provider.send(query())


def test_feishu_provider_raw_response_not_exposed_to_domain_result():
    client = FakeNotificationHttpClient(
        response={"code": 0, "msg": "ok", "extra": {"provider_id": "hidden"}}
    )
    provider = create_feishu_provider(client)

    result = provider.send(query())

    assert "extra" not in result.model_dump()
    assert result.status == "feishu_delivered"


def test_notification_tool_schema_remains_unchanged():
    tool_input = NotificationToolInput(
        title="Stage24 Test",
        message="Real notification delivery test completed successfully.",
        channel="mobile",
    )

    assert tool_input.channel == NotificationChannel.MOBILE
    assert NotificationToolResult.model_validate(
        {
            "notification_id": "mock-notification-123456789abc",
            "channel": "mobile",
            "status": "mock_delivered",
            "title": "Stage24 Test",
            "message": "Real notification delivery test completed successfully.",
        }
    )
