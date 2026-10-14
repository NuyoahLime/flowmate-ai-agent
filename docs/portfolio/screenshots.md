# Screenshot Evidence

Screenshot capture status: `CAPTURED_FROM_REAL_LOCAL_RUNTIME`

All eight images below were captured from the running FlowMate backend and frontend on 2026-10-02. They are not mockups, Figma compositions, or AI-generated images. Phone and Car are independent browser clients sharing the same FastAPI/SQLite Task state. The Car surface is explicitly a Web Simulator, not real vehicle hardware.

| File | Scenario | What it proves |
| --- | --- | --- |
| [`01_phone_task_creation.png`](assets/01_phone_task_creation.png) | Phone creates Morning Commute | A real Task ID is created on `phone_001`; initial owner and version are visible. |
| [`02_phone_agent_trace.png`](assets/02_phone_agent_trace.png) | Completed Agent foundation | Calendar, Weather and Navigation steps succeeded before handoff; the trace remains visible. |
| [`03_router_recommendation.png`](assets/03_router_recommendation.png) | Car online and route available | Deterministic router recommends `car_001` from presence, NAVIGATION capability and Task context. |
| [`04_car_incoming_handoff.png`](assets/04_car_incoming_handoff.png) | Car receives pending handoff | Car shows the same Task ID, source `phone_001`, version 2, meeting, destination, route and Accept/Reject controls. |
| [`05_car_accept_handoff.png`](assets/05_car_accept_handoff.png) | Car accepts | Handoff is `ACCEPTED`, version is 3 and the Task surface belongs to `car_001`. |
| [`06_phone_synced_after_handoff.png`](assets/06_phone_synced_after_handoff.png) | Phone next poll | Phone shows the same Task with current owner `car_001`, version 3 and an accepted timeline. |
| [`07_cross_device_eval.png`](assets/07_cross_device_eval.png) | Saved offline eval artifact | The real `cross_device_eval_v1.json` result reports 16/16 passing cases and eleven 1.000 metrics. |
| [`08_safety_hitl.png`](assets/08_safety_hitl.png) | MEDIUM notification pending | RiskPolicy and backend HITL remain active; the side effect awaits explicit confirmation. |

## Key continuity evidence

- A — `01`/`03`: Task ID, `current_device=phone_001`, router recommendation `car_001`.
- B — `04`: the same Task ID arrives from `phone_001` and is still `PENDING` before acceptance.
- C — `05`/`06`: Car accepts, version changes to 3, and Phone automatically sees `current_device=car_001`.
