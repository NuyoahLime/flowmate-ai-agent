# Resume Bullets

## AI 产品经理版

- 面向手机与车辆场景中的 AI 上下文割裂问题，设计 Task-centered 跨设备 Agent，使 Phone Web 创建的同一 Task 可携带会议、目的地与执行状态接力至 Car Simulator，避免用户跨端重复表达需求。
- 建立 Device Identity、Capability Registry、确定性 Device Router 与 Handoff 状态机，通过共享 Task、version/expected_version 和轮询同步实现 Phone → Car → Phone view continuity，并处理离线、能力不匹配、重复接管及 409 并发冲突。
- 设计 Observation-driven Dynamic Re-planning 与 LOW/MEDIUM/HIGH RiskPolicy + HITL，使跨端接管仍遵循统一安全边界，防止多端重复确认及 Side Effect 重复执行。
- 建立 Planner、Proactive Trigger、Cross-device 三层 Eval，并接入 Google Calendar、Open-Meteo、高德地图真实信息 Provider；通过 Bad Case 定位并解决同名 POI 导致约 1900km 错误路线的 Grounding 问题。

## AI Agent / AI 应用开发版

- 实现统一 Planner contract，将 RuleBasedPlanner 与 LLMPlanner 输出转换为 Pydantic Task/PlanStep/ToolCall，并通过 schema 与工具白名单硬化执行边界。
- 构建 ToolRegistry、ToolExecutor、StepExecutor、TaskExecutor 分层执行链，实现单步、任务、多步骤、HITL 与 fail-fast 状态流。
- 设计 observation-driven dynamic runtime，基于 Calendar observation 继续生成 Weather/Navigation/Notification 计划，并保留结构化执行 trace。
- 实现 SQLite Task/Trigger persistence、显式 Trigger tick、重复触发防护与前端 Demo API，用 Vue workspace 展示 Agent trace、history、eval 与 confirmation。
- 实现 Device Registry、确定性 Device Router、事务型 HandoffService、乐观并发与 2 秒轮询同步；16-case 跨端评测 11 项指标均为 1.000，并保留“Web 模拟器、非真实车机”的能力边界。
