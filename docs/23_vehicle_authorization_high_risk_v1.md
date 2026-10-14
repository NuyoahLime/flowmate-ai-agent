# Vehicle Planner Authorization & HIGH-Risk Action Policy V1

## 1. Goal

Stage 19.1 authorizes `LLMPlanner` to propose the five existing VehicleTool
actions. Deterministic action-aware RiskPolicy assigns LOW, MEDIUM, or HIGH risk,
and existing HITL plus TaskExecutor gates all side effects.

## 2. Stage 19 Baseline

The baseline was `444 passed`. All six planned tools were installed, but Vehicle
was absent from Planner and RiskPolicy. Vehicle remained a deterministic offline
mock with no movement or real API capability.

## 3. Why Vehicle Is Different

VehicleTool is safety-sensitive and combines read-only status with physical-world
control commands. Planner proposal, deterministic risk, human approval, and
execution authorization remain separate boundaries.

## 4. Planner Authorization

The Planner whitelist now contains all six installed tools. Vehicle authorization
allows proposals only; it does not bypass RiskPolicy or confirmation.

## 5. Vehicle Capability Boundary

Supported explicit immediate actions are `get_status`, `start_climate`,
`stop_climate`, `lock`, and `unlock`. `vehicle_id=my-car` is the canonical mock
logical identifier when the user explicitly refers to their car.

`get_status` returns only mock locked and climate states. Fuel, battery, charge,
location, speed, mileage, tire pressure, and other telemetry are unsupported.

## 6. Read vs Physical Side Effects

`get_status` is read-only. Climate, lock, and unlock actions represent side
effects. This distinction proves that one Tool can contain actions with different
risk and confirmation requirements.

## 7. LOW / MEDIUM / HIGH Risk Contract

- LOW: no confirmation
- MEDIUM: confirmation required
- HIGH: confirmation required

`RiskAssessment` fields remain unchanged.

## 8. Action-aware Vehicle Risk Matrix

| Action | Risk | Confirmation |
| --- | --- | --- |
| `get_status` | LOW | no |
| `start_climate` | MEDIUM | required |
| `stop_climate` | MEDIUM | required |
| `lock` | HIGH | required |
| `unlock` | HIGH | required |

Each action has an explicit matrix entry. VehicleTool is not assigned one coarse
tool-level risk.

## 9. Why Lock/Unlock Are HIGH in V1

Lock and unlock change a security-sensitive physical-world state. V1 applies a
conservative HIGH classification to both. Unlock is FlowMate's first explicit
HIGH-risk action.

## 10. Validated Arguments as Risk Source

LLM output passes `ToolArgumentValidator` before Task construction and
`RiskPolicy.apply_to_task`. Schema validation owns vehicle ID, action, temperature
compatibility, and the 16-30 range. RiskPolicy reads the validated action only.

## 11. LLM Risk Metadata Is Untrusted

Model LOW/no-confirmation metadata for unlock becomes HIGH/confirmation-required.
Model HIGH/confirmation metadata for get_status becomes LOW/no-confirmation.
Deterministic policy is the sole final risk source.

## 12. Fail-Closed Behavior

Unknown Vehicle actions raise `UnknownActionRiskError`. Unknown tools continue to
raise `UnknownToolRiskError`. Name-only Vehicle risk assessment is rejected because
the action contract is required.

## 13. Highest-Risk Task Rule

Task risk is the highest action risk independent of ToolCall order. Calendar plus
status is LOW; weather plus climate is MEDIUM; notification plus unlock is HIGH;
SmartHome plus lock is HIGH.

## 14. get_status No-confirm Lifecycle

Planner produces a LOW Task with `requires_confirmation=false` and
`confirmation_status=NOT_REQUIRED`. TaskExecutor executes it directly to
COMPLETED. The mock VehicleTool execution count is one.

## 15. MEDIUM Climate HITL Lifecycle

An unconfirmed start-climate Task is blocked with zero executions. After request
and confirm, `start_climate temperature=24` executes once and returns
`climate=on`, `temperature=24`, and `status=mock_executed`.

