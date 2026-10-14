# Stage 24: Feishu Real Notification Delivery Adapter V1

## 1. Goal

Stage 24 adds a real outbound notification provider using a Feishu custom bot
webhook while preserving the existing `notification_tool` schema and safety
gates.

## 2. China Portfolio Positioning

Feishu is used as the first real notification channel because FlowMate is aimed
at a China-facing portfolio context.

## 3. Stage23 Baseline

Stage23/23.1 closed Calendar, Weather, and Navigation real read integrations.

## 4. Existing Notification Contract

Input:

```json
{"title": "string", "message": "string", "channel": "mobile"}
```

Result:

```json
{
  "notification_id": "string",
  "channel": "mobile",
  "status": "string",
  "title": "string",
  "message": "string"
}
```

The contract was preserved.

## 5. Provider Architecture

```text
NotificationTool
├─ MockNotificationProvider
└─ FeishuWebhookNotificationProvider
```

## 6. NotificationProvider

`NotificationProvider.send(NotificationProviderQuery) -> NotificationToolResult`
is the provider boundary.

## 7. Mock Preservation

`NotificationTool()` defaults to `MockNotificationProvider` and keeps the
deterministic `mock-notification-*` ID plus `mock_delivered` status.

## 8. FeishuWebhookNotificationProvider

The real provider sends one text webhook POST per authorized `NotificationTool`
execution.

## 9. Webhook Credential Boundary

`FEISHU_BOT_WEBHOOK_URL` is treated as a secret. It is not part of Planner,
ToolCall, or Tool result schemas.

## 10. Deterministic Text Formatting

The Feishu text formatter emits:

```text
[FlowMate] {title}

{message}
```

## 11. FlowMate Keyword

The fixed `FlowMate` keyword supports Feishu custom bot keyword security.

## 12. HTTP Transport

The adapter uses Python standard-library `urllib` via a small HTTP client
boundary.

## 13. Timeout

`FEISHU_TIMEOUT_SECONDS` defaults to 10 seconds.

## 14. Proxy

Standard `HTTP_PROXY`, `HTTPS_PROXY`, and `NO_PROXY` environment variables are
honored by the underlying runtime. No proxy is hardcoded.

## 15. Error Taxonomy

Notification errors distinguish configuration, transport, response, delivery,
and mapping failures.

## 16. Secret Redaction

Provider exceptions do not include the webhook URL or token.

## 17. RiskPolicy

`notification_tool` remains MEDIUM risk and requires confirmation.

## 18. HITL

Real delivery is only reachable after backend confirmation.

## 19. Pending Containment

PENDING notification tasks cannot execute and produce zero provider attempts.

## 20. Rejection Containment

REJECTED notification tasks remain cancelled and produce zero provider attempts.

## 21. Confirmed Delivery

CONFIRMED notification tasks execute exactly one provider attempt in one
authorized lifecycle.

## 22. Duplicate Execution Containment

COMPLETED tasks cannot be executed again by the current `TaskExecutor`.

## 23. Side-effect Retry Decision

No provider retry is implemented. Timeout outcomes may be ambiguous after a
write.

## 24. Delivery Ambiguity

This stage does not claim distributed exactly-once delivery. It guarantees one
application-level provider invocation per authorized task lifecycle.

## 25. Dynamic Compatibility

Dynamic notification proposal and confirmation remain unchanged; only the
provider behind `NotificationTool` changes.

## 26. Offline Tests

Pytest uses fake providers and fake HTTP clients. It performs zero real Feishu
calls.

## 27. Real Smoke

Default smoke is safety-only and sends no message:

```powershell
python scripts\feishu_notification_smoke.py
```

Real delivery requires explicit confirmation:

```powershell
python scripts\feishu_notification_smoke.py --confirm-send
```

## 28. Engineering Gate

Provider abstraction, mock preservation, Feishu provider, safety matrix, and
offline tests must pass.

## 29. Real Safety Gate

Pre-confirm smoke must show MEDIUM risk, confirmation pending, and zero sends.

## 30. Real Delivery Gate

Confirmed smoke must produce one provider attempt and a completed task.

## 31. Current Limitations

No scheduling, retry, ledger, reconciliation, multi-recipient routing, cards,
files, images, FCM, APNs, Enterprise WeChat, frontend, or proactive triggers are
implemented.

## 32. Stage25 Persistence Readiness

Persistence is the natural next step for durable side-effect ledgers, but is not
implemented here.

## 33. Interview Takeaway

Stage24 shows that FlowMate can add a real outbound side-effect provider without
weakening Planner boundaries, RiskPolicy, HITL, or Executor safety.
