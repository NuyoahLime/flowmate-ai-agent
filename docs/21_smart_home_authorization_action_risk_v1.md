# SmartHome Planner Authorization & Action-Aware Risk Policy V1

## 1. Goal

Stage 18.1 authorizes `LLMPlanner` to propose explicit, immediate
`smart_home_tool` actions while deterministic action-aware risk and the existing
human-confirmation gate control execution.

## 2. Stage 18 Baseline

Stage 18 installed a deterministic Mock SmartHomeTool for lights and air
conditioners. The baseline was `361 passed`; SmartHome was installed but absent
from Planner, DynamicTaskOrchestrator, and RiskPolicy authorization.

## 3. Planner Authorization

The default Planner whitelist now contains five tools:

- `weather_tool`
- `navigation_tool`
- `calendar_tool`
- `notification_tool`
- `smart_home_tool`

Planner authorization permits proposal only. It is not execution authorization.

## 4. SmartHome Capability Boundary

Supported requests are explicit and immediate:

- light: `turn_on`, `turn_off`
- air conditioner: `turn_on`, `turn_off`, `set_temperature`
- temperature: 16 through 30 degrees Celsius

The prompt provides deterministic mock logical IDs for explicitly named rooms
and devices. It rejects unspecified rooms instead of selecting a default device.

Unsupported boundaries include unsupported devices, delayed or scheduled
actions, conditional triggers, scenes, real-state verification, and real-device
guarantees.

## 5. Why Tool-level Risk Is No Longer Enough

Physical-world tools can contain actions with different future risk. A single
tool-level entry cannot distinguish a light command from a future lock or
vehicle command. RiskPolicy therefore reads the validated ToolCall contract.

## 6. Action-Aware Risk Architecture

The static path is:

`LLM output -> ToolArgumentValidator -> Task/ToolCall -> RiskPolicy -> HITL -> TaskExecutor`

`assess(tool_names)` remains available for existing tools. New task assessment
uses `assess_tool_call`, `assess_tool_calls`, and `assess_task`.

## 7. Risk Matrix

| Device | Action | Risk | Confirmation |
| --- | --- | --- | --- |
| light | turn_on | MEDIUM | required |
| light | turn_off | MEDIUM | required |
| air_conditioner | turn_on | MEDIUM | required |
| air_conditioner | turn_off | MEDIUM | required |
| air_conditioner | set_temperature | MEDIUM | required |

All V1 actions are MEDIUM, but each contract tuple has an explicit policy entry.

## 8. Validated Arguments as Risk Input

LLMPlanner validates Tool arguments against the registered SmartHome schema
before Task construction and policy application. Schema validation owns device
types, actions, compatibility, value presence, and the 16-30 range. RiskPolicy
uses only the resulting `device_type + action` contract for risk lookup.

## 9. Fail-Closed Policy

Unknown tools raise `UnknownToolRiskError`. Unknown or missing SmartHome action
contracts raise `UnknownActionRiskError`. Neither path defaults to LOW.

## 10. Highest-Risk Rule

Task risk is the highest deterministic risk across ToolCalls. Weather or
calendar plus SmartHome remains MEDIUM. Notification plus SmartHome also remains
MEDIUM. ToolCall order does not change the result.

## 11. LLM Risk Metadata Is Untrusted

LLM-provided risk metadata is only parsed as Planner output. `apply_to_task`
overwrites it deterministically. A model-produced LOW/no-confirmation SmartHome
plan becomes MEDIUM/confirmation-required. A model-produced HIGH weather plan
remains LOW/no-confirmation.

## 12. HITL Lifecycle

SmartHome uses the existing `TaskConfirmationService` and `TaskExecutor`. No
SmartHome-specific confirmation service was added.

## 13. Pending / Confirm / Reject

- Pending: TaskExecutor blocks execution; SmartHome execution count is zero.
- Confirm: Task returns to PLANNED, completes, and executes SmartHome exactly once.
- Repeat after completion: TaskExecutor rejects re-execution; count remains one.
- Reject: Task becomes CANCELLED; SmartHome execution count remains zero.

Confirmed air-conditioner temperature control preserves value 24 and returns
`status=mock_executed`, `state.temperature=24`.

## 14. SmartHome Planner Dataset

`evals/planner_smart_home_v1.json` contains 20 cases:

- light_control_supported: 4
- air_conditioner_control_supported: 6
- unsupported_device: 3
- scheduled_automation_unsupported: 2
- conditional_automation_unsupported: 2
- non_smart_home_minimality: 3

## 15. Real Provider Eval

Provider: `deepseek-v4-flash` through the configured OpenAI-compatible adapter.
The 20-case run completed with 20 provider attempts and zero retries.

| Metric | Result |
| --- | ---: |
| Scenario Accuracy | 1.000 |
| Supported Recall | 1.000 |
| Unsupported Recall | 1.000 |
| Tool Selection Accuracy | 1.000 |
| Parameter Accuracy | 0.974 |
| Parameter Completeness | 1.000 |
| Schema Valid Rate | 1.000 |
| Extra Tool Rate | 0.000 |
| Action Risk Accuracy | 1.000 |
| SmartHome Supported Recall | 1.000 |
| Unsupported Device Recall | 1.000 |
| Scheduled Automation Unsupported Recall | 1.000 |
| Conditional Automation Unsupported Recall | 1.000 |
| SmartHome Minimality Accuracy | 1.000 |

The only SmartHome dataset failure is `smart-home-minimality-003`: the model
preserved the notification message semantics but omitted the final Chinese full
stop, producing an exact-match parameter value error. No Prompt or Gold change
was made.

## 16. Static Regression

The unchanged 22-case `planner_eval_v2.json` produced:

| Metric | Result |
| --- | ---: |
| Scenario Accuracy | 0.955 |
| Supported Recall | 1.000 |
| Unsupported Recall | 0.909 |
| Tool Selection Accuracy | 1.000 |
| Parameter Accuracy | 0.909 |
| Parameter Completeness | 1.000 |
| Schema Valid Rate | 1.000 |
| Extra Tool Rate | 0.000 |

Two cases are retained:

- `unsupported-smart-home-001`: historical V2 Gold says the explicit living-room
  light command is unsupported. Stage 18.1 intentionally authorizes that exact
  request, so this is attributed to capability authorization change, not
  unrelated SmartHome over-selection. V2 Gold remains unchanged.
- `unsupported-calendar-002`: the model returned `next_month` instead of Gold
  `next month`; this is an existing calendar parameter exact-match issue.

No weather, calendar, navigation, or notification case selected SmartHome.

## 17. Side-effect Minimality

Weather-only, calendar-only, and notification-only cases selected their single
required tool. Air-conditioner temperature requests selected SmartHome only and
did not add Weather. SmartHome dataset Extra Tool Rate is 0.000.

## 18. Current Limitations

- Mock execution only
- no real device state or verification
- no scheduler, triggers, scenes, or proactive control
- no unspecified-room default
- no tool retry or semantic retry
- no real IoT provider

## 19. Dynamic SmartHome Boundary

`DynamicTaskOrchestrator` is unchanged. SmartHome is not authorized for dynamic
continuations or dynamic side-effect proposals.

## 20. VehicleTool Implications

Action-aware risk can later represent HIGH actions without another structural
RiskPolicy rewrite. Stage 18.1 does not implement or authorize VehicleTool.

## 21. Conclusion

Stage 18.1 completes static SmartHome proposal authorization with deterministic
action-aware risk and enforced human confirmation. Offline tests pass, real
Planner evaluation completed, no Planner Eval executed a Tool, and no real IoT
operation occurred.
