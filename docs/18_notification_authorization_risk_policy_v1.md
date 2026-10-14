# Notification Planner Authorization & Deterministic Risk Policy V1

## 1. Goal
Stage 17.1 authorizes `LLMPlanner` to propose `notification_tool`, while deterministic code assigns risk and requires confirmation before execution.

## 2. Stage17 Baseline
Stage 17 installed:
- mock `notification_tool`
- deterministic mobile channel
- registry integration
- validator integration
- executor integration

Planner access was still disabled.

## 3. Installed vs Planner-authorized vs Execution-authorized
Installed:
- `weather_tool`
- `navigation_tool`
- `calendar_tool`
- `notification_tool`

Planner-authorized:
- `weather_tool`
- `navigation_tool`
- `calendar_tool`
- `notification_tool`

Execution-authorized:
- still controlled by deterministic risk policy and Human-in-the-loop confirmation.

## 4. Notification Capability Boundary
Supported:
- immediate mock mobile notifications

Unsupported:
- scheduled notification
- delayed notification
- conditional notification
- email
- SMS
- WeChat
- real push guarantee

## 5. Deterministic Risk Policy
`RiskPolicy` is the source of truth for execution risk.

The model proposes actions. Deterministic policy assigns execution risk. Human confirmation authorizes side effects. Executors enforce the authorization state.

## 6. RiskAssessment
`RiskAssessment` contains:
- `risk_level`
- `requires_confirmation`
- `reason`

`reason` is for audit/debug only.

## 7. Highest-risk Rule
Tool risk:
- `weather_tool`: LOW, confirmation=false
- `navigation_tool`: LOW, confirmation=false
- `calendar_tool`: LOW, confirmation=false
- `notification_tool`: MEDIUM, confirmation=true

Multi-tool Task risk uses the highest-risk planned tool.

## 8. Untrusted LLM Risk Metadata
LLM-provided `risk_level` and `requires_confirmation` are not trusted.

The final Task uses `RiskPolicy`, even if the model claims:
- notification is LOW
- notification requires no confirmation
- weather is HIGH
- weather requires confirmation

## 9. Planner Authorization
`LLMPlanner.allowed_tools` now includes `notification_tool`.

The prompt adds only narrow notification rules:
- immediate mock mobile notification is supported
- scheduled/delayed/conditional notifications are unsupported
- do not add notification unless explicitly requested

## 10. Human-in-the-loop Lifecycle
Notification Tasks are:
- `risk_level=MEDIUM`
- `requires_confirmation=true`
- `confirmation_status=PENDING`

They use the existing `TaskConfirmationService`.

## 11. Pending / Confirm / Reject
Pending:
- unconfirmed notification Task is blocked by `TaskExecutor`

Confirm:
- `WAITING_CONFIRMATION -> PLANNED`
- `TaskExecutor` can execute the mock notification exactly once

Reject:
- `WAITING_CONFIRMATION -> CANCELLED`
- no notification execution occurs

## 12. Side-effect Enforcement
The safety boundary is not the Planner whitelist.

The execution chain remains:

`Planner -> RiskPolicy -> Human confirmation -> TaskExecutor -> ToolExecutor -> NotificationTool`

## 13. Notification Planner Dataset
`evals/planner_notification_v1.json` contains 16 cases:
- immediate_notification_supported: 6
- scheduled_notification_unsupported: 4
- conditional_notification_unsupported: 3
- non_notification_minimality: 3

## 14. Planner Eval Results
Real provider evaluation was not run because local provider configuration is missing:
- `LLM_API_KEY=missing`
- `LLM_MODEL=missing`
- `LLM_BASE_URL=missing`

Planner eval executes no Tools.

## 15. Risk Policy Accuracy
Offline pytest validates:
- notification -> MEDIUM / confirmation=true
- read-only tools -> LOW / confirmation=false
- unknown tools fail closed
- LLM metadata cannot downgrade or upgrade final Task risk

Risk Policy Accuracy in covered tests: 1.000

## 16. Confirmation Enforcement Rate
Offline HITL integration validates unconfirmed notification execution is blocked.

Confirmation Enforcement Rate in covered tests: 1.000

## 17. Rejection Containment Rate
Offline HITL integration validates rejected notification Tasks execute zero side-effect tools.

Rejection Containment Rate in covered tests: 1.000

## 18. Static Regression
`python -m pytest` passes.

`planner_eval_v2.json` was not modified.

## 19. Provider Retry Observations
No real provider eval was run, so no provider retry occurred.

## 20. Remaining Limitations
- no scheduled notifications
- no conditional notifications
- no real push API
- no dynamic notification flow
- no notification channel beyond mobile

## 21. Stage17.2 Boundary
Stage 17.2 may connect dynamic results to notifications.

Stage 17.1 does not modify `DynamicTaskOrchestrator` or dynamic evals.

## 22. Conclusion
Stage 17.1 completes the first side-effect safety chain:

`LLM proposal -> deterministic risk -> human confirmation -> gated execution`

Notification is now planner-authorized but not unconditionally executable.
