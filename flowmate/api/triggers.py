from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query

from flowmate.schemas import TriggerStatus
from flowmate.triggers import ProactiveTriggerService, SQLiteTriggerRepository


router = APIRouter(prefix="/api/v1/triggers", tags=["triggers"])


@router.get("")
def list_triggers(
    status: TriggerStatus | None = None,
    limit: int = Query(default=50, ge=1, le=100),
):
    repository = SQLiteTriggerRepository()
    return [
        trigger.model_dump(mode="json")
        for trigger in repository.list_triggers(status=status, limit=limit)
    ]


@router.get("/{trigger_id}")
def get_trigger(trigger_id: str):
    trigger = SQLiteTriggerRepository().get(trigger_id)
    if trigger is None:
        raise HTTPException(status_code=404, detail="Trigger not found.")
    return trigger.model_dump(mode="json")


@router.post("/tick")
def tick_triggers(now: str | None = None):
    parsed_now = _parse_now(now)
    repository = SQLiteTriggerRepository()
    result = ProactiveTriggerService(repository).tick(now=parsed_now)
    return result.model_dump(mode="json")


def _parse_now(value: str | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise HTTPException(status_code=400, detail="now must be timezone-aware.")
    return parsed
