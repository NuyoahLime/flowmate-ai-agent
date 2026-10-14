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
)
from flowmate.eval import PlannerEvaluator, load_eval_dataset


TARGET_CASE_IDS = [
    "boundary-supported-002",
    "boundary-supported-004",
    "boundary-supported-005",
]
DATASET_PATH = PROJECT_ROOT / "evals" / "planner_boundary_v1.json"
RESULT_PATH = (
    PROJECT_ROOT
    / "evals"
    / "results"
    / "llm_planner_stage15_2_semantic_recheck.json"
)


def result_passed(result) -> bool:
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


def main() -> None:
    try:
        config = LLMClientConfig.from_env()
    except LLMClientConfigurationError as exc:
        print(f"Missing configuration: {exc}")
        return

    all_cases = {case.id: case for case in load_eval_dataset(DATASET_PATH)}
    planner = LLMPlanner(OpenAILLMClient(config))
    evaluator = PlannerEvaluator()
    records = []

    for case_id in TARGET_CASE_IDS:
        case = all_cases[case_id]
        result = evaluator.evaluate_case(planner, case, planner_name="LLMPlanner")
        passed = result_passed(result)
        record = {
            "case_id": case_id,
            "dataset": str(DATASET_PATH.relative_to(PROJECT_ROOT)),
            "status": "previously_failed_now_passed" if passed else "still_failed",
            "success": passed,
            "failure_stage": result.failure_stage,
            "failure_type": result.failure_type,
            "expected_supported": result.expected_supported,
            "predicted_supported": result.predicted_supported,
            "expected_tools": result.expected_tools,
            "predicted_tools": result.predicted_tools,
            "expected_arguments": result.expected_arguments,
            "predicted_arguments": result.predicted_arguments,
            "schema_valid": result.schema_valid,
            "error": result.error,
        }
        records.append(record)
        print(json.dumps(record, ensure_ascii=False))

    payload = {
        "planner_name": "LLMPlanner",
        "case_count": len(records),
        "provider_call_count": len(records),
        "records": records,
        "note": "Planner-only semantic recheck. No Task or Tool execution.",
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
