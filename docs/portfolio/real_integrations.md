# Real Integrations

FlowMate distinguishes current demo runtime from real integration verification.

| Capability | Authentication | Provider boundary | Real smoke status | What remains |
| --- | --- | --- | --- | --- |
| Google Calendar | OAuth desktop flow | Read-only Calendar provider | PASS | No calendar write support |
| Open-Meteo | No API key | Weather provider | PASS | No paid weather SLA |
| Amap | `AMAP_WEB_SERVICE_KEY` | Navigation + POI grounding provider | PASS | Provider data can vary by city and traffic |
| Feishu | `FEISHU_BOT_WEBHOOK_URL` | Notification provider | ENGINEERING READY | Final real delivery verification pending |

## Status Accuracy

Feishu engineering is implemented, but final real message delivery remains pending. The project must not claim `FULLY_VERIFIED` until a real Feishu send is confirmed.

## Mock Runtime

Demo Mode uses Mock Calendar, Mock Weather, Mock Navigation and Mock Notification. This keeps the portfolio demo repeatable, offline-capable and safe from real side effects while using the same Tool contracts.
