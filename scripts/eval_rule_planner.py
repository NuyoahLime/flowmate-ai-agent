import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flowmate.agent import RuleBasedPlanner
from flowmate.eval import PlannerEvaluator, load_eval_dataset


DATASET_PATH = PROJECT_ROOT / "evals" / "planner_eval_v1.json"
RESULT_PATH = PROJECT_ROOT / "evals" / "results" / "rule_planner_v1.json"


def main() -> None:
    cases = load_eval_dataset(DATASET_PATH)
    results, metrics = PlannerEvaluator().evaluate_dataset(
        RuleBasedPlanner(),
        cases,
        planner_name="RuleBasedPlanner",
    )

    payload = {
        "planner_name": "RuleBasedPlanner",
        "dataset": str(DATASET_PATH.relative_to(PROJECT_ROOT)),
        "metrics": metrics.model_dump(mode="json"),
        "results": [result.model_dump(mode="json") for result in results],
    }

    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(
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
    print(f"Detailed results: {RESULT_PATH}")


if __name__ == "__main__":
    main()
