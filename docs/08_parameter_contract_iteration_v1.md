# Parameter Contract Iteration V1

## 1. Problem

Stage 14 left one known parameter failure:

```text
boundary-supported-004
expected: navigation_tool.origin, destination, departure_time
predicted: navigation_tool.origin, destination
```

The issue was parameter completeness. Tool arguments should not rely only on
prompt wording. The final boundary must be deterministic validation against each
Tool input schema.

## 2. Stage 14 Baseline

| Dataset | Scenario | Tool Selection | Parameter Accuracy | Parameter Completeness | Unsupported | Schema Valid | Extra Tool |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Main | 1.000 | 1.000 | 1.000 | N/A | 1.000 | 1.000 | 0.000 |
| Challenge | 1.000 | 1.000 | 1.000 | N/A | 1.000 | 1.000 | 0.000 |
| Boundary | 1.000 | 1.000 | 0.933 | N/A | 1.000 | 1.000 | 0.000 |
| Minimality | 1.000 | 1.000 | 1.000 | N/A | N/A | 1.000 | 0.000 |

## 3. Failure Analysis

The Stage 14 failure was not a tool whitelist or over-selection issue. The model
selected `navigation_tool`, but omitted the required `departure_time` argument.

This stage separates two parameter metrics:

- `Parameter Completeness`: expected argument field exists.
- `Parameter Accuracy`: expected argument field exists and has the expected value.

## 4. Existing Tool Schema Audit

`WeatherToolInput`:

| Field | Required | Optional | Default |
| --- | --- | --- | --- |
| `location` | yes | no | none |
| `date` | yes | no | none |

`NavigationToolInput`:

| Field | Required | Optional | Default |
| --- | --- | --- | --- |
| `origin` | yes | no | none |
| `destination` | yes | no | none |
| `departure_time` | yes | no | none |

Both input models now forbid extra argument keys.

## 5. Parameter Contract Design

The chain is:

```text
Tool input schema
-> planner-visible tool specification
-> LLM structured plan
-> deterministic argument validation
-> Task
```

The prompt provides soft guidance. Pydantic Tool input schemas enforce the hard
contract. No missing argument is silently filled by Python.

## 6. Tool Argument Validator

`ToolArgumentValidator.validate(tool_name, arguments)` performs:

```text
tool_name
-> ToolRegistry.get(tool_name)
-> tool.input_schema.model_validate(arguments)
```

It does not call `tool.run()` or `tool.execute()`.

Invalid arguments raise `ToolArgumentValidationError`.

## 7. Planner Schema Exposure

The planner prompt now receives a generated Tool Spec from `ToolRegistry` and
each Tool's `input_schema`:

```text
tool name
purpose / description
required arguments
optional arguments, if any
```

The prompt also states that all required arguments must be provided and that
extra argument keys are invalid.

## 8. Parameter Dataset

`evals/planner_parameters_v1.json` contains 12 supported cases:

| Category | Cases |
| --- | ---: |
| `navigation_required_arguments` | 6 |
| `weather_required_arguments` | 3 |
| `combined_required_arguments` | 3 |

## 9. Metrics

`Parameter Completeness` is:

```text
number of expected parameter fields present in prediction
/
number of expected parameter fields
```

It checks field presence only. `Parameter Accuracy` continues to check presence
and value equality.

When a metric has no applicable denominator, the value is `None` in JSON and
displayed as `N/A`.

## 10. Before Results

Parameters Before:

| Metric | Value |
| --- | ---: |
| Cases | 12 |
| Scenario Accuracy | 1.000 |
| Tool Selection Accuracy | 1.000 |
| Parameter Accuracy | 0.956 |
| Parameter Completeness | 1.000 |
| Unsupported Accuracy | N/A |
| Schema Valid Rate | 1.000 |
| Extra Tool Rate | 0.000 |

Before failures:

- `parameters-navigation-002`: `destination=office`, expected `company`.
- `parameters-combined-002`: `destination=office`, expected `company`.

## 11. After Results

Main After:

| Metric | Value |
| --- | ---: |
| Cases | 22 |
| Scenario Accuracy | 1.000 |
| Tool Selection Accuracy | 1.000 |
| Parameter Accuracy | 0.980 |
| Parameter Completeness | 1.000 |
| Unsupported Accuracy | 1.000 |
| Schema Valid Rate | 1.000 |
| Extra Tool Rate | 0.000 |

Challenge After:

| Metric | Value |
| --- | ---: |
| Cases | 8 |
| Scenario Accuracy | 1.000 |
| Tool Selection Accuracy | 1.000 |
| Parameter Accuracy | 1.000 |
| Parameter Completeness | 1.000 |
| Unsupported Accuracy | 1.000 |
| Schema Valid Rate | 1.000 |
| Extra Tool Rate | 0.000 |

Boundary After:

| Metric | Value |
| --- | ---: |
| Cases | 10 |
| Scenario Accuracy | 0.700 |
| Tool Selection Accuracy | 0.400 |
| Parameter Accuracy | 0.400 |
| Parameter Completeness | 1.000 |
| Unsupported Accuracy | 1.000 |
| Schema Valid Rate | 0.700 |
| Extra Tool Rate | 0.000 |

Minimality After:

| Metric | Value |
| --- | ---: |
| Cases | 12 |
| Scenario Accuracy | 0.917 |
| Tool Selection Accuracy | 0.917 |
| Parameter Accuracy | 0.917 |
| Parameter Completeness | 1.000 |
| Unsupported Accuracy | N/A |
| Schema Valid Rate | 0.917 |
| Extra Tool Rate | 0.000 |

Parameters After:

| Metric | Value |
| --- | ---: |
| Cases | 12 |
| Scenario Accuracy | 1.000 |
| Tool Selection Accuracy | 1.000 |
| Parameter Accuracy | 1.000 |
| Parameter Completeness | 1.000 |
| Unsupported Accuracy | N/A |
| Schema Valid Rate | 1.000 |
| Extra Tool Rate | 0.000 |

## 12. Regression Analysis

### Newly Fixed Cases

- `parameters-navigation-002`
- `parameters-combined-002`

### New Regression Cases

- `commute-006`
- `boundary-supported-002`
- `boundary-supported-005`
- `minimality-navigation-004`

### Remaining Failure Cases

- `commute-006`
- `boundary-supported-002`
- `boundary-supported-004`
- `boundary-supported-005`
- `minimality-navigation-004`

## 13. boundary-supported-004

Stage 15 did not fix `boundary-supported-004`.

Final result:

```text
failure_type: provider_error
error: Unable to parse DeepSeek JSON plan response.
```

No executable Task was created for this case in the final After run.

## 14. Remaining Failures

The final After run shows that parameter completeness is now strong, but the
real model became less stable on Boundary and one Minimality case. The failures
are not caused by Tool execution. They occurred during planning or provider JSON
parsing.

## 15. Conclusion

The hard parameter contract is implemented and verified offline:

- Tool input schemas are the source of truth for required arguments.
- LLMPlanner validates planned Tool arguments before creating a Task.
- Missing required arguments fail explicitly.
- No Python default is silently inserted.
- The new Parameters dataset improved from `0.956` to `1.000` Parameter Accuracy.

Stage 15 should be considered partially successful, not fully accepted. The
parameter contract work is complete, but the real-provider eval introduced
Boundary and Minimality regressions that should be addressed in a later planner
stability iteration.

No RuleBasedPlanner changes, no new Tools, and no Task or Tool execution occurred.
