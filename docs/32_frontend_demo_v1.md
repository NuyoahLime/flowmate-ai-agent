# Stage 27: Frontend Demo V1

## 1. Goal

Stage27 adds a browser workspace that makes FlowMate's planner, tool trace,
observations, HITL, persistence, evals, and proactive triggers visible.

## 2. Stack

Frontend uses Vue 3, Vite, and TypeScript in `frontend/`.

## 3. Backend Source of Truth

The frontend reads only FastAPI endpoints. It does not read SQLite, eval JSON,
Python files, or docs directly.

## 4. Demo Mode

`FLOWMATE_DEMO_MODE=true` uses mock providers for Calendar, Weather, Navigation,
and Notification.

## 5. Main Scenario

Morning Commute shows Calendar observation, weather, navigation, dynamic
re-plan, notification proposal, MEDIUM risk, pending confirmation, and mock
notification delivery after confirm.

## 6. Safety Scenarios

SmartHome and Vehicle presets create pending mock side-effect tasks. Vehicle
unlock is HIGH risk.

## 7. API

- `POST /api/v1/demo/tasks`
- `GET /api/v1/tasks`
- `GET /api/v1/tasks/{task_id}`
- `POST /api/v1/tasks/{task_id}/confirm`
- `POST /api/v1/tasks/{task_id}/reject`
- `GET /api/v1/triggers`
- `GET /api/v1/triggers/{trigger_id}`
- `POST /api/v1/triggers/tick`
- `GET /api/v1/evals`
- `GET /api/v1/system/status`

## 8. UI Structure

The workspace has task history, trigger history, eval dashboard, scenario input,
current task, agent timeline, HITL panel, result cards, integration status, and
developer details.

## 9. Secret Boundary

The UI does not display provider secrets, tokens, hidden chain-of-thought, or
raw provider payloads.

## 10. Build

```powershell
cd frontend
npm install
npm run build
```

The local machine has Node 12, so the frontend pins a compatible Vue 3/Vite 2
toolchain.

## 11. Current Limitations

No login, WebSocket, background scheduler, mobile app, real Feishu delivery, or
new Agent capability is added in this stage.
