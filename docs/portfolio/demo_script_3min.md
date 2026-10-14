# 3-minute Demo Script

## 0:00–0:25 Product Problem

“FlowMate 想解决的核心问题，是 AI 助手在不同设备之间的上下文割裂。用户已经在手机上告诉 AI 明早去哪、什么时候开会，上车之后不应该再和车机重新说一遍。因此我把 Agent 的核心从‘设备上的聊天窗口’改成了‘可以跨设备流转的 Task’。”

明确边界：Phone 是 Web Client，Car 是 Web Simulator，不代表真实车机接入。

## 0:25–1:00 Phone Creates Morning Commute

在 `/phone` 创建“明早 8:30 公司开会，帮我安排好出门”。展示同一 Task 的 `task_id`、`current_device=phone_001` 和 Agent Trace：Calendar observation → Weather → Navigation。说明这条链是跨设备接力的执行基础。

## 1:00–1:40 Device Router + Handoff

保持 `/car` 在第二个浏览器窗口在线。回到 Phone，展示 Router 因 `ONLINE + NAVIGATION capability + commute context` 确定性推荐 `car_001`，然后点击 Handoff。强调 Router 只推荐，不静默转移；此时状态是 `PENDING`，Task 仍属于 Phone。

## 1:40–2:00 Car Takes Over

切到 Car：核对与 Phone 相同的 `task_id`、来源 `phone_001`、会议、目的地和路线摘要。点击 Accept，展示 `ACCEPTED`、version 递增以及 `current_device=car_001`。Planner、Calendar 和路线查询都没有重跑。

## 2:00–2:20 Phone Synchronizes

返回 Phone，等待下一次 2 秒轮询，展示 current owner、version 和 timeline 自动更新。这完成 Phone → Car → Phone view update。

## 2:20–2:40 Risk / HITL

打开 MEDIUM notification，展示 RiskPolicy、PENDING confirmation 和 Confirm/Reject。强调跨端接力不能绕过后端 HITL；相同 version 的并发确认只有一个请求能成功。

## 2:40–3:00 Evaluation + Grounding + Real Provider

展示三层质量体系：Planner Eval、Trigger Eval、Cross-device Eval。补充 Amap “人民广场”曾解析到错误省份、产生约 1900km 路线，后来通过 origin context、region constraint 和 defensive validation 修正。Calendar、Weather、Navigation 的真实信息 adapter 已验证；Feishu engineering PASS，但真实发送仍 PENDING。
