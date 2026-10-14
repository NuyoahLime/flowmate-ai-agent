# Capability Boundary Iteration V1

## Before

修改前使用阶段 12.1 的 Prompt 和同一 Provider/模型。

### Main Dataset

```text
Cases: 22
Scenario Accuracy: 0.955
Tool Selection Accuracy: 1.000
Parameter Accuracy: 1.000
Unsupported Accuracy: 0.917
Schema Valid Rate: 1.000
```

已知失败：

```text
帮我把车开到公司门口
```

模型错误生成了 `weather_tool` 和 `navigation_tool`。

### Challenge Set

```text
Cases: 8
Scenario Accuracy: 1.000
Tool Selection Accuracy: 1.000
Parameter Accuracy: 1.000
Unsupported Accuracy: 1.000
Schema Valid Rate: 1.000
```

Before 结果文件：

```text
evals/results/llm_planner_challenge_before_v1.json
```

## Change

只修改了 `LLM_PLANNER_PROMPT` 的能力边界描述：

- 明确 `weather_tool` 只能查询天气，不能控制环境或发送提醒。
- 明确 `navigation_tool` 只能提供路线、距离、时间和导航规划信息。
- 明确 `navigation_tool` 不能驾驶、移动车辆、启动汽车或控制车门/车窗/空调。
- 增加核心规则：工具与请求主题相关，不代表工具有能力完成请求。
- 明确车辆控制、家居控制、日历和通知请求必须返回 unsupported。

没有修改 RuleBasedPlanner、Tool 白名单、Pydantic 校验或执行链。

## After

### Main Dataset

```text
Cases: 22
Scenario Accuracy: 1.000
Tool Selection Accuracy: 1.000
Parameter Accuracy: 1.000
Unsupported Accuracy: 1.000
Schema Valid Rate: 1.000
```

结果文件：

```text
evals/results/llm_planner_v1_after_boundary.json
```

### Challenge Set

```text
Cases: 8
Scenario Accuracy: 1.000
Tool Selection Accuracy: 1.000
Parameter Accuracy: 1.000
Unsupported Accuracy: 1.000
Schema Valid Rate: 1.000
```

结果文件：

```text
evals/results/llm_planner_challenge_after_v1.json
```

### Boundary Set

文件：

```text
evals/planner_boundary_v1.json
```

共 10 条：

- 5 条车辆相关的信息/路线规划 Supported Case
- 5 条车辆真实控制 Unsupported Case

结果：

```text
Cases: 10
Scenario Accuracy: 1.000
Tool Selection Accuracy: 0.600
Parameter Accuracy: 1.000
Unsupported Accuracy: 1.000
Schema Valid Rate: 1.000
```

结果文件：

```text
evals/results/llm_planner_boundary_v1.json
```

## Regression

没有发现旧 Case 从正确变为错误：

```text
Main Dataset: 0.955 -> 1.000
Challenge Set: 1.000 -> 1.000
```

## Remaining Failures

Boundary Set 有 2 个 Tool Selection 失败：

```text
boundary-supported-001
```

用户只要求规划明早开车路线，模型额外生成了 `weather_tool`。

```text
boundary-supported-005
```

用户只要求估算通勤时间，模型额外生成了 `weather_tool`。

这两个 Case 的场景判断、参数和 Schema 均正确，失败仅是 Gold 要求的 Tool 集合 Exact Match 不一致。

## Dataset Audit

主 Dataset 的 10 条 supported Morning Commute Case：

```text
supported Cases 总数: 10
直接命中显式组合: 10
仅因单个“通勤”命中: 0
不含规则关键词但语义属于 Morning Commute: 0
keyword_coverage_rate: 1.000
```

主 Dataset 对 RuleBasedPlanner 的覆盖仍然偏高；Challenge Set 才暴露了规则系统的召回和误判边界。

## Current Limitations

- Boundary Set 的 Tool Selection 仍有 2 个额外天气工具调用。
- 当前指标使用 Tool 集合 Exact Match，无法表达“额外步骤是否合理”的软评分。
- 本阶段只优化 LLMPlanner 能力边界，没有修改 RuleBasedPlanner。
- 所有 Eval 仍然只运行 Planner，不执行 Task 或 Tool。
