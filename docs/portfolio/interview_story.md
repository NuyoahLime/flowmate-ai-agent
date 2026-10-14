# Interview Story

## 1. Reactive Agent

最初的问题是把自然语言可靠地变成可执行任务，而不是做一个只生成文本的聊天机器人。FlowMate 建立 Task、PlanStep、ToolCall、Planner contract 和分层 Executor；LLM 只提出结构化计划，schema、白名单和系统状态由后端控制。

## 2. Dynamic Agent

静态计划不能利用运行时信息。Morning Commute 先执行 Calendar，得到会议地点 observation，再继续生成 Weather 和 Navigation steps，形成 Plan → Act → Observe → Re-plan。真实 Amap bad case 进一步证明 grounding 不能只看 HTTP 成功或 schema valid。

## 3. Safe Agent

当 Agent 能触发通知、智能家居和车辆动作时，prompt 不能充当安全边界。FlowMate 加入确定性 RiskPolicy、Capability Authorization、ToolArgumentValidator 和 HITL；确认前没有 side effect，拒绝后不会执行。

## 4. Proactive Agent

系统不能永远等用户提问，但主动也不能等于失控。持久化 Trigger 通过显式 tick 检测 due event，防止重复注册和重复 fire，并继续复用现有 Task runtime 与安全 gate。

## 5. Cross-device Task Agent

最后一个问题是 Task 仍被困在单个设备。Stage 29 加入 User/Device identity、Capability Registry、确定性 Device Router、Handoff、Task version 和 polling sync。Phone 创建的同一个 Task 携带 context 接力到 Car Simulator，Car 接受后 Phone 自动看到新 owner；并发确认使用 version conflict 保证一致性。

最终 FlowMate 从 Reactive Agent 演进为 Task-centered Cross-device Agent。它证明两个独立 Web client 的共享 Task 连续性，但不声称真实车机、原生 App、生产认证或真实设备控制。
