# Minimal Cross-device Task Handoff V1

Stage 29 adds a small coordination layer that lets one existing FlowMate Task move from a Phone Web Client to a Car Simulator Web Client without creating a second Task or rerunning the Agent plan.

## Product Boundary

The V1 claim is deliberately narrow:

```text
Phone Web Client
  -> shared Task + minimized handoff context
  -> Car Simulator Web Client
  -> shared state is visible on Phone again
```

Both clients are browser applications backed by the same FastAPI process and SQLite database. The Car client is a simulator. This is not a native mobile application, a production authentication system, or a real vehicle integration.

## Architecture

```text
                   Shared Backend
             +-------------------------+
             | FastAPI                 |
Phone Web -->| TaskDeviceState         |<-- Car Simulator
             | DeviceRegistryService   |
             | deterministic Router    |
             | HandoffService          |
             | SQLite persistence      |
             +-------------------------+
                         |
                  existing Agent runtime
                         |
                    existing Tools
```

Cross-device coordination sits beside the existing runtime. Planner prompts, planner authorization, tool schemas, validators, risk policy, executor semantics, and dynamic orchestration are unchanged.

## Data Model

SQLite schema version 3 adds:

- `users`: demo identity ownership.
- `devices`: `PHONE` or `CAR`, status, and last heartbeat time.
- `device_capabilities`: presentation/surface capabilities, separate from Tool capabilities.
- `task_device_state`: owner, origin device, current device, and optimistic-lock version for one existing Task.
- `handoffs`: source, target, minimized context, status, timestamps, and Task version.

The demo registry contains `demo_user`, `phone_001`, and `car_001`. Phone capabilities are calendar, weather, notification, and navigation view. Car capabilities are navigation and mock vehicle status.

## Deterministic Routing and Handoff

The V1 router has one rule: when a Morning Commute Task has navigation context and an online same-user Car with `NAVIGATION`, recommend that Car. Otherwise the Task stays on its current device. The router only recommends; it never transfers ownership.

`HandoffService` validates Task and device ownership, current source ownership, target presence, target capability, expected version, and duplicate pending handoffs. Creation leaves the current device unchanged. Acceptance atomically marks the handoff accepted, moves the current device to the target, and increments the Task device-state version. Reject and cancel keep the current device unchanged. Repeated acceptance is idempotent and cannot increment the version twice.

Only the following context is copied into the handoff: goal, meeting summary and start time, destination, navigation summary, risk level, and confirmation status. The Task ID remains unchanged and the raw Task is not duplicated.

## State Sync and Presence

The Phone and Car clients poll coordination-only endpoints every 2 seconds. They do not poll trigger ticks or execute Tools. Each client sends a heartbeat every 4 seconds; a device is considered online when its latest heartbeat is no more than 10 seconds old.

Polling is sufficient for this portfolio V1 because it makes the shared-state behavior deterministic, inspectable, and easy to run locally. SSE or WebSocket could replace the transport later without changing the Task, device, or handoff invariants, but that is outside Stage 29.

## Concurrency and Safety

Every cross-device state mutation uses `expected_version`. A stale write returns HTTP `409 Conflict`; it is never silently overwritten. Coordinated confirmation uses the same version claim so two open clients cannot win the same pending confirmation. Exactly one state transition and one side effect can succeed.

Device IDs supplied by a client are not treated as authorization. The coordination layer verifies that devices exist and belong to the Task owner. This demo identity model is not production authentication: it intentionally includes no password, session, JWT, OAuth, RBAC, or multi-tenant boundary.

Handoff does not bypass RiskPolicy or HITL. It reuses an existing Task and context, and does not invoke Planner, Calendar, or dynamic re-planning. Real vehicle, smart-home, Feishu, Google, Weather, and Amap calls are all zero in the offline Stage 29 smoke and regression suite.

## Local Demo

```powershell
$env:FLOWMATE_DEMO_MODE="true"
uvicorn main:app --host 127.0.0.1 --port 8000

cd frontend
npm run dev
```

Open two browser windows:

- Phone: `http://localhost:5173/phone`
- Car simulator: `http://localhost:5173/car`

Create the Morning Commute Task on Phone, keep Car open so its heartbeat makes it online, request the recommended handoff, and accept it on Car. Car displays the existing navigation context and Phone observes `current_device_id=car_001` on its next poll.

Offline verification:

```powershell
python scripts/cross_device_handoff_smoke.py
python scripts/eval_cross_device.py
python -m pytest
cd frontend
npm run build
```

## Verified Result

- `42` Stage 29 tests were added; the full suite passes with `739 passed`.
- Cross-device Eval V1 has `16` deterministic cases and all eleven metrics are `1.000`.
- The frontend production build passes.
- A two-browser acceptance run verified Phone create -> pending handoff -> Car receive/accept -> Phone automatic update with the same Task ID.
- SQLite restart preserves the accepted handoff and current device.

## Known Limitations

- Phone is a Web Client and Car is a Web Simulator.
- There is no real vehicle integration or native mobile app.
- Identity is a single-user demo model, not production authentication.
- Sync is polling-based; there is no WebSocket or SSE.
- There is no distributed coordination, multi-instance locking, or production presence service.
- Feishu real-send final verification remains pending independently of Stage 29.

Stage 29 is complete and feature development is frozen here. No Home/Watch client, real car, native app, WebSocket rewrite, RAG, memory, or multi-agent expansion is part of this stage.
