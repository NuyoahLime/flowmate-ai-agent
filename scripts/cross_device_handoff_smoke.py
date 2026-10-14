from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flowmate.cross_device.demo import run_cross_device_smoke


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the fully offline Stage 29 cross-device handoff smoke."
    )
    parser.add_argument("--db-path", default=None)
    args = parser.parse_args()

    if args.db_path:
        result = run_cross_device_smoke(Path(args.db_path))
    else:
        with tempfile.TemporaryDirectory(prefix="flowmate-stage29-") as directory:
            result = run_cross_device_smoke(Path(directory) / "cross_device_smoke.db")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    expected = {
        "origin_device": "phone_001",
        "initial_current_device": "phone_001",
        "router_recommendation": "car_001",
        "handoff_initial_status": "PENDING",
        "handoff_final_status": "ACCEPTED",
        "final_current_device": "car_001",
        "phone_post_handoff_current_device": "car_001",
        "duplicate_task_count": 0,
        "duplicate_accept_count": 0,
        "real_vehicle_calls": 0,
        "real_smart_home_calls": 0,
        "real_feishu_calls": 0,
    }
    return 0 if all(result[key] == value for key, value in expected.items()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
