# Provider Stability Failure Attribution V1

## 1. Problem

Stage 15 completed deterministic Tool argument validation, but the final real
provider eval still had five failed cases:

- `commute-006`
- `boundary-supported-002`
- `boundary-supported-004`
- `boundary-supported-005`
- `minimality-navigation-004`

This stage is diagnostic. It does not optimize Planner behavior.

## 2. Stage 15 Regression Summary

Known Stage 15 final metrics:

| Dataset | Scenario | Tool Selection | Parameter Accuracy | Parameter Completeness | Unsupported | Schema Valid | Extra Tool |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Main | 1.000 | 1.000 | 0.980 | 1.000 | 1.000 | 1.000 | 0.000 |
| Challenge | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 |
| Boundary | 0.700 | 0.400 | 0.400 | 1.000 | 1.000 | 0.700 | 0.000 |
| Minimality | 0.917 | 0.917 | 0.917 | 1.000 | N/A | 0.917 | 0.000 |
| Parameters | 1.000 | 1.000 | 1.000 | 1.000 | N/A | 1.000 | 0.000 |

## 3. Provider Parsing Pipeline

Actual DeepSeek path:

```text
OpenAILLMClient
-> chat.completions.create
-> response_format={"type": "json_object"}
-> response.choices[0].message.content
-> response extraction
-> whitespace / whole-code-fence normalization
-> json.loads
-> Mapping check
-> LLMPlanner
-> LLMPlanResponse validation
```

The Adapter does not execute Tools and does not validate business semantics.

## 4. Failure Taxonomy

The diagnostic failure types used in this stage are:

- `provider_transport_error`: SDK, HTTP, or provider request failure.
- `provider_empty_output`: provider returned no usable content.
- `provider_parse_error`: provider response shape or extracted JSON object shape was unusable.
- `provider_invalid_json`: content existed but was not valid JSON.
- `llm_schema_error`: JSON decoded but failed `LLMPlanResponse` validation.
- `tool_argument_validation_error`: planned Tool arguments failed Tool input schema validation.
- `scenario_error`: supported / unsupported decision was wrong.
- `tool_selection_error`: supported decision was correct but Tool set was wrong.
- `parameter_value_error`: Tool set and fields were present, but a Gold parameter value differed.
- `parameter_completeness_error`: expected parameter field was missing.

## 5. Five Failure Cases

Original Stage 15 attribution:

| Case | Dataset | Original Failure | Attribution |
| --- | --- | --- | --- |
| `commute-006` | Main | `weather_tool.location=home`, expected `current_city` | `parameter_value_error` |
| `boundary-supported-002` | Boundary | model returned unsupported due missing origin/departure time | `scenario_error` |
| `boundary-supported-004` | Boundary | unable to parse DeepSeek JSON response | provider parse failure, stage unavailable in old result |
| `boundary-supported-005` | Boundary | unable to parse DeepSeek JSON response | provider parse failure, stage unavailable in old result |
| `minimality-navigation-004` | Minimality | unable to parse DeepSeek JSON response | provider parse failure, stage unavailable in old result |

When prediction data was absent in the original result, it was treated as
prediction unavailable.

## 6. Adapter Audit

The DeepSeek Adapter previously called `json.loads(content)` directly after
reading `response.choices[0].message.content`.

Observed weaknesses:

- Empty content was collapsed into a generic parse message.
- Malformed JSON was collapsed into the same generic parse message.
- Whole Markdown JSON code fences were not handled.
- Non-object JSON was not distinguished from malformed JSON.
- Provider SDK exceptions and response parsing failures were both too coarse.
- Pydantic `LLMPlanResponse` validation happened later in LLMPlanner, but
  Evaluator attribution used a generic schema bucket.

## 7. Deterministic Parser Changes

Implemented deterministic parsing hardening:

- Trim leading/trailing whitespace.
- Accept whole-response Markdown code fences such as ```json ... ```.
- Distinguish empty content as `provider_empty_output`.
- Distinguish `json.JSONDecodeError` as `provider_invalid_json`.
- Distinguish non-object JSON as `provider_parse_error`.
- Preserve `LLMProviderError.stage` and `LLMProviderError.error_type`.
- Preserve provider error type/stage in `PlannerEvalResult`.
- Attribute `PlannerOutputValidationError` as `llm_schema_error`.
- Attribute Tool input schema failures as `tool_argument_validation_error`.

No raw provider response, API key, or authorization header is persisted.

## 8. Offline Tests

Added offline tests for:

- valid DeepSeek JSON mode output
- JSON with surrounding whitespace
- whole Markdown JSON code fence
- empty content
- malformed JSON
- non-object JSON
- provider SDK exception
- provider stage/error type propagation
- LLM schema attribution
- Tool argument validation attribution

Full test result:

```text
155 passed
```

## 9. Targeted Real Recheck

Only the five previously failed cases were rechecked. Each case used one real
Planner call. No retry and no Tool execution occurred.

Result file:

```text
evals/results/llm_planner_stage15_1_recheck.json
```

| Case | Recheck Status | Failure Stage | Failure Type |
| --- | --- | --- | --- |
| `commute-006` | `previously_failed_now_passed` | N/A | N/A |
| `boundary-supported-002` | `still_failed` | `capability_or_unsupported` | `scenario_error` |
| `boundary-supported-004` | `still_failed` | `capability_or_unsupported` | `scenario_error` |
| `boundary-supported-005` | `still_failed` | `capability_or_unsupported` | `scenario_error` |
| `minimality-navigation-004` | `still_failed` | `response_extraction` | `provider_empty_output` |

## 10. Failure Attribution

After recheck:

- `commute-006` appears nondeterministic. The exact previous parameter-value
  error did not reproduce.
- `boundary-supported-002`, `boundary-supported-004`, and
  `boundary-supported-005` are Planner semantic regressions in this run. The
  model decided the requests were unsupported because it would not infer required
  navigation arguments from the current canonical rules.
- `minimality-navigation-004` is provider/parser instability. The improved
  Adapter now identifies the failure as empty provider output at response
  extraction.

## 11. Stability Findings

The current regression is mixed:

- Provider/parser instability exists, proven by `provider_empty_output` and prior
  generic parse failures.
- Planner semantic regression exists in Boundary supported driving-information
  cases.
- Tool argument validation is stricter, but it is not the direct cause of the
  five recheck failures.

## 12. Retry Decision

Retry is justified as a future reliability feature for provider transport,
empty-output, and invalid-JSON failures.

Retry is not a solution for semantic regressions. Boundary semantic failures
need Planner prompt/schema policy work in a later stage.

No retry was implemented in this stage.

## 13. Remaining Risks

- DeepSeek JSON mode may still occasionally return empty content or unparsable
  output.
- Boundary supported vehicle-information cases remain sensitive to whether the
  model applies canonical argument mappings.
- Targeted recheck is not a replacement for full Eval metrics.

## 14. Conclusion

Stage 15.1 improved failure attribution and Adapter observability without
changing Planner business strategy. It found a mixed failure pattern:

- one previously failed case passed on recheck
- three cases remain semantic Planner regressions
- one case remains provider/parser instability

No Tools were executed, no Retry was implemented, no Tool Schema was changed, and
no Planner Prompt was changed in this stage.
