# 5-minute Interview Pitch

## 1. Product Problem: Device-centered Chatbot

普通助手把每台设备当成独立聊天窗口。用户已在手机上说明会议时间和目的地，上车后还要重新说一遍；上下文、执行状态和确认状态都被困在设备里。FlowMate 因此把核心对象改成 Task：Task 属于用户，Device 只临时拥有当前交互表面。

## 2. Task-centered Cross-device Demo

用户在 Phone Web Client 创建 Morning Commute Task。Task 有固定 `task_id`，包含目标、Calendar observation、Weather/Navigation 结果、风险和确认状态。`car_001` 上线后，Phone 发起 handoff；Car Simulator 展示同一个 Task 和最小化 context，接受后 current device 变为 Car，Phone 自动同步新状态。Handoff 不创建新 Task，因为复制会破坏历史、确认和执行一致性。

## 3. Why a Deterministic Device Router

V1 Router 根据 device online status、device capability 和 task context 做确定性推荐：通勤 Task 有路线 context，在线 Car 具有 NAVIGATION，才推荐 Car。设备归属影响交互与一致性，不能交给 LLM 猜测；确定性规则更容易解释、测试和审计。Router 只推荐，HandoffService 才能真正转移。

## 4. Why Handoff and Versioning

Handoff 有 PENDING、ACCEPTED、REJECTED、CANCELLED 状态。创建时 Task 仍属于 Phone，Car 明确接受后才原子更新。每次协调写入带 `expected_version`；过期写入返回 409，而不是 last-write-wins。两个端同时确认时只有一个 version claim 能赢，避免重复确认和重复副作用。

## 5. Why Polling in V1

Phone 和 Car 每 2 秒只轮询 coordination state，heartbeat 每 4 秒更新 presence。Portfolio V1 的目标是证明 Task、路由、handoff 和一致性 invariant，轮询更简单、稳定、可离线验证。SSE/WebSocket 只是可替换 transport，不值得在 V1 扩大范围。

## 6. Dynamic Agent Foundation

Calendar 工具先返回会议地点等结构化 observation，系统再生成 Weather 和 Navigation continuation。这让 Morning Commute 不是一次性猜完整计划，而是 Plan → Act → Observe → Re-plan。跨端接管只复用这些结果，不重跑 Planner 或 Calendar。

## 7. Safety / HITL

安全不靠 prompt。Capability Authorization、ToolArgumentValidator、RiskPolicy 和 TaskConfirmationService 都在后端。MEDIUM/HIGH side effect 必须确认；跨端接力无法绕过 gate。Car 显示的 `VEHICLE_STATUS` 只是 Mock capability，不是真实车辆控制。

## 8. Proactive + Persistence

SQLite 保存 Task、Trigger、Device、TaskDeviceState 和 Handoff。Proactive Trigger 使用显式 tick，不引入隐藏 scheduler；重复注册、重复 fire、重启幂等和 side-effect containment 由 Trigger Eval 验证。

## 9. Three-layer Evaluation

Planner Eval V3 的真实 saved result 是 36 cases：Scenario Accuracy 0.9722、Tool Selection 0.9583、Parameter Accuracy 0.9375、Extra Tool Rate 0.000。Trigger Eval V1 有 12 cases，八项指标均为 1.000。Cross-device Eval V1 有 16 cases，十一项路由、一致性和持久化指标均为 1.000。

## 10. Real-world Grounding

Amap 曾把“人民广场”解析到错误省份，产生约 1900km 的有效但不可用路线。通过 origin geographic context、POI region constraint、city limit 和 defensive validation 修正。这说明 schema valid 和 HTTP 200 都不等于产品语义正确。

## 11. Why No Real Car

本项目要证明的是跨设备 Task continuity 和安全协调，不是 OEM 集成。真实车控涉及硬件、车厂权限、认证、法规和安全责任，会掩盖核心产品假设。Phone 是 Web Client，Car 是 Web Simulator；无原生 App、生产认证、真实车辆或真实智能家居。Feishu engineering PASS，但真实发送仍 PENDING。
