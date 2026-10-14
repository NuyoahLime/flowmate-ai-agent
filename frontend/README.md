# FlowMate Frontend Demo

This is the Vue workspace for FlowMate Portfolio V1. It renders backend state only; it does not read SQLite, eval JSON, Python files or provider payloads directly.

## Current Validated Local Toolchain

- Node `v12.16.1`
- npm `6.13.4`
- Vue `3.2.47`
- Vite `2.9.18`
- TypeScript `4.9.5`

This is a compatibility baseline for the current portfolio demo environment, not a recommended modern production baseline. Dependencies are intentionally not upgraded in Stage 28.

## Install

```powershell
npm install
```

## Dev

```powershell
npm run dev
```

Vite attempts the configured dev port first. If it is occupied, use the next available URL printed by Vite. In the latest local validation FlowMate used:

```text
http://localhost:5174/index.html
```

Do not assume 5174 is permanent.

## Build

```powershell
npm run build
```

The build command runs:

```text
tsc --noEmit && vite build
```

## API URL

Create `.env` from `.env.example` when needed:

```powershell
VITE_FLOWMATE_API_BASE_URL=http://localhost:8000
```

The frontend API client files live in `src/api/`:

- `client.ts`
- `tasks.ts`
- `triggers.ts`
- `evals.ts`
- `system.ts`

## Demo Mode

Run the backend with mock providers:

```powershell
$env:FLOWMATE_DEMO_MODE="true"
$env:FLOWMATE_DB_PATH="data/flowmate_demo.db"
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Optional deterministic seed:

```powershell
python scripts/demo_seed.py
```

Optional reset:

```powershell
python scripts/demo_reset.py
```

## Main Demo Flow

1. Run Morning Commute.
2. Inspect Calendar observation, weather, route and notification proposal.
3. Confirm the pending MEDIUM notification.
4. Run Vehicle Safety and reject the HIGH-risk action.
5. Evaluate proactive triggers.
6. Refresh and verify task history remains.

## Safety Boundary

The frontend renders backend state. It does not implement:

- RiskPolicy
- TriggerEvaluator
- Task status machine
- Confirmation rules
- Tool execution
- Secret handling

Do not expose provider raw payloads, hidden chain-of-thought, API keys, OAuth tokens, webhooks or local secret files in UI.
