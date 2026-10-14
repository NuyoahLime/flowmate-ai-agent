import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flowmate.eval import DynamicExecutionEvaluator, load_dynamic_execution_dataset


def format_optional(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.3f}"


def main(
    dataset_path: Path | None = None,
    result_path: Path | None = None,
) -> None:
    dataset_path = dataset_path or PROJECT_ROOT / "evals" / "dynamic_execution_v1.json"
    result_path = result_path or (
        PROJECT_ROOT / "evals" / "results" / "dynamic_execution_v1.json"
    )

    cases = load_dynamic_execution_dataset(dataset_path)
    results, metrics = DynamicExecutionEvaluator().evaluate_dataset(cases)

    payload = {
        "planner_name": "DynamicTaskOrchestrator",
        "dataset": str(dataset_path.relative_to(PROJECT_ROOT)),
        "metrics": metrics.model_dump(mode="json"),
        "results": [result.model_dump(mode="json") for result in results],
        "note": (
            "Dynamic execution eval runs CalendarTool mock and continuation Mock tools "
            "through ToolExecutor. No real third-party APIs are called."
        ),
    }

    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Cases: {metrics.cases}")
    print(
        "Final Execution Success Rate: "
        f"{format_optional(metrics.final_execution_success_rate)}"
    )
    print(
        "Continuation Execution Accuracy: "
        f"{format_optional(metrics.continuation_execution_accuracy)}"
    )
    print(
        "Execution Order Accuracy: "
        f"{format_optional(metrics.execution_order_accuracy)}"
    )
    print(
        "Failure Containment Rate: "
        f"{format_optional(metrics.failure_containment_rate)}"
    )
    print(
        "Grounded Execution Rate: "
        f"{format_optional(metrics.grounded_execution_rate)}"
    )
    print(f"Detailed results: {result_path}")
    print("No real provider calls or real third-party Tool APIs are performed.")


if __name__ == "__main__":
    dataset_argument = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    result_argument = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    if dataset_argument is not None and not dataset_argument.is_absolute():
        dataset_argument = PROJECT_ROOT / dataset_argument
    if result_argument is not None and not result_argument.is_absolute():
        result_argument = PROJECT_ROOT / result_argument
    main(dataset_argument, result_argument)
