# Tool Minimality Iteration V1

## 1. Problem

Stage 13 exposed tool over-selection at the capability boundary. For two supported
vehicle-information cases, the user requested route or commute-time information,
but the LLM planner added `weather_tool` even though weather was not requested.

The goal of this stage was to reduce unnecessary tool calls while preserving the
existing capability boundary and planner validation rules.

## 2. Stage 13 Baseline

The Stage 13 boundary result was:

| Metric | Value |
| --- | ---: |
| Scenario Accuracy | 1.000 |
| Tool Selection Accuracy | 0.600 |
| Parameter Accuracy | 1.000 |
| Unsupported Accuracy | 1.000 |
| Schema Valid Rate | 1.000 |
| Extra Tool Rate | 0.400 |

The two boundary failures were `boundary-supported-001` and
`boundary-supported-005`. Both predicted `weather_tool` plus
`navigation_tool`, while the gold set required only `navigation_tool`.

## 3. Failure Analysis

The failures were tool-selection errors, not capability-boundary, schema, or
parameter errors. The model treated weather as potentially useful context for
commuting, rather than distinguishing it from the user's explicit route or
commute-time goal.

## 4. Prompt Change

Only `LLM_PLANNER_PROMPT` was changed. It now states:

- Include a tool only when its output is necessary for an explicit or directly
  implied user goal.
- Optional contextual tools must not be added merely because they might help.
- Use the smallest sufficient set of tools.

No RuleBasedPlanner, Tool, executor, whitelist, or provider was changed.

## 5. Minimality Dataset

`evals/planner_minimality_v1.json` contains 12 supported cases:

| Category | Cases |
| --- | ---: |
| `navigation_only` | 4 |
| `weather_only` | 4 |
| `weather_and_navigation` | 4 |

The dataset tests whether the planner selects only the tools required by the
request and does not add the other available tool as optional context.

## 6. Metrics

- **Scenario Accuracy**: correct supported/unsupported classification over all cases.
- **Tool Selection Accuracy**: exact match between predicted and expected tool sets
  for supported cases.
- **Parameter Accuracy**: average per-case fraction of expected argument fields
  with the expected values.
- **Unsupported Accuracy**: correct rejection rate among unsupported cases.
  When there are no unsupported cases, the metric is not applicable and is stored
  as `null`, displayed as `N/A`.
- **Schema Valid Rate**: proportion of results that pass the planner/task schema
  boundary.
- **Extra Tool Rate**: supported cases containing at least one predicted tool not
  present in the gold tool set, divided by supported case count.

## 7. Main Dataset Results

Real provider results from 22 calls:

| Metric | RuleBasedPlanner | LLMPlanner |
| --- | ---: | ---: |
| Scenario Accuracy | 1.000 | 1.000 |
| Tool Selection Accuracy | 1.000 | 1.000 |
| Parameter Accuracy | 1.000 | 1.000 |
| Unsupported Accuracy | 1.000 | 1.000 |
| Schema Valid Rate | 1.000 | 1.000 |
| Extra Tool Rate | N/A | 0.000 |

Source: `evals/results/llm_planner_v1_after_minimality.json`.

## 8. Challenge Results

The 8-case challenge set retained its baseline results:

| Metric | RuleBasedPlanner | LLMPlanner |
| --- | ---: | ---: |
| Scenario Accuracy | 1.000 | 1.000 |
| Tool Selection Accuracy | 1.000 | 1.000 |
| Parameter Accuracy | 1.000 | 1.000 |
| Unsupported Accuracy | 1.000 | 1.000 |
| Schema Valid Rate | 1.000 | 1.000 |
| Extra Tool Rate | 0.000 | 0.000 |

Source: `evals/results/llm_planner_challenge_after_minimality_v1.json`.

## 9. Boundary Results

After the prompt change:

| Metric | Stage 13 | Stage 14 |
| --- | ---: | ---: |
| Scenario Accuracy | 1.000 | 1.000 |
| Tool Selection Accuracy | 0.600 | 1.000 |
| Parameter Accuracy | 1.000 | 0.933 |
| Unsupported Accuracy | 1.000 | 1.000 |
| Schema Valid Rate | 1.000 | 1.000 |
| Extra Tool Rate | 0.400 | 0.000 |

`boundary-supported-001` and `boundary-supported-005` are fixed: both now
select only `navigation_tool`.

## 10. Minimality Results

The 12-case minimality set produced:

| Metric | LLMPlanner |
| --- | ---: |
| Scenario Accuracy | 1.000 |
| Tool Selection Accuracy | 1.000 |
| Parameter Accuracy | 1.000 |
| Unsupported Accuracy | N/A |
| Schema Valid Rate | 1.000 |
| Extra Tool Rate | 0.000 |

There are no unsupported cases in this dataset, so Unsupported Accuracy is
not a performance score for this run.

## 11. Before / After

The targeted boundary change reduced case-level extra-tool errors from 2/5
supported cases to 0/5. Main and Challenge results did not regress.

The complete real-provider run used 60 planner calls:

- 8 Stage 13 challenge-before calls
- 22 main after-minimality calls
- 8 challenge after-minimality calls
- 10 boundary after-minimality calls
- 12 minimality calls

Each case was called once. There was no retry, self-consistency, Task execution,
or Tool execution.

## 12. Regression Analysis

### Newly Fixed Cases

- `boundary-supported-001`: removed unnecessary `weather_tool`.
- `boundary-supported-005`: removed unnecessary `weather_tool`.

### New Regression Cases

- `boundary-supported-004`: still selected `navigation_tool`, but omitted the
  expected `departure_time` argument. Its parameter accuracy is `2/3`.

This is a parameter-completeness regression, not a tool-minimality regression.

### Remaining Failure Cases

- `boundary-supported-004`: missing `navigation_tool.departure_time`.

## 13. Remaining Failures

The remaining issue should be tracked for a later iteration as an argument
completeness problem. It is intentionally not fixed in Stage 14 because this
stage permits only one minimality-focused prompt iteration.

## 14. Conclusion

The core Tool Minimality objective was achieved: Boundary Tool Selection Accuracy
reached `1.000` and Extra Tool Rate reached `0.000`. The Main, Challenge, and
Minimality results show no observed regression. Stage 14 is therefore
substantially successful, with one documented parameter regression remaining for
future evaluation.

No new Tool was added, RuleBasedPlanner was not modified, and no Task or Tool
was executed.
