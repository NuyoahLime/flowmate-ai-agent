# Release Checklist

| Gate | Status |
| --- | --- |
| pytest PASS | PASS |
| frontend build PASS | PASS |
| frontend dist secret scan PASS | PASS |
| repo secret scan PASS | PASS |
| README links PASS | PASS |
| Demo Mode PASS | PASS |
| Morning Commute PASS | PASS |
| MEDIUM HITL Confirm PASS | PASS |
| Reject PASS | PASS |
| Vehicle HIGH Risk PASS | PASS |
| Proactive Trigger PASS | PASS |
| Persistence Refresh PASS | PASS |
| Eval UI PASS | PASS |
| Status Accuracy PASS | PASS |
| Phone Client | PASS |
| Car Simulator Client | PASS |
| Same task_id across clients | PASS |
| Device Router recommendation | PASS |
| Handoff PENDING | PASS |
| Handoff ACCEPTED | PASS |
| Phone state sync after Car accept | PASS |
| Version conflict / HTTP 409 | PASS |
| Wrong-user isolation | PASS |
| Confirmation consistency | PASS |
| Cross-device Eval V1, 16 cases | PASS |
| Eight real runtime screenshots | PASS |

## Known Maintenance Item

`npm audit` reports known vulnerabilities in the old Vite/Rollup chain kept for current Node 12 local compatibility. Do not run `npm audit fix --force` as part of Portfolio V1 because it would force dependency modernization outside the release-pass scope.

`LICENSE` is currently missing. This release pass records the issue but does not choose a license on the owner's behalf.
