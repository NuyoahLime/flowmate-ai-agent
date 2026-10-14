# Design Decisions

| Decision | Why | Alternative | Why rejected | Trade-off |
| --- | --- | --- | --- | --- |
| Mock-first | Stable offline demo and zero real side effects | Real providers by default | Fragile in interview environment | Mock status must be clearly disclosed |
| Provider Boundary | Keep tools independent from vendor SDKs | Put SDK calls in tools | Harder to test and swap | More interfaces |
| Rule baseline | Establish deterministic comparison | Only LLM planner | No baseline for eval | Rule coverage is limited |
| Structured Output | Validate planner output before Task creation | Parse natural language JSON manually | Brittle and unsafe | More schemas |
| Tool schema source of truth | Arguments validated before execution | Trust prompt instructions | Prompt cannot enforce runtime correctness | Schema maintenance |
| Deterministic RiskPolicy | Safety must not depend on model confidence | Ask LLM for risk | Model risk can drift | Requires action-aware rules |
| Observation-driven planning | Later steps should use real observations | Guess full plan upfront | Wrong route/location risk | More runtime state |
| SQLite V1 | Local persistence and refresh demo | PostgreSQL | Too much ops for portfolio V1 | Not production HA |
| Explicit tick | Controlled proactive behavior | Background scheduler | Hidden side effects and harder tests | Manual demo step |
| Demo Mode | Repeatable offline product demo | Always real API | Network and credential dependency | Need real integration matrix |
| Task-centered instead of Device-centered | Keep one user-owned Task/context across surfaces | Create a new Task per client | Splits history, risk and confirmation state | Requires coordination metadata beside the Agent domain |
| Deterministic Device Router | Routing must be explainable and testable from presence, capability and context | LLM chooses a device | Non-deterministic ownership decisions are hard to audit | V1 rule coverage is intentionally narrow |
| Polling V1 | Stable local demo with minimal transport complexity | WebSocket or SSE | Connection lifecycle does not improve core invariants | Up to 2 seconds of sync latency |
| Optimistic concurrency | Reject stale multi-client writes explicitly | Silent last-write-wins | Can overwrite ownership or repeat confirmation | Clients must handle HTTP 409 and reload |
