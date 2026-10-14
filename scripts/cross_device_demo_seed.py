from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flowmate.cross_device import SQLiteCrossDeviceRepository, TaskDeviceStateService, seed_demo_devices
from flowmate.cross_device.demo import build_cross_device_commute_task
from flowmate.persistence import TaskPersistenceService


def main() -> int:
    repository = SQLiteCrossDeviceRepository()
    user, phone, car = seed_demo_devices(repository)
    task = build_cross_device_commute_task()
    TaskPersistenceService().persist(task)
    state = TaskDeviceStateService(repository).initialize(
        task_id=task.id,
        owner_user_id=user.id,
        origin_device_id=phone.id,
    )
    print(
        json.dumps(
            {
                "user": user.model_dump(mode="json"),
                "devices": [
                    phone.model_dump(mode="json"),
                    car.model_dump(mode="json"),
                ],
                "task_id": task.id,
                "device_state": state.model_dump(mode="json"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
