# VehicleTool V1

## 1. Goal

Stage 19 installs a deterministic offline `vehicle_tool` through the existing
`BaseTool -> ToolRegistry -> ToolArgumentValidator -> ToolExecutor` path. It does
not authorize Planner, RiskPolicy, HITL product flow, or dynamic use.

## 2. Stage 18.1 Baseline

The baseline was `394 passed`. Five tools were installed and Planner-authorized:
weather, navigation, calendar, notification, and SmartHome. SmartHome execution
was protected by action-aware risk and human confirmation.

## 3. Why Vehicle Is Safety-sensitive

Vehicle control represents a safety-critical physical-world side effect. A
working Tool implementation does not establish authority to control a vehicle.
Installation, Planner authorization, risk approval, confirmation, and execution
authorization remain separate boundaries.

## 4. Supported Actions

- `get_status`
- `lock`
- `unlock`
- `start_climate`
- `stop_climate`

`get_status` is read-only. The remaining actions model limited control commands.

## 5. Unsupported Vehicle Movement

The Tool has no engine-start, remote-driving, movement, parking, summon, route
control, or autonomous-driving action. It cannot move a vehicle or cause a
vehicle to drive itself.

## 6. Input Schema

`VehicleToolInput` contains:

- `vehicle_id: str` (required)
- `action: VehicleAction` (required)
- `temperature: int | float | None = None` (optional)

Unknown fields are forbidden. `vehicle_id` is trimmed and must be non-empty. It
is a mock logical identifier such as `my-car`, not a VIN or real registry ID.

## 7. Argument Contract

| Action | Temperature |
| --- | --- |
| `get_status` | must be `None` |
| `lock` | must be `None` |
| `unlock` | must be `None` |
| `start_climate` | optional |
| `stop_climate` | must be `None` |

An omitted `start_climate` temperature means only start the mock climate system;
it does not infer a target temperature.

## 8. Climate Temperature Contract

When provided for `start_climate`, temperature must satisfy
`16 <= temperature <= 30` degrees Celsius. Boolean values, Fahrenheit values,
automatic conversion, and a default 24 degrees are not supported.

## 9. Result Schema

`VehicleToolResult` contains:

- `vehicle_id`
- `action`
- `status`, fixed to `mock_executed`
- `state: dict[str, Any]`

## 10. Mock Execution Semantics

`mock_executed` means the FlowMate test environment accepted and simulated the
command. It does not mean a real command was accepted or a real vehicle changed
state. In particular, an unlock result does not mean a physical vehicle unlocked.

## 11. Deterministic Behavior

The same validated input produces the same result. The Tool uses no UUID,
timestamp, random battery, speed, location, temperature, state, or failure.

## 12. Registry Integration

The default Registry now installs six tools:

- `weather_tool`
- `navigation_tool`
- `calendar_tool`
- `notification_tool`
- `smart_home_tool`
- `vehicle_tool`

Original planned Tool coverage is now 6 of 6.

## 13. Validator Integration

`ToolArgumentValidator` resolves VehicleTool through the Registry and validates
against `VehicleTool.input_schema`. No Vehicle-specific validation branch exists.

## 14. Executor Integration

`ToolExecutor` resolves `vehicle_tool` by name and uses the existing
`BaseTool.run` path. ToolExecutor, TaskExecutor, and StepExecutor required no
Vehicle-specific dispatch or core change.

Infrastructure tests call ToolExecutor directly only to verify the Tool
contract. This is not a product authorization path.

## 15. Installed vs Planner-authorized

Installed capabilities: 6 of 6. Planner-authorized capabilities remain 5 of 6:
weather, navigation, calendar, notification, and SmartHome. VehicleTool is not
included in the Planner whitelist or prompt.

## 16. Read vs Control Capability Distinction

VehicleTool is the first FlowMate Tool containing both a read action
(`get_status`) and control actions (`lock`, `unlock`, climate commands). This
distinction is preserved so a later policy can assign different risks inside a
single Tool.

## 17. Risk Hypothesis for Stage 19.1

Future work may consider `get_status` LOW, climate commands MEDIUM, and unlock
HIGH. Lock may require MEDIUM or HIGH. These are hypotheses only. Stage 19 does
not add VehicleTool to RiskPolicy or establish any Vehicle risk contract.

## 18. Current Limitations

- local deterministic mock only
- no real vehicle registry or persisted state
- no OEM API, CAN bus, OBD, Bluetooth, MQTT, or network
- no movement, remote driving, parking, summon, or autonomous driving
- no Planner, RiskPolicy, HITL product, or dynamic authorization
- no scheduler, trigger, proactive control, or retries

## 19. No Real Vehicle Guarantee

No real vehicle API is called and no physical vehicle is read, locked, unlocked,
started, stopped, moved, or otherwise controlled. Mock output cannot verify real
vehicle state.

## 20. Stage 19.1 Readiness

The input contract preserves enough action detail for a future action-aware risk
design. That future stage must explicitly authorize Planner access and define
risk plus confirmation before any product execution path is permitted.

## 21. Conclusion

Stage 19 completes the sixth Tool infrastructure implementation while preserving
all authorization boundaries. The generic BaseTool, Registry, schema-driven
validation, and ToolExecutor architecture required no core execution changes.
