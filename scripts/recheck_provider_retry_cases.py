import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flowmate.agent import (
    LLMClientConfig,
    LLMClientConfigurationError,
    LLMPlanner,
    OpenAILLMClient,
    RetryingLLMClient,
)
from flowmate.eval import PlannerEvaluator, load_eval_dataset


TARGETS = [
    ("commute-008", "evals/planner_eval_v1.json"),
    ("minimality-navigation-004", "evals/planner_minimality_v1.json"),
]
RESULT_PATH = (
    PROJECT_ROOT
    / "evals"
    / "results"
    / "llm_planner_stage15_3_retry_recheck.json"
)


def result_successful(result) -> bool:
    return (
        result.scenario_correct
        and result.tool_selection_correct
        and (result.parameter_accuracy is None or result.parameter_accuracy == 1.0)
        and (
            result.parameter_completeness is None
            or result.parameter_completeness == 1.0
        )
        and result.schema_valid
    )


def final_status(result) -> str:
    if result.retry_performed and result_successful(result):
        return "retry_recovered"
    if not result.retry_performed and result_successful(result):
        return "no_retry_needed"
    if result.retry_performed and str(result.failure_type or "").startswith("provider_"):
        return "retry_exhausted"
    if result.failure_type in {
        "scenario_error",
        "tool_selection_error",
        "parameter_value_error",
        "parameter_completeness_error",
        "tool_argument_validation_error",
        "llm_schema_error",
    }:
        return "semantic_failure_no_retry"
    return "still_failed"


def load_case(case_id: str, dataset_name: str):
    dataset_path = PROJECT_ROOT / dataset_name
    cases = load_eval_dataset(dataset_path)
    return dataset_name, next(case for case in cases if case.id == case_id)


def main() -> None:
    try:
        config = LLMClientConfig.from_env()
    except LLMClientConfigurationError as exc:
        print(f"Missing configuration: {exc}")
        return

    planner = LLMPlanner(
        RetryingLLMClient(
            OpenAILLMClient(config),
            max_attempts=2,
        )
    )
    evaluator = PlannerEvaluator()
    records = []

    for case_id, dataset_name in TARGETS:
        dataset, case = load_case(case_id, dataset_name)
        result = evaluator.evaluate_case(planner, case, planner_name="LLMPlanner")
        status = final_status(result)
        record = {
            "case_id": case_id,
            "dataset": dataset,
            "attempt_count": result.attempt_count,
            "retry_performed": result.retry_performed,
            "first_provider_error_type": result.first_provider_error_type,
            "final_provider_error_type": result.final_provider_error_type,
            "final_status": status,
            "final_failure_type": result.failure_type,
            "predicted_tools": result.predicted_tools,
            "predicted_arguments": result.predicted_arguments,
            "error": result.error,
        }
        records.append(record)
        print(json.dumps(record, ensure_ascii=False))

    payload = {
        "planner_name": "LLMPlanner",
        "case_count": len(records),
        "max_attempts_per_case": 2,
        "total_provider_attempts": sum(record["attempt_count"] for record in records),
        "records": records,
        "note": "Planner-only retry validation. No Task or Tool execution.",
    }
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Detailed results: {RESULT_PATH}")
    print("No Task or Tool execution is performed by this script.")


if __name__ == "__main__":
    main()
