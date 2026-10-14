# Cross-device Demo Checklist

Use this checklist for the Phone Web + Car Web Simulator portfolio demo. It does not require or claim real vehicle hardware.

## Before Demo

- [ ] Start backend with `FLOWMATE_DEMO_MODE=true` and a known local SQLite path.
- [ ] Start the frontend and confirm the API base URL targets that backend.
- [ ] Reset or choose a clean demo database.
- [ ] Open `/phone`; confirm `phone_001` heartbeat makes it ONLINE.
- [ ] Open `/car`; confirm the page says `CAR SIMULATOR`, `NO REAL VEHICLE CONTROL`, and `car_001 ONLINE`.

## Demo

- [ ] Phone creates the Morning Commute Task.
- [ ] Record the Phone `task_id`, version and `current_device=phone_001`.
- [ ] Show Calendar, Weather and Navigation in the Agent trace.
- [ ] Show deterministic Router recommendation for `car_001`.
- [ ] Phone requests handoff; verify `PENDING` and version increment.
- [ ] Car receives the same `task_id`, source `phone_001` and reused meeting/route context.
- [ ] Car accepts; verify `ACCEPTED`, new version and current device `car_001`.
- [ ] Return to Phone; verify its next poll shows Car takeover and the accepted timeline.

## Evidence

- [ ] `task_id` is identical on Phone and Car.
- [ ] Version changes from 1 to 2 on request and 2 to 3 on accept.
- [ ] `current_device` changes from `phone_001` to `car_001` only after accept.
- [ ] Meeting, destination and navigation summary are reused.
- [ ] Planner does not rerun during handoff.
- [ ] Calendar does not rerun during handoff.
- [ ] Duplicate Task count is zero.
- [ ] Real Google, Open-Meteo, Amap, Feishu, Vehicle and SmartHome calls are zero in demo mode.

## Recovery

- If Router shows unavailable, keep `/car` open and wait for its heartbeat, then let Phone poll again.
- If a write returns 409, reload coordination state and use the latest version; do not retry a stale mutation blindly.
- If the database contains an old pending handoff, use a clean demo database rather than modifying product behavior during the presentation.
