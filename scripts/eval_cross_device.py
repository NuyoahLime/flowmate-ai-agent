from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flowmate.eval.cross_device_evaluator import CrossDeviceEvaluator


def main() -> int:
    dataset = PROJECT_ROOT / "evals" / "cross_device_eval_v1.json"
    output = PROJECT_ROOT / "evals" / "results" / "cross_device_eval_v1.json"
    result = CrossDeviceEvaluator().evaluate(dataset)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["metrics"], ensure_ascii=False, indent=2))
    metric_values = [
        value
        for key, value in result["metrics"].items()
        if key != "cases" and value is not None
    ]
    return 0 if metric_values and all(value == 1.0 for value in metric_values) else 1


if __name__ == "__main__":
    raise SystemExit(main())
