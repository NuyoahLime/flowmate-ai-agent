# Interview FAQ

## Product

1. Why build FlowMate?  
FlowMate validates how an assistant moves from passive answers to controlled proactive task collaboration.

2. What is the core scenario?  
Morning commute: calendar observation, weather, route, notification proposal and confirmation.

3. Why not focus on many scenarios equally?  
A portfolio demo needs one clear end-to-end story, with SmartHome and Vehicle as safety examples.

4. What problem does it solve for users?  
It reduces coordination work across calendar, weather, routes and reminders while keeping control visible.

5. What is not included?  
Production auth, multi-user, real vehicle/smart-home control, distributed scheduling, RAG and memory.

## Agent Architecture

6. Why not use LangGraph?  
The project first proves explicit planner/runtime boundaries. A graph framework can be added later when the state model demands it.

7. Why not use RAG?  
FlowMate is not knowledge retrieval; it is capability planning and controlled tool execution.

8. Why keep Rule Planner and LLM Planner?  
The rule planner is a deterministic baseline for comparison. The LLM planner handles broader natural language.

9. What is the Planner contract?  
`plan(user_input: str) -> Task`.

10. Why does LLM not generate full Task internals?  
IDs, statuses, confirmation status, results and errors are deterministic system state, not model output.

## Planner

11. How do you handle unsupported requests?  
The planner raises a clear unsupported error instead of inventing tools or mapping to wrong tools.

12. How do you prevent fake tools?  
Tool whitelist and capability authorization check planned tool names and actions.

13. How do you handle tool over-selection?  
Prompt constraints, whitelist validation and Extra Tool Rate evaluation.

14. Why structured output?  
It makes model output machine-validated before Task construction.

15. Can schema valid still be wrong?  
Yes. The 1919.6 km POI case showed schema validity does not prove real-world grounding.

## Tool Calling

16. Why Mock and Real share one Tool contract?  
It lets tests and offline demos use the same planner and executor path as real providers.

17. Why not let frontend call tools?  
Frontend is a renderer. Backend owns tool execution, risk and persistence.

18. How are arguments validated?  
ToolArgumentValidator and Pydantic schemas validate arguments before execution.

19. What happens on Tool failure?  
ToolCall and owning Step/Task move to failed state according to executor rules.

20. Why no retry everywhere?  
Retry is limited to provider instability; business or planning errors should be surfaced.

## Dynamic Planning

21. What is observation-driven planning?  
The system executes a first tool, records structured observation, then creates continuation steps from that observation.

22. Retry and re-plan difference?  
Retry repeats the same provider call; re-plan changes the task based on new information.

23. Why is Calendar first in commute?  
The calendar event provides destination and timing context.

24. How is re-plan shown?  
Frontend timeline renders Calendar observation and Dynamic Re-plan before weather and route.

25. Why persist dynamic state?  
For auditability and browser refresh persistence.

## Safety

26. Why not trust LLM risk level?  
Risk affects side effects, so it must be deterministic backend logic.

27. Why does Notification need confirmation?  
It is a user-visible side effect and may disclose information.

28. Why not real Vehicle?  
Real vehicle control is high-risk and outside Portfolio V1 safety scope.

29. How do you avoid autonomous side effects?  
HITL, explicit tick and backend confirmation state.

30. Why put HITL in backend?  
Client state can be manipulated; backend state machine is the enforcement point.

## Evaluation

31. How do you evaluate Agent quality?  
Offline tests, planner evals, trigger evals, provider smoke tests, frontend build and secret audits.

32. Why split Parameter Accuracy and Completeness?  
Wrong values and missing values are different product failures.

33. Why classify provider errors?  
Provider outage should not be counted as planner reasoning failure.

34. Why version eval datasets?  
Versioning keeps regression and improvement history honest.

35. What is Unsupported Recall?  
The rate at which unsupported user requests are correctly rejected.

## Persistence / Proactive / Frontend

36. SQLite vs PostgreSQL?  
SQLite is enough for local portfolio auditability; distributed production storage is outside V1.

37. Why not APScheduler?  
Explicit tick keeps proactive behavior deterministic and avoids hidden side effects.

38. Persistence vs Memory?  
Persistence stores task history and trigger state; it is not personalized long-term memory.

39. What does frontend prove?  
It shows trace, HITL, history, evals and provider status without exposing secrets or raw provider payloads.

40. What would be next after Portfolio V1?  
Feishu final verification, GitHub release, resume integration and interview rehearsal.

## Cross-device Task Continuity

41. 为什么这是跨设备 Agent，而不是两个网页？  
两个独立网页只是 client surface；跨设备能力来自共享持久化 Task、显式 Device identity/capability、Router、Handoff 状态机、version conflict、restart persistence 和 Phone 自动同步。两端共享同一个 `task_id`，不是各自创建任务。

42. 为什么不让 LLM 决定路由到哪台设备？  
路由影响状态归属和交互一致性。V1 用在线状态、capability 和 Task context 的确定性规则，保证可解释、可测试、可审计。

43. Task 和 Device 的关系是什么？  
Task 属于用户并持有上下文；Device 只是暂时拥有当前执行/展示表面。

44. 为什么 handoff 不创建新 Task？  
新 Task 会拆分历史、context、风险、确认与执行状态，无法证明 continuity。

45. 为什么需要 version？  
多个客户端可能基于旧状态写入。`expected_version` 让后端检测 stale write，并以 409 拒绝而非静默覆盖。

46. 两个设备同时确认怎么办？  
确认状态和 version 在同一事务中 claim。只有一个请求成功，另一个收到 409，因此不会产生第二次副作用。

47. Car offline 怎么办？  
心跳超过 10 秒视为 OFFLINE。Router 不推荐，HandoffService 也拒绝创建。

48. 为什么 V1 用 polling？  
2 秒 coordination-only polling 足以证明 Task continuity 和一致性，简单、稳定、适合离线作品集演示。

49. 为什么不用 WebSocket？  
WebSocket 会扩大连接管理和重连范围，却不改变核心 Task/Handoff invariant。未来可以替换 transport，但不属于 V1。

50. 为什么不接真实车机？  
真实 OEM 车机涉及硬件权限、认证、法规和安全责任。V1 验证跨设备产品逻辑，不声称硬件集成。

51. Phone Web + Car Simulator 能证明什么？  
它证明两个独立 client 的 device identity、capability routing、same-Task context handoff、state sync、restart persistence 和 confirmation consistency。

52. 这和普通多端同步有什么区别？  
普通同步通常复制内容；FlowMate 还建模“哪台设备当前更适合承载 Task”、明确 PENDING/ACCEPTED handoff，并保持 Agent risk/confirmation invariant。
