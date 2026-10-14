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
    LLMProviderError,
    OpenAILLMClient,
)
from flowmate.eval import PlannerEvaluator, load_eval_dataset


def main(
    dataset_path: Path | None = None,
    result_path: Path | None = None,
) -> None:
    dataset_path = dataset_path or PROJECT_ROOT / "evals" / "planner_eval_v1.json"
    result_path = result_path or PROJECT_ROOT / "evals" / "results" / "llm_planner_v1.json"

    try:
        config = LLMClientConfig.from_env()
    except LLMClientConfigurationError as exc:
        print(f"Missing configuration: {exc}")
        return

    cases = load_eval_dataset(dataset_path)
    planner = LLMPlanner(OpenAILLMClient(config))
    results, metrics = PlannerEvaluator().evaluate_dataset(
        planner,
        cases,
        planner_name="LLMPlanner",
    )

    payload = {
        "planner_name": "LLMPlanner",
        "dataset": str(dataset_path.relative_to(PROJECT_ROOT)),
        "metrics": metrics.model_dump(mode="json"),
        "results": [result.model_dump(mode="json") for result in results],
    }

    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Cases: {metrics.cases}")
    print(f"Scenario Accuracy: {metrics.scenario_accuracy:.3f}")
    supported_recall = (
        "N/A"
        if metrics.supported_recall is None
        else f"{metrics.supported_recall:.3f}"
    )
    unsupported_recall = (
        "N/A"
        if metrics.unsupported_recall is None
        else f"{metrics.unsupported_recall:.3f}"
    )
    print(f"Supported Recall: {supported_recall}")
    print(f"Unsupported Recall: {unsupported_recall}")
    print(f"Tool Selection Accuracy: {metrics.tool_selection_accuracy:.3f}")
    print(f"Parameter Accuracy: {metrics.parameter_accuracy:.3f}")
    parameter_completeness = (
        "N/A"
        if metrics.parameter_completeness is None
        else f"{metrics.parameter_completeness:.3f}"
    )
    print(f"Parameter Completeness: {parameter_completeness}")
    temporal_rate = (
        "N/A"
        if metrics.temporal_constraint_preservation_rate is None
        else f"{metrics.temporal_constraint_preservation_rate:.3f}"
    )
    print(f"Temporal Constraint Preservation Rate: {temporal_rate}")
    unsupported_accuracy = (
        "N/A"
        if metrics.unsupported_accuracy is None
        else f"{metrics.unsupported_accuracy:.3f}"
    )
    print(f"Unsupported Accuracy: {unsupported_accuracy}")
    print(f"Schema Valid Rate: {metrics.schema_valid_rate:.3f}")
    print(f"Extra Tool Rate: {metrics.extra_tool_rate:.3f}")
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
