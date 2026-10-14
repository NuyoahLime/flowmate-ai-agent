# Evaluation Summary

FlowMate evaluation is split into three product layers instead of relying on one aggregate number:

```text
Planner Evaluation -> planning quality
Trigger Evaluation -> proactive behavior correctness
Cross-device Evaluation -> coordination and consistency correctness
```

## Why Keep Rule Baseline

RuleBasedPlanner creates a deterministic baseline. It shows what can be solved with explicit rules and exposes where rule leakage appears on challenge sets.

## Why Challenge Sets Exist

Main datasets can overfit to obvious wording. Challenge sets include paraphrases and hard negatives to reveal boundary weakness, tool over-selection and over-refusal.

## Planner Eval V3

Current saved result: `evals/results/llm_planner_v3_stage20.json`.

| Metric | Value |
| --- | ---: |
| Cases | 36 |
| Scenario Accuracy | 0.9722 |
| Tool Selection Accuracy | 0.9583 |
| Parameter Accuracy | 0.9375 |
| Parameter Completeness | 1.000 |
| Supported Recall | 0.9583 |
| Unsupported Recall | 1.000 |
| Schema Valid Rate | 0.9722 |
| Extra Tool Rate | 0.000 |

## Metric Design

- Supported Recall and Unsupported Recall are separate because over-refusal and over-acceptance are different product failures.
- Tool Minimality is measured separately because extra tools can create cost, latency and safety risk even when the final answer looks valid.
- Parameter Accuracy and Parameter Completeness are separate because wrong fields and missing fields require different fixes.
- Provider failure is classified separately from planner failure so network instability is not mistaken for reasoning failure.
- V1 / V2 / V3 datasets are versioned to keep regression history honest.

## Trigger Eval V1

Current saved result: `evals/results/proactive_trigger_eval_v1.json`.

Trigger Eval is not an LLM eval. It validates deterministic trigger registration, due detection, expiration, duplicate prevention, restart idempotency, task creation and side-effect containment.

| Metric | Value |
| --- | ---: |
| Cases | 12 |
| Registration Accuracy | 1.000 |
| Due Detection Accuracy | 1.000 |
| Expiration Accuracy | 1.000 |
| Duplicate Trigger Prevention | 1.000 |
| Duplicate Fire Prevention | 1.000 |
| Restart Idempotency | 1.000 |
| Task Creation Accuracy | 1.000 |
| Side-effect Containment | 1.000 |

## Cross-device Eval V1

Current saved result: `evals/results/cross_device_eval_v1.json`.

The dataset contains 16 deterministic cases covering routing success, offline and missing-capability rejection, duplicate handoff prevention, accept idempotency, wrong-user isolation, rejection, restart persistence, confirmation consistency, and state sync.

| Metric | Value |
| --- | ---: |
| Cases | 16 |
| Device Registration Accuracy | 1.000 |
| Routing Accuracy | 1.000 |
| Capability Match Accuracy | 1.000 |
| Offline Device Rejection | 1.000 |
| Handoff Creation Accuracy | 1.000 |
| Duplicate Handoff Prevention | 1.000 |
| Handoff Acceptance Accuracy | 1.000 |
| Wrong-user Isolation | 1.000 |
| Restart Persistence | 1.000 |
| Confirmation Consistency | 1.000 |
| State Sync Accuracy | 1.000 |
