# SmartHomeTool V1

## 1. Goal

Stage 18 installs `smart_home_tool` as deterministic mock capability infrastructure.
It validates the existing `BaseTool -> ToolRegistry -> ToolArgumentValidator ->
ToolExecutor` path without authorizing Planner or dynamic use.

## 2. Stage 17.2 Baseline

The baseline before this stage was `318 passed`. The installed tools were
`weather_tool`, `navigation_tool`, `calendar_tool`, and `notification_tool`.
The authorized dynamic side effect remained notification-only and protected by
RiskPolicy plus human confirmation.

## 3. Why Smart Home Is Different

Weather, navigation, and calendar reads return information. Smart-home actions
represent physical-world changes. Installing a Tool implementation therefore
does not grant a Planner or runtime permission to use it.

## 4. Physical-world Side-effect Semantics

`smart_home_tool` models physical control commands, but Stage 18 executes only a
local simulation. No result from this Tool proves that a physical device changed.

## 5. Supported Device Types

- `light`
- `air_conditioner`

`device_id` is a non-empty mock logical identifier such as
`living-room-light` or `bedroom-ac`. It is not a real device registry ID.

## 6. Supported Actions

- `turn_on`
- `turn_off`
- `set_temperature`

No scenes, schedules, triggers, discovery, pairing, or other device classes are
supported.

## 7. Input Schema

`SmartHomeToolInput` contains:

- `device_id: str` (required, trimmed, blank values rejected)
- `device_type: SmartHomeDeviceType` (required)
- `action: SmartHomeAction` (required)
- `value: int | float | None = None` (optional)

Unknown fields are forbidden.

## 8. Action/Device Compatibility

| Device | `turn_on` | `turn_off` | `set_temperature` |
| --- | --- | --- | --- |
| `light` | allowed | allowed | rejected |
| `air_conditioner` | allowed | allowed | allowed |

Compatibility is enforced deterministically by the Pydantic input model.

## 9. Temperature Contract

`set_temperature` requires an explicit numeric `value`, applies only to
`air_conditioner`, and accepts `16 <= value <= 30` degrees Celsius. Boolean
values, Fahrenheit input, missing values, and automatic defaults are rejected.
Power actions require `value=None`.

## 10. Result Schema

`SmartHomeToolResult` contains:

- `device_id`
- `device_type`
- `action`
- `status`, fixed to `mock_executed`
- `state: dict[str, Any]`

Power actions return `state.power` as `on` or `off`. Temperature actions return
the requested value as `state.temperature`.

## 11. Mock Execution Semantics

`mock_executed` means the FlowMate local mock accepted and simulated a valid
command. It does not mean a real light, air conditioner, home, or IoT platform
was contacted or changed.

## 12. Deterministic Behavior

The Tool uses no UUID, timestamp, random value, persisted device state, or
random failure. The same validated input produces the same structured result.

## 13. Registry Integration

The default Registry now installs:

- `weather_tool`
- `navigation_tool`
- `calendar_tool`
- `notification_tool`
- `smart_home_tool`

Installed capability coverage is now 5 of the 6 originally planned tools.

## 14. Validator Integration

`ToolArgumentValidator` obtains `SmartHomeToolInput` from the registered Tool's
`input_schema`. No SmartHome-specific branch was added.

## 15. Executor Integration

`ToolExecutor` resolves the Tool by name and invokes the existing `BaseTool.run`
path. Neither ToolExecutor, TaskExecutor, nor StepExecutor required a SmartHome
dispatch branch or core change.

Direct `ToolExecutor` integration tests prove infrastructure behavior only.
They do not establish permission for an LLM or product runtime to control a
home.

## 16. Installed vs Authorized Capability

These are separate boundaries:

`Registry-installed capability != Planner-authorized capability != execution-authorized capability`

Installed capabilities: 5. Planner-authorized capabilities remain 4:
`weather_tool`, `navigation_tool`, `calendar_tool`, and `notification_tool`.
`smart_home_tool` is not included in the Planner prompt or whitelist.

## 17. Risk/HITL Boundary

Smart-home control is a physical-world side effect. Stage 18 does not add it to
RiskPolicy and does not create a confirmation flow. Future authorization must
define deterministic risk and HITL rules before Planner or dynamic access is
allowed.

Possible future policy may distinguish actions, but the current RiskPolicy is
tool-level. This stage does not introduce tool-plus-action risk policy. A future
door-lock capability could require higher risk than the current light and air
conditioner actions, but door locks are not part of V1.

## 18. Current Limitations

- mock logical device IDs only
- no real device registry or state
- no real IoT protocol, network, API, or device
- no Planner authorization
- no DynamicTaskOrchestrator authorization
- no RiskPolicy mapping or smart-home HITL flow
- no scheduler, trigger, automation, or scene
- only lights and air conditioners

## 19. Stage 18.1 Readiness

The infrastructure contract is ready for a separate authorization design stage.
That stage must explicitly decide risk, confirmation, Planner access, and
execution boundaries. Stage 18 does not make those decisions.

## 20. Conclusion

Stage 18 installs a small, deterministic Mock SmartHomeTool while preserving all
authorization boundaries. Adding the fifth Tool required no ToolExecutor core
change, which validates the extensibility of BaseTool, Registry lookup, and
schema-driven argument validation.
