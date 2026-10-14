# Bounded Provider Retry V1

## 1. Problem

Stage 15.1 and 15.2 observed transient provider/infrastructure failures such as
`provider_empty_output`. Semantic failures must not be retried, but provider
failures can reasonably receive one bounded retry.

## 2. Evidence for Retry

Historical provider failures:

- `minimality-navigation-004`: `provider_empty_output`
- `commute-008`: `provider_empty_output`

These failures occurred before any Tool execution and before semantic task
execution. They are provider response reliability issues.

## 3. Retryable vs Non-retryable Failures

Retryable whitelist:

- `provider_transport_error`
- `provider_empty_output`
- `provider_invalid_json`
- `provider_parse_error`

Non-retryable:

- `llm_schema_error`
- `tool_argument_validation_error`
- `scenario_error`
- `tool_selection_error`
- `parameter_value_error`
- `parameter_completeness_error`
- `UnsupportedPlanningScenarioError`

## 4. Architecture

Retry is implemented as an LLM client wrapper:

```text
LLMPlanner
-> LLMClient Protocol
-> RetryingLLMClient
-> OpenAILLMClient
-> Provider
```

The Planner contract remains:

```text
plan(user_input: str) -> Task
```

No retry logic was added to `PlannerEvaluator`, `ToolExecutor`, `StepExecutor`,
or `TaskExecutor`.

## 5. Retry Policy

`RetryPolicy.is_retryable(error)` checks structured `LLMProviderError.error_type`.
It does not rely on substring matching.

V1 configuration:

```text
max_attempts = 2
retry_delay_seconds = 0
```

This means one initial provider request plus at most one retry.

## 6. Observability

`RetryingLLMClient` exposes `last_call_metadata`:

- `attempt_count`
- `retry_performed`
- `first_provider_error_type`
- `final_provider_error_type`

`PlannerEvalResult` records:

- `attempt_count`
- `retry_performed`
- `first_provider_error_type`
- `final_provider_error_type`

`PlannerEvalMetrics` records:

- `retry_cases`
- `retry_recovery_rate`
- `total_provider_attempts`
- `average_provider_attempts_per_case`

## 7. Offline Tests

Offline tests cover:

- first attempt success
- retry recovery for all retryable provider error types
- retry exhaustion after the second attempt
- no third provider call
- no retry for LLM schema error
- no retry for semantic unsupported
- no retry for Tool argument validation error
- retry metadata in Eval result
- retry recovery rate
- N/A retry recovery rate when no retry occurs
- API key not included in retry error output
- existing provider attribution tests continue passing

Full result:

```text
178 passed
```

## 8. Targeted Real Retry Validation

Targeted cases:

- `commute-008`
- `minimality-navigation-004`

Result:

| Case | Final Status | Attempt Count | Retry Performed |
| --- | --- | ---: | --- |
| `commute-008` | `no_retry_needed` | 1 | false |
| `minimality-navigation-004` | `no_retry_needed` | 1 | false |

Both historical provider failures succeeded on the first attempt in this run.
That confirms nondeterminism, but does not count as retry recovery.

## 9. Main Dataset Retry Eval

Main Dataset with bounded provider retry:

| Metric | Value |
| --- | ---: |
| Cases | 22 |
| Scenario Accuracy | 1.000 |
| Supported Recall | 1.000 |
| Unsupported Recall | 1.000 |
| Tool Selection Accuracy | 1.000 |
| Parameter Accuracy | 1.000 |
| Parameter Completeness | 1.000 |
| Unsupported Accuracy | 1.000 |
| Schema Valid Rate | 1.000 |
| Extra Tool Rate | 0.000 |
| Retry Cases | 0 |
| Retry Recovery Rate | N/A |
| Total Provider Attempts | 22 |
| Average Provider Attempts Per Case | 1.000 |

## 10. Retry Recovery Rate

```text
retry cases that eventually succeeded / all retry cases
```

If no retry occurs, the metric is `None` in JSON and displayed as `N/A`.

## 11. Average Provider Attempts

```text
total provider attempts / case count
```

In the Main retry eval:

```text
22 / 22 = 1.000
```

## 12. Semantic Failure Protection

Retry occurs only inside `RetryingLLMClient`, before Planner business validation.
Therefore:

- `unsupported=true` is not retried.
- schema validation failure is not retried.
- Tool argument validation failure is not retried.
- scenario/tool/parameter semantic failures are not retried.

## 13. Remaining Provider Risks

The real run did not trigger retry, so there is no real-provider recovery case
yet. Offline tests prove the retry path, but future real evals are still needed
to measure recovery rate under actual provider instability.

## 14. Conclusion

Stage 15.3 implemented a single bounded provider retry without changing Planner
Prompt, Tool Schema, ToolArgumentValidator, RuleBasedPlanner, or any Tool
execution path.

The stage succeeds architecturally and offline. The real targeted and Main runs
had no retry cases, so real Retry Recovery Rate is currently `N/A`, not `0.000`.
