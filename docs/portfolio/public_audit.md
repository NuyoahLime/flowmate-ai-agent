# Public Repository Audit

Audit scope:

- `README.md`
- `docs/`
- `frontend/`
- `scripts/`
- `evals/`
- `tests/`
- `.env.example`
- `.gitignore`
- `requirements.txt`
- `frontend/package.json`
- `frontend/package-lock.json`

## Secret Search Terms

Searched terms:

- `LLM_API_KEY`
- `AMAP_WEB_SERVICE_KEY`
- `FEISHU_BOT_WEBHOOK_URL`
- `GOOGLE_CALENDAR_TOKEN`
- `client_secret`
- `Bearer`
- `api_key`
- `webhook`
- `secret`
- `token`

Allowed matches:

- `.env.example` variable names and placeholders
- `.gitignore` ignore rules
- Tests using explicit fake values such as `test-secret-key`
- Documentation that says secrets are not printed or persisted

Result: no real secret value found.

## Frontend Dist

`frontend/src` and `frontend/dist` were scanned for core secret names. No real secret value was found.

## Absolute Path / PID / Temp State

Public portfolio docs do not rely on local project-drive paths or user-home paths. Historical stage documents may preserve old local context as audit history.

No public portfolio doc records backend PID, frontend PID or temporary local process IDs.

## Gate

`PUBLIC_SECRET_AUDIT_GATE = PASS`

## Portfolio Claim Audit

- Public title is `FlowMate｜跨设备主动式智能生活 AI Agent`.
- Cross-device claims are limited to Phone Web Client + Car Web Simulator sharing one Task.
- No current portfolio material carries the pre-Stage29 negative Cross-device status.
- No public portfolio material uses an obsolete pre-Stage29 test baseline; current regression is `739 passed`.
- Planner Eval values match `evals/results/llm_planner_v3_stage20.json`; it is not described as all-1.000.
- Real Vehicle, real SmartHome, native mobile and production auth are explicitly NOT IMPLEMENTED.
- Feishu Engineering is PASS and Feishu Real Delivery remains PENDING.
- Eight screenshots under `docs/portfolio/assets/` were captured from the real local runtime.
- LICENSE remains missing and was not selected automatically.

`PUBLIC_CLAIM_GATE = PASS`
