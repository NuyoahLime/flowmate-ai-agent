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
from flowmate.eval import PlannerEvalCase, PlannerEvaluator, load_eval_dataset


TARGETS = [
    ("commute-006", "evals/planner_eval_v1.json"),
    ("boundary-supported-002", "evals/planner_boundary_v1.json"),
    ("boundary-supported-004", "evals/planner_boundary_v1.json"),
    ("boundary-supported-005", "evals/planner_boundary_v1.json"),
    ("minimality-navigation-004", "evals/planner_minimality_v1.json"),
]

RESULT_PATH = PROJECT_ROOT / "evals" / "results" / "llm_planner_stage15_1_recheck.json"


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


def load_target_cases() -> list[tuple[str, PlannerEvalCase]]:
    loaded: list[tuple[str, PlannerEvalCase]] = []
    for case_id, dataset_name in TARGETS:
        dataset_path = PROJECT_ROOT / dataset_name
        cases = load_eval_dataset(dataset_path)
        case = next(item for item in cases if item.id == case_id)
        loaded.append((dataset_name, case))
    return loaded


def main() -> None:
    try:
        config = LLMClientConfig.from_env()
    except LLMClientConfigurationError as exc:
        print(f"Missing configuration: {exc}")
        return

    planner = LLMPlanner(OpenAILLMClient(config))
    evaluator = PlannerEvaluator()
    records = []

    for dataset_name, case in load_target_cases():
        result = evaluator.evaluate_case(planner, case, planner_name="LLMPlanner")
        passed = result_passed(result)
        records.append(
            {
                "case_id": case.id,
                "dataset": dataset_name,
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
        )
        print(
            json.dumps(
                {
                    "case_id": case.id,
                    "status": records[-1]["status"],
                    "failure_stage": result.failure_stage,
                    "failure_type": result.failure_type,
                    "predicted_tools": result.predicted_tools,
                    "predicted_arguments": result.predicted_arguments,
                    "error": result.error,
                },
                ensure_ascii=False,
            )
        )

    payload = {
        "planner_name": "LLMPlanner",
        "case_count": len(records),
        "provider_call_count": len(records),
        "records": records,
        "note": "Planner-only recheck. No TaskExecutor, StepExecutor, ToolExecutor, or Tool execution.",
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
