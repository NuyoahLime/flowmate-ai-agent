# Runbook

## Offline Demo

Use Demo Mode for interviews and portfolio review:

```powershell
$env:FLOWMATE_DEMO_MODE="true"
$env:FLOWMATE_DB_PATH="data/flowmate_demo.db"
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Demo Mode uses Mock Calendar, Mock Weather, Mock Navigation and Mock Notification. Agent Core, Planner, RiskPolicy, Persistence and Trigger evaluation still use real project code.

## Seed

```powershell
python scripts/demo_seed.py
```

The seed script is idempotent and creates deterministic demo data.

## Reset

```powershell
python scripts/demo_reset.py
```

This only resets the demo database path you configure. It is not a production delete API.

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

Vite attempts its configured dev port first. If the port is occupied, use the next available URL printed by Vite.

Open two independent clients:

- `/phone` — Phone Web Client.
- `/car` — Car Web Simulator; keep it open so heartbeat marks `car_001` ONLINE.

## Build

```powershell
cd frontend
npm run build
```

## Tests

```powershell
python -m pytest
```

## Main Demo Order

1. Phone creates Morning Commute; record `task_id`, version 1 and `current_device=phone_001`.
2. Show Calendar observation, Weather, Navigation and the preserved Agent Trace.
3. Show Router recommending online `car_001`; Phone requests Handoff and reaches PENDING/version 2.
4. Car displays the same `task_id` and context, then accepts; show version 3/current device Car.
5. Return to Phone and show automatic poll update plus accepted timeline.
6. Open the MEDIUM notification and show backend HITL before any side effect.
7. Show Planner Eval V3, Trigger Eval V1, Cross-device Eval V1 and the provider matrix.

Use [Cross-device Demo Checklist](cross_device_demo_checklist.md) for the full preflight and evidence list.
