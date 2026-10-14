import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flowmate.eval import DynamicNotificationEvaluator, load_dynamic_notification_dataset


def format_optional(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.3f}"


def main(
    dataset_path: Path | None = None,
    result_path: Path | None = None,
) -> None:
    dataset_path = dataset_path or PROJECT_ROOT / "evals" / "dynamic_notification_v1.json"
    result_path = result_path or (
        PROJECT_ROOT / "evals" / "results" / "dynamic_notification_v1.json"
    )

    cases = load_dynamic_notification_dataset(dataset_path)
    results, metrics = DynamicNotificationEvaluator().evaluate_dataset(cases)

    payload = {
        "evaluator": "DynamicNotificationEvaluator",
        "dataset": str(dataset_path.relative_to(PROJECT_ROOT)),
        "metrics": metrics.model_dump(mode="json"),
        "results": [result.model_dump(mode="json") for result in results],
        "note": (
            "Runs deterministic mock tools only. No real provider calls or real "
            "external notifications are performed."
        ),
    }

    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Cases: {metrics.cases}")
    print(
        "Side-effect Proposal Accuracy: "
        f"{metrics.side_effect_proposal_accuracy:.3f}"
    )
    print(
        "Pre-confirmation Blocking Rate: "
        f"{format_optional(metrics.pre_confirmation_blocking_rate)}"
    )
    print(
        "Confirmed Side-effect Success Rate: "
        f"{format_optional(metrics.confirmed_side_effect_success_rate)}"
    )
    print(
        "Rejected Side-effect Containment Rate: "
        f"{format_optional(metrics.rejected_side_effect_containment_rate)}"
    )
    print(
        "Informational Re-execution Rate: "
        f"{format_optional(metrics.informational_reexecution_rate)}"
    )
    print(
        "Notification Grounding Accuracy: "
        f"{format_optional(metrics.notification_grounding_accuracy)}"
    )
    print(
        "Side-effect Minimality Accuracy: "
        f"{format_optional(metrics.side_effect_minimality_accuracy)}"
    )
    print(f"Detailed results: {result_path}")


if __name__ == "__main__":
    dataset_argument = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    result_argument = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    if dataset_argument is not None and not dataset_argument.is_absolute():
        dataset_argument = PROJECT_ROOT / dataset_argument
    if result_argument is not None and not result_argument.is_absolute():
        result_argument = PROJECT_ROOT / result_argument
    main(dataset_argument, result_argument)
