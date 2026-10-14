import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flowmate.eval import DynamicPlannerEvaluator, load_dynamic_eval_dataset


def format_optional(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.3f}"


def main(
    dataset_path: Path | None = None,
    result_path: Path | None = None,
) -> None:
    dataset_path = dataset_path or PROJECT_ROOT / "evals" / "planner_dynamic_morning_v1.json"
    result_path = result_path or (
        PROJECT_ROOT / "evals" / "results" / "dynamic_planner_morning_v1.json"
    )

    cases = load_dynamic_eval_dataset(dataset_path)
    results, metrics = DynamicPlannerEvaluator().evaluate_dataset(cases)

    payload = {
        "planner_name": "DynamicTaskOrchestrator",
        "dataset": str(dataset_path.relative_to(PROJECT_ROOT)),
        "metrics": metrics.model_dump(mode="json"),
        "results": [result.model_dump(mode="json") for result in results],
        "note": (
            "Dynamic eval executes calendar_tool mock to obtain observations. "
            "WeatherTool and NavigationTool are not executed."
        ),
    }

    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Cases: {metrics.cases}")
    print(f"Initial Tool Accuracy: {metrics.initial_tool_accuracy:.3f}")
    print(
        "Observation Grounding Accuracy: "
        f"{format_optional(metrics.observation_grounding_accuracy)}"
    )
    print(
        "Continuation Tool Accuracy: "
        f"{format_optional(metrics.continuation_tool_accuracy)}"
    )
    print(f"Dynamic Completion Rate: {format_optional(metrics.dynamic_completion_rate)}")
    print(f"Safe Failure Rate: {format_optional(metrics.safe_failure_rate)}")
    print(f"Detailed results: {result_path}")
    print("CalendarTool mock is executed. WeatherTool and NavigationTool are not executed.")


if __name__ == "__main__":
    dataset_argument = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    result_argument = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    if dataset_argument is not None and not dataset_argument.is_absolute():
        dataset_argument = PROJECT_ROOT / dataset_argument
    if result_argument is not None and not result_argument.is_absolute():
        result_argument = PROJECT_ROOT / result_argument
    main(dataset_argument, result_argument)
