import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flowmate.eval.proactive_trigger_evaluator import (
    ProactiveTriggerEvaluator,
    load_proactive_trigger_eval_dataset,
)


def main() -> int:
    dataset_path = PROJECT_ROOT / "evals" / "proactive_trigger_eval_v1.json"
    output_path = PROJECT_ROOT / "evals" / "results" / "proactive_trigger_eval_v1.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cases = load_proactive_trigger_eval_dataset(dataset_path)
    results, metrics = ProactiveTriggerEvaluator().evaluate_dataset(cases)
    payload = {
        "metrics": metrics.model_dump(mode="json"),
        "results": [result.model_dump(mode="json") for result in results],
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(metrics.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
