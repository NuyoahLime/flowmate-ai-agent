# Dynamic Result to Authorized Notification V1

## 1. Goal
Stage 17.2 connects completed dynamic informational results to an authorized notification side-effect phase.

The notification is proposed after information gathering completes. It is not executed with low-risk continuation tools.

## 2. Stage17.1 Baseline
Stage 17.1 established:
- `notification_tool` is Planner-authorized
- `RiskPolicy(notification_tool)=MEDIUM`
- `requires_confirmation=true`
- unconfirmed execution is blocked
- confirmed execution happens once
- rejected execution happens zero times

## 3. Why Side-effect Must Be Separated
Calendar, weather, and navigation are informational.

Notification is side-effecting. Therefore:
- informational continuation may execute first
- notification must enter a separate authorization lifecycle

## 4. Dynamic Informational Phase
The existing dynamic flow remains:
- calendar observation
- weather/navigation continuation
- continuation execution
- structured `DynamicTaskResult`

This phase completes before notification confirmation.

## 5. Side-effect Proposal Phase
If the user explicitly asks to be notified when the result is ready, the dynamic workflow creates:
- `DynamicSideEffectProposal`
- `notification_task`

If the user does not request notification, no proposal is created.

## 6. NotificationFormatter
`NotificationFormatter` deterministically creates:
- title
- message
- channel=mobile

It uses only structured dynamic result data.

## 7. RiskPolicy Integration
The notification Task is passed through `RiskPolicy.apply_to_task`.

Final notification risk:
- `risk_level=MEDIUM`
- `requires_confirmation=true`
- `confirmation_status=PENDING`

## 8. HITL Integration
The workflow reuses:
- `TaskConfirmationService`
- `TaskExecutor`

No second confirmation system was created.

## 9. Confirm Lifecycle
Confirm path:
1. informational tools complete
2. notification Task waits for confirmation
3. user confirms
4. `TaskExecutor` executes `NotificationTool`
5. final status is `COMPLETED`

Calendar, weather, and navigation are not re-executed.

## 10. Reject Lifecycle
Reject path:
1. informational tools complete
2. notification Task waits for confirmation
3. user rejects
4. notification execution count remains zero
5. dynamic workflow status is `CANCELLED`

Informational results are preserved.

## 11. Informational Result Preservation
Waiting, confirm, reject, and notification failure do not discard:
- calendar result
- weather result
- navigation result

## 12. No Re-execution Guarantee
Confirm/reject affects only the side-effect Task.

It does not re-run:
- CalendarTool
- WeatherTool
- NavigationTool

## 13. Notification Grounding
Notification content must be grounded in `DynamicTaskResult`.

Current deterministic formatter includes:
- selected event title
- selected event time
- selected event location
- weather result when available
- navigation result when available

It does not invent arrival-by scheduling or exact departure time.

## 14. DynamicNotificationEvaluator
`DynamicNotificationEvaluator` evaluates:
- proposal accuracy
- pre-confirmation blocking
- confirmed execution
- rejected containment
- informational re-execution
- notification grounding
- side-effect minimality

## 15. Metrics
`evals/dynamic_notification_v1.json` contains 12 cases:
- dynamic_notification_confirm_success: 4
- dynamic_notification_reject: 2
- dynamic_without_notification: 2
- scheduled_notification_unsupported: 2
- conditional_notification_unsupported: 2

Latest results:
- Side-effect Proposal Accuracy: 1.000
- Pre-confirmation Blocking Rate: 1.000
- Confirmed Side-effect Success Rate: 1.000
- Rejected Side-effect Containment Rate: 1.000
- Informational Re-execution Rate: 0.000
- Notification Grounding Accuracy: 1.000
- Side-effect Minimality Accuracy: 1.000

## 16. Integration Tests
Covered paths:
- confirm
- reject
- weather + navigation + notification
- dynamic without notification
- scheduled unsupported
- conditional unsupported
- notification failure
- no informational re-execution

## 17. Failure Handling
New side-effect failures:
- `side_effect_proposal_error`
- `side_effect_risk_policy_error`
- `side_effect_execution_error`
- `notification_grounding_error`
- `unsupported_scheduled_notification`
- `unsupported_conditional_notification`

## 18. Retry vs Re-plan vs Confirmation
Retry handles provider failure.
Re-plan handles new information.
Confirmation authorizes side effects.

Stage 17.2 does not add Tool retry or provider retry.

## 19. Current Limitations
- no scheduler
- no conditional trigger
- no real push
- no notification copywriting LLM call
- no exact departure time calculation

## 20. Conclusion
Stage 17.2 completes the first dynamic side-effect lifecycle:

`informational dynamic result -> notification proposal -> RiskPolicy -> HITL -> authorized mock notification`

LangGraph is still not implemented. The workflow is more complex than Stage 16.4, but remains bounded enough for explicit Python. The pressure for a graph runtime is increasing, especially around pause/resume and future multi-side-effect support, but it is not yet mandatory.
