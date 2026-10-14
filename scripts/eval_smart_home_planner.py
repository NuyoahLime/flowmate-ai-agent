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
from flowmate.eval import (
    PlannerEvaluator,
    calculate_smart_home_category_metrics,
    load_eval_dataset,
)


def format_optional(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.3f}"


def main(
    dataset_path: Path | None = None,
    result_path: Path | None = None,
) -> None:
    dataset_path = dataset_path or (
        PROJECT_ROOT / "evals" / "planner_smart_home_v1.json"
    )
    result_path = result_path or (
        PROJECT_ROOT
        / "evals"
        / "results"
        / "llm_planner_smart_home_v1_stage18_1.json"
    )

    try:
        config = LLMClientConfig.from_env()
    except LLMClientConfigurationError as exc:
        print(f"Missing configuration: {exc}")
        return

    cases = load_eval_dataset(dataset_path)
    planner = LLMPlanner(
        RetryingLLMClient(
            OpenAILLMClient(config),
            max_attempts=2,
        )
    )
    results, metrics = PlannerEvaluator().evaluate_dataset(
        planner,
        cases,
        planner_name="LLMPlanner",
    )
    category_metrics = calculate_smart_home_category_metrics(results, metrics)

    payload = {
        "planner_name": "LLMPlanner",
        "dataset": str(dataset_path.relative_to(PROJECT_ROOT)),
        "max_attempts_per_case": 2,
        "metrics": metrics.model_dump(mode="json"),
        "category_metrics": category_metrics.model_dump(mode="json"),
        "results": [result.model_dump(mode="json") for result in results],
        "note": "Planner-only eval. No Task or Tool execution.",
    }
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Cases: {metrics.cases}")
    print(f"Scenario Accuracy: {metrics.scenario_accuracy:.3f}")
    print(f"Supported Recall: {format_optional(metrics.supported_recall)}")
    print(f"Unsupported Recall: {format_optional(metrics.unsupported_recall)}")
    print(f"Tool Selection Accuracy: {metrics.tool_selection_accuracy:.3f}")
    print(f"Parameter Accuracy: {metrics.parameter_accuracy:.3f}")
    print(f"Parameter Completeness: {format_optional(metrics.parameter_completeness)}")
    print(f"Schema Valid Rate: {metrics.schema_valid_rate:.3f}")
    print(f"Extra Tool Rate: {metrics.extra_tool_rate:.3f}")
    print(f"Action Risk Accuracy: {format_optional(metrics.action_risk_accuracy)}")
    print(
        "SmartHome Supported Recall: "
        f"{format_optional(category_metrics.smart_home_supported_recall)}"
    )
    print(
        "Unsupported Device Recall: "
        f"{format_optional(category_metrics.unsupported_device_recall)}"
    )
    print(
        "Scheduled Automation Unsupported Recall: "
        f"{format_optional(category_metrics.scheduled_automation_unsupported_recall)}"
    )
    print(
        "Conditional Automation Unsupported Recall: "
        f"{format_optional(category_metrics.conditional_automation_unsupported_recall)}"
    )
    print(
        "SmartHome Minimality Accuracy: "
        f"{format_optional(category_metrics.smart_home_minimality_accuracy)}"
    )
    print(f"Retry Cases: {metrics.retry_cases}")
    print(f"Retry Recovery Rate: {format_optional(metrics.retry_recovery_rate)}")
    print(f"Total Provider Attempts: {metrics.total_provider_attempts}")
    print(
        "Average Provider Attempts Per Case: "
        f"{metrics.average_provider_attempts_per_case:.3f}"
    )
    print(f"Detailed results: {result_path}")
    print("No Task or Tool execution is performed by this script.")


if __name__ == "__main__":
    dataset_argument = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    result_argument = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    if dataset_argument is not None and not dataset_argument.is_absolute():
        dataset_argument = PROJECT_ROOT / dataset_argument
    if result_argument is not None and not result_argument.is_absolute():
        result_argument = PROJECT_ROOT / result_argument
    main(dataset_argument, result_argument)
