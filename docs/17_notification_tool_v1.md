# NotificationTool V1

## 1. Goal
Stage 17 installs `notification_tool` as a mock, deterministic, single-channel Tool.

This stage does not authorize Planner use of notifications.

## 2. Why Notification Is Different
Existing tools are read/information oriented:
- `weather_tool`
- `navigation_tool`
- `calendar_tool`

`notification_tool` is side-effecting. Even as a mock, it represents an action that would eventually affect the user experience outside planning.

## 3. Side-effect Semantics
Stage 17 only establishes:

`Tool installed`

It does not establish:
- Planner authorization
- execution approval policy
- human confirmation rules
- real push delivery

## 4. Tool Input Schema
`NotificationToolInput`:
- `title: str`
- `message: str`
- `channel: NotificationChannel`

All fields are required. No default channel is provided.

## 5. Tool Result Schema
`NotificationToolResult`:
- `notification_id`
- `channel`
- `status`
- `title`
- `message`

`status` is currently fixed to `mock_delivered`.

## 6. Mock Delivery Semantics
`mock_delivered` means the mock tool accepted and produced a deterministic result inside the FlowMate test environment.

It does not mean a real mobile device received a push notification.

## 7. Registry Integration
Default installed tools are now:
- `weather_tool`
- `navigation_tool`
- `calendar_tool`
- `notification_tool`

## 8. Argument Validation
Validation is handled through the existing `ToolArgumentValidator` and `tool.input_schema`.

No `notification_tool` special-case validator was added.

## 9. Executor Integration
`ToolExecutor` can execute:

`ToolCall(tool_name="notification_tool", arguments=...)`

No Notification-specific executor or dispatch path was added.

## 10. Installed vs Authorized Capability
Installed capabilities:
- weather
- navigation
- calendar
- notification

Planner authorized capabilities:
- weather
- navigation
- calendar

`notification_tool` is intentionally not in `LLMPlanner.allowed_tools`.

## 11. Risk / Confirmation Boundary
Notification is a side-effecting capability. A future authorization stage should decide:
- `RiskLevel`
- `requires_confirmation`
- confirmation policy
- which notification classes are pre-authorized

Stage 17 does not modify Risk Policy or Human-in-the-loop flow.

## 12. Integration Test
The integration path is:

`ToolRegistry -> ToolExecutor -> NotificationTool`

This validates Tool infrastructure only. It is not a user-facing notification authorization path.

## 13. Current Limitations
- only `mobile` channel exists
- no scheduling
- no push provider
- no APNs, FCM, SMS, email, or WebSocket
- no Planner access
- no DynamicTaskOrchestrator integration

## 14. Future Planner Authorization
A later stage can decide whether the Planner may generate `notification_tool` ToolCalls.

That should be paired with risk and confirmation rules.

## 15. Conclusion
Stage 17 adds NotificationTool infrastructure without expanding Planner or dynamic execution authority.

This preserves the distinction between installed capability and authorized behavior.
