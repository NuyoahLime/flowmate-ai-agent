# Planner Eval V1

## Dataset

主 Dataset：`evals/planner_eval_v1.json`

共 22 条：

- 10 条 `morning_commute`
- 4 条 `unsupported_smart_home`
- 3 条 `unsupported_vehicle`
- 3 条 `unsupported_calendar`
- 2 条 `unsupported_notification`

每条 Case 包含：

- `id`
- `category`
- `user_input`
- `supported`
- `expected_tools`
- `expected_arguments`

## Metrics

- Scenario Accuracy：正确判断 supported / unsupported 的比例。
- Tool Selection Accuracy：supported Case 的 Tool 集合 Exact Match 比例。
- Parameter Accuracy：Gold 参数字段中正确字段的比例。
- Unsupported Accuracy：unsupported Case 的正确拒绝比例。
- Schema Valid Rate：返回合法 Task 或明确 Unsupported 结果的比例。

## RuleBasedPlanner Results

运行命令：

```powershell
python scripts\eval_rule_planner.py
```

结果文件：`evals/results/rule_planner_v1.json`

```text
Cases: 22
Scenario Accuracy: 1.000
Tool Selection Accuracy: 1.000
Parameter Accuracy: 1.000
Unsupported Accuracy: 1.000
Schema Valid Rate: 1.000
```

## Real LLMPlanner Results

运行命令：

```powershell
python scripts\eval_llm_planner.py
```

本次使用真实 Provider 完整运行 22 条，每条 Case 调用一次 Planner，没有执行任何 Task 或 Tool。

```text
Cases: 22
Scenario Accuracy: 0.955
Tool Selection Accuracy: 1.000
Parameter Accuracy: 1.000
Unsupported Accuracy: 0.917
Schema Valid Rate: 1.000
```

结果文件：`evals/results/llm_planner_v1.json`

## Rule vs LLM Comparison

| Metric | RuleBasedPlanner | LLMPlanner |
|---|---:|---:|
| Scenario Accuracy | 1.000 | 0.955 |
| Tool Selection Accuracy | 1.000 | 1.000 |
| Parameter Accuracy | 1.000 | 1.000 |
| Unsupported Accuracy | 1.000 | 0.917 |
| Schema Valid Rate | 1.000 | 1.000 |

## LLM Failure Analysis

本次只有 1 个失败 Case：

```text
case_id: unsupported-vehicle-001
category: unsupported_vehicle
user_input: 帮我把车开到公司门口
expected_supported: false
predicted_supported: true
expected_tools: []
predicted_tools: [weather_tool, navigation_tool]
expected_arguments: {}
predicted_arguments:
  weather_tool:
    location: current_city
    date: tomorrow
  navigation_tool:
    origin: home
    destination: company
    departure_time: tomorrow morning
error: null
failure_type: scenario_error
```

模型把“车辆控制”误判为普通通勤导航。程序侧 Tool 白名单没有失效，因为生成的 Tool 仍然是白名单内工具；失败发生在场景判断层。

## Dataset Audit

针对主 Dataset 的 10 条 supported Morning Commute Case：

```text
supported Cases 总数: 10
直接命中显式组合: 10
仅因单个“通勤”命中: 0
不含规则关键词但语义属于 Morning Commute: 0
keyword_coverage_rate: 1.000
```

显式组合包括：

```text
("公司", "开会")
("公司", "出门")
("上班", "通勤")
("上班", "出门")
```

结论：主 Dataset 对 RuleBasedPlanner 的关键词覆盖完整，尚不足以单独衡量规则系统在未见表达上的泛化能力。

## RuleBasedPlanner Challenge Set

Challenge Dataset：`evals/planner_challenge_v1.json`

共 8 条：

- 4 条 `morning_commute_paraphrase`
- 4 条 `unsupported_hard_negative`

运行命令：

```powershell
python scripts\eval_rule_challenge.py
```

结果：

```text
Challenge Cases: 8
Challenge Scenario Accuracy: 0.125
Challenge Tool Selection Accuracy: 0.000
Challenge Unsupported Accuracy: 0.250
```

失败案例：

```text
challenge-supported-001: 语义是通勤，但未命中现有关键词
challenge-supported-002: 语义是通勤，但未命中现有关键词
challenge-supported-003: 语义是通勤，但未命中现有关键词
challenge-supported-004: 语义是通勤，但未命中现有关键词
challenge-hard-negative-002: “通勤”仅用于解释，不应生成 Task
challenge-hard-negative-003: 讨论公司的通勤制度，不是出行规划
challenge-hard-negative-004: 用户已经到公司，不需要安排出门
```

详细结果：`evals/results/rule_planner_challenge_v1.json`

## Current Limitations

- RuleBasedPlanner 在主 Dataset 上表现良好，但 Challenge Set 暴露出关键词误判和召回不足。
- LLMPlanner 主 Dataset 上出现 1 个 unsupported 场景误判。
- 当前评测只比较 Planner 输出，不执行 Task 或 Tool。
- 尚未运行真实 LLM Challenge Set。

本阶段不根据评测结果修改 Planner、Prompt 或 Tool。
