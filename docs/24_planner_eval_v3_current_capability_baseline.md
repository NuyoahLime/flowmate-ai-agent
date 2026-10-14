# Planner Eval V3 Current Capability Baseline

## 1. Goal

Stage 20 creates `planner_eval_v3.json` as the current static Planner capability
baseline. It consolidates all six Planner-authorized tools and their current
unsupported boundaries without changing Planner, risk, Tool, or execution code.

## 2. Why V3 Is Needed

V2 predates SmartHome and Vehicle Planner authorization. Its
`unsupported-smart-home-001` Gold conflicts with the current capability contract.
Historical V2 remains useful, but it cannot remain the current baseline.

## 3. V1 / V2 / V3 History

- V1: early weather/navigation Planner baseline
- V2: calendar-era intermediate capability baseline
- V3: current six-tool static Planner capability baseline

V1 and V2 remain immutable historical artifacts.

## 4. Current Tool Capability Matrix

| Capability | Installed | Planner | Risk | Confirm | Dynamic | API |
| --- | --- | --- | --- | --- | --- | --- |
| weather | yes | yes | LOW | no | yes | mock |
| navigation | yes | yes | LOW | no | yes | mock |
| calendar read | yes | yes | LOW | no | yes | mock |
| immediate notification | yes | yes | MEDIUM | yes | yes | mock |
| SmartHome supported actions | yes | yes | MEDIUM | yes | no | mock |
| vehicle status | yes | yes | LOW | no | no | mock |
| vehicle climate | yes | yes | MEDIUM | yes | no | mock |
| vehicle lock/unlock | yes | yes | HIGH | yes | no | mock |

## 5. Current Planner Authorization Matrix

All six installed tools are authorized for static Planner proposals:
weather, navigation, calendar, notification, SmartHome, and Vehicle. Planner
authorization remains separate from execution authorization.

## 6. Current Risk Matrix

LOW covers weather, navigation, calendar, and vehicle status. MEDIUM covers
notification, supported SmartHome actions, and vehicle climate. HIGH covers
vehicle lock and unlock. Dataset risk fields describe deterministic policy Gold,
not model-owned metadata.

## 7. V2 Drift Audit

`planner_eval_v2_to_v3_audit.json` contains all 22 V2 Case IDs. One record changed:

- `unsupported-smart-home-001`: unsupported/[] became
  supported/[smart_home_tool], sourced from Stage 18.1.

All other V2 capability contracts remain unchanged. Compact V3 omits repetitive
phrasing through an explicit `v3_included` field rather than silently deleting
audit history.

## 8. Capability-driven vs Model-driven Relabeling

Allowed audit change types are `unchanged`, `capability_driven_relabel`, and
`capability_driven_parameter_update`. Capability-driven relabel count is one.
Model-driven relabel count is zero.

## 9. V3 Dataset Design

The current V3 dataset contains 38 representative, boundary-heavy Cases: 26
supported and 12 unsupported. Two navigation Cases were added after the Stage 20
baseline to verify that explicit clock times, origins, and destinations survive
planning. It remains a compact regression suite rather than a concatenation of
the Notification, SmartHome, Vehicle, Calendar, or dynamic specialist datasets.

## 10. Supported Capability Coverage

- weather_supported: 3
- navigation_supported: 5
- calendar_read_supported: 4
- notification_immediate_supported: 3
- smart_home_supported: 5
- vehicle_supported: 6

Static multi-tool coverage includes weather plus navigation and calendar plus a
fully specified navigation request.

## 11. Unsupported Boundary Coverage

- scheduled_automation_unsupported: 2
- conditional_automation_unsupported: 2
- unsupported_smart_home: 3
- unsupported_vehicle_movement: 2
- unsupported_vehicle_action_or_telemetry: 2
- calendar_write_unsupported: 1

These cover real-state guarantees, scenes, unsupported devices, vehicle movement,
fuel telemetry, engine start, and calendar writes.

## 12. Tool Minimality Coverage

V3 includes representative single-tool Gold for every authorized tool. Route
planning while the user drives remains navigation-only. Vehicle status remains
vehicle-only. The real run produced Extra Tool Rate 0.000.

## 13. Static vs Dynamic Eval Separation

V3 evaluates static LLM planning only. Calendar-observation continuation and
dynamic notification authorization remain covered by their existing dynamic
datasets. V3 does not call TaskExecutor, ToolExecutor, or any Tool.

## 14. Real Provider Results

The saved `deepseek-v4-flash` Stage 20 snapshot completed 36 Cases with 37
provider attempts. It predates the two explicit-constraint Cases and is retained
as historical evidence; its metrics must not be presented as a real-provider run
of the current 38-Case dataset.

| Metric | Result |
| --- | ---: |
| Scenario Accuracy | 1.000 |
| Supported Recall | 1.000 |
| Unsupported Recall | 1.000 |
| Tool Selection Accuracy | 1.000 |
| Parameter Accuracy | 1.000 |
| Parameter Completeness | 1.000 |
| Schema Valid Rate | 1.000 |
| Extra Tool Rate | 0.000 |
| Current Capability Accuracy | 1.000 |

All twelve capability-group recalls are 1.000.

Real-provider evaluation of the current 38-Case dataset has not been run in the
free-text Agent integration work. The two new Cases are covered by offline
Planner validation tests only.

## 15. Failure Attribution

Final failure IDs: none. One bounded infrastructure retry occurred for
`unsupported-calendar-002`: the first attempt returned `provider_empty_output`,
and the second attempt succeeded. No semantic retry occurred.

## 16. Exact-match Findings

Formal Parameter Accuracy remains exact equality and scored 1.000. No punctuation
or whitespace normalization was added. A normalized parameter diagnostic remains
not implemented and does not alter the formal metric.

## 17. V3 as Current Regression Baseline

Manifest status for V3 is `current_capability_baseline`. Future static capability
changes require a new version or an explicit audited Gold migration.

## 18. Historical Baseline Preservation

V2 status is `historical_capability_baseline`. Its SHA-256 remained
`000991CBFA56E4A38D1E6E7E79B8081B73B13E0CAB5AF4418D0CFFC6E1FCAD0F`
before and after Stage 20. V1 remains `historical_baseline`.

## 19. Current Limitations

- all six Tools use mock data or mock execution
- no real provider adapters for domain Tools
- no persistence, frontend, scheduler, or trigger engine
- SmartHome and Vehicle are static-only
- dynamic behavior remains intentionally narrow

## 20. Next Productization Phase

The static Agent core and current capability regression baseline are ready for
productization. Recommended real-adapter order is Calendar, Weather, Navigation,
Notification, then explicit SmartHome and Vehicle integration strategy. Real
Vehicle control should not be the first productization step.

## 21. Conclusion

Stage 20 establishes an audited, reproducible current static Planner baseline.
All offline tests and real V3 metrics pass, historical data remains preserved,
and no execution or real-device boundary was expanded.
