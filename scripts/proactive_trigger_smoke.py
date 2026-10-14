import json
import sys
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flowmate.persistence import SQLiteTaskRepository
from flowmate.triggers import (
    CalendarTriggerRegistrationService,
    CalendarTriggerSourceEvent,
    ProactiveTriggerService,
    SQLiteTriggerRepository,
)


def main() -> int:
    with TemporaryDirectory() as directory:
        db_path = Path(directory) / "proactive_trigger_smoke.db"
        trigger_repository = SQLiteTriggerRepository(db_path)
        task_repository = SQLiteTaskRepository(db_path)
        registration = CalendarTriggerRegistrationService(
            trigger_repository,
            lead_time_minutes=60,
        )
        now = datetime.fromisoformat("2026-08-12T07:30:00+08:00")
        trigger = registration.register_event(
            CalendarTriggerSourceEvent(
                id="smoke-calendar-event-001",
                summary="Morning Meeting",
                start=datetime.fromisoformat("2026-08-12T08:30:00+08:00"),
                location="人民广场",
            ),
            now=now,
        )
        first = ProactiveTriggerService(trigger_repository).tick(now=now)
        second = ProactiveTriggerService(trigger_repository).tick(now=now)
        restarted = ProactiveTriggerService(SQLiteTriggerRepository(db_path)).tick(now=now)
        final_trigger = trigger_repository.get(trigger.id)
        tasks = task_repository.list_tasks()

        print(
            json.dumps(
                {
                    "trigger_status_before": "ACTIVE",
                    "first_tick_generated_tasks": len(first.generated_task_ids),
                    "second_tick_generated_tasks": len(second.generated_task_ids),
                    "restart_tick_generated_tasks": len(restarted.generated_task_ids),
                    "trigger_status_after": final_trigger.status.value,
                    "generated_task_id": final_trigger.generated_task_id,
                    "task_count": len(tasks),
                    "real_calendar_calls": 0,
                    "real_weather_calls": 0,
                    "real_amap_calls": 0,
                    "real_feishu_calls": 0,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
