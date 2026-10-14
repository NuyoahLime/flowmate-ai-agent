# 90-second Interview Pitch

FlowMate 想解决的是 AI 助手在不同设备之间的上下文割裂。用户已经在手机上说过明早什么时候开会、要去哪里，上车后不应该再向另一个聊天窗口重复一遍。因此我把产品核心设计成 Task-centered Agent：Task 属于用户，设备只是临时承载执行和展示的表面。

主 Demo 中，用户在 Phone Web Client 创建 Morning Commute Task。系统先通过 Calendar observation 得到会议信息，再继续规划 Weather 和 Navigation。`car_001` 上线后，确定性 Device Router 根据在线状态、NAVIGATION capability 和 Task context 推荐 Car；Phone 发起 handoff，Car Simulator 收到相同 `task_id` 和最小化 context，接受后 current device 与 version 原子更新，Phone 在下一次轮询自动看到接管结果。

跨端不会放大 Agent 风险。LLM 只提出计划，Tool schema、Capability Authorization 和 RiskPolicy 都由后端确定性执行；MEDIUM/HIGH side effect 必须 HITL。同一 Task 在两个客户端同时确认时，expected version 和 409 conflict 保证只有一个状态转换和一次副作用。

质量上我分三层：Planner Eval 衡量规划，Trigger Eval 衡量主动行为，16-case Cross-device Eval 衡量路由、隔离、持久化和一致性。真实信息 adapter 覆盖 Google Calendar、Open-Meteo 和 Amap；默认 Demo 全离线。Car 是 Web Simulator，项目不声称真实车机、原生 App 或生产认证。