## 16. HIGH Lock/Unlock HITL Lifecycle

Pending lock and unlock Tasks are blocked with zero executions. Confirmed HIGH
actions execute exactly once. Rejected unlock becomes CANCELLED and executes zero
times.

## 17. Duplicate Side-effect Protection

After confirmed unlock completes, a second TaskExecutor call is rejected because
the Task is already COMPLETED. Execution count remains one.

## 18. Vehicle Movement Safety Boundary

Vehicle movement, remote driving, autonomous driving, summon, engine control,
trunk/window control, horn, lights, charging, scheduled control, and conditional
control remain unsupported. Route planning remains navigation-only, including
when the user will drive personally.

## 19. Vehicle Planner Dataset

`evals/planner_vehicle_v1.json` contains 24 cases:

- vehicle_status_supported: 4
- vehicle_climate_supported: 6
- vehicle_lock_supported: 3
- vehicle_unlock_supported: 3
- vehicle_movement_unsupported: 3
- unsupported_vehicle_action: 2
- scheduled_conditional_unsupported: 2
- non_vehicle_minimality: 1

## 20. Real Provider Eval

The final `deepseek-v4-flash` run completed all 24 cases in 24 attempts with zero
retry. Every aggregate, category, parameter, minimality, action-risk, and
high-risk classification metric was 1.000. Extra Tool Rate was 0.000.

The first V2 run exposed `unsupported-vehicle-002`: fuel-level information was
incorrectly mapped to `get_status`. The Prompt was narrowed to the actual result
contract, then both complete datasets were rerun. Gold and Tool contracts were
unchanged.

## 21. V2 Regression / Capability Drift

Final 22-case V2 metrics:

| Metric | Result |
| --- | ---: |
| Scenario Accuracy | 0.955 |
| Supported Recall | 1.000 |
| Unsupported Recall | 0.909 |
| Tool Selection Accuracy | 1.000 |
| Parameter Accuracy | 1.000 |
| Parameter Completeness | 1.000 |
| Schema Valid Rate | 1.000 |
| Extra Tool Rate | 0.000 |

No V2 Vehicle Gold is stale: movement, fuel telemetry, and remote engine start
remain unsupported. Vehicle over-selection is zero after boundary hardening.
The only remaining failure is `unsupported-smart-home-001`, an existing
capability-driven drift because V2 predates SmartHome authorization.

## 22. High-risk Metrics

Offline deterministic and HITL metrics:

- Action Risk Accuracy: 1.000
- High-Risk Classification Accuracy: 1.000
- High-Risk Pre-confirmation Blocking Rate: 1.000
- High-Risk Confirmed Execution Accuracy: 1.000
- High-Risk Rejection Containment Rate: 1.000
- Read-only No-confirm Accuracy: 1.000

## 23. Real Vehicle Safety Boundary

Planner Eval executes no Tool. HITL tests execute only the local deterministic
mock after required confirmation. No real API, network, OEM system, or physical
vehicle was accessed or controlled.

## 24. Current Limitations

- no real status or telemetry
- no real vehicle state persistence
- no movement or autonomous capability
- no scheduler, trigger, proactive control, retry, or fallback
- static Planner flow only

## 25. Dynamic Vehicle Boundary

`DynamicTaskOrchestrator` is unchanged. Vehicle is not authorized for dynamic
continuations or dynamic side-effect proposals.

## 26. Eval V3 Recommendation

A future evaluation-maintenance stage should create `planner_eval_v3` to reflect
the authorized SmartHome and Vehicle capability baseline while retaining hard
negative vehicle movement and telemetry cases. Stage 19.1 does not create or
modify that dataset.

## 27. Conclusion

Stage 19.1 establishes the first complete LOW/MEDIUM/HIGH action-risk policy,
preserves fail-closed boundaries, and enforces confirmation for all Vehicle side
effects. Real Planner evaluation completed without Tool execution or real vehicle
access.
