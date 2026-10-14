from __future__ import annotations

import os
from datetime import date, datetime, time
from hashlib import sha256
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, model_validator

from flowmate.schemas import TriggerDefinition, TriggerStatus, TriggerType
from flowmate.tools.calendar import CalendarEvent
from flowmate.triggers.errors import TriggerConfigurationError
from flowmate.triggers.repository import TriggerRepository


DEFAULT_CALENDAR_TRIGGER_LEAD_MINUTES = 90
LEAD_TIME_ENV = "FLOWMATE_CALENDAR_TRIGGER_LEAD_MINUTES"


class CalendarTriggerSourceEvent(BaseModel):
    id: str | None = None
    summary: str = Field(min_length=1)
    start: datetime | None = None
    location: str | None = None
    all_day: bool = False

    @model_validator(mode="after")
    def validate_start(self) -> "CalendarTriggerSourceEvent":
        if self.start is not None and self.start.tzinfo is None:
            raise ValueError("Calendar trigger source start must be timezone-aware.")
        return self


class CalendarTriggerRegistrationService:
    def __init__(
        self,
        repository: TriggerRepository,
        *,
        lead_time_minutes: int | None = None,
    ) -> None:
        self.repository = repository
        self.lead_time_minutes = (
            lead_time_minutes
            if lead_time_minutes is not None
            else resolve_calendar_trigger_lead_minutes()
        )
        if self.lead_time_minutes <= 0:
            raise TriggerConfigurationError("Calendar trigger lead time must be > 0.")

    def register_event(
        self,
        event: CalendarTriggerSourceEvent,
        *,
        now: datetime,
    ) -> TriggerDefinition | None:
        if now.tzinfo is None:
            raise TriggerConfigurationError("Trigger registration clock must be timezone-aware.")
        if event.all_day or event.start is None or not event.location:
            return None

        source_event_id = event.id or self._fingerprint_event(event)
        existing = self.repository.get_by_source_event_id(source_event_id)
        if existing is not None:
            if existing.status == TriggerStatus.ACTIVE:
                updated = existing.model_copy(
                    update={
                        "source_event_start": event.start,
                        "source_event_location": event.location,
                        "source_event_summary": event.summary,
                        "lead_time_minutes": self.lead_time_minutes,
                    }
                )
                self.repository.save(updated)
                return updated
            return existing

        trigger = TriggerDefinition(
            id=self._trigger_id(source_event_id),
            trigger_type=TriggerType.CALENDAR_EVENT_LEAD_TIME,
            status=TriggerStatus.ACTIVE,
            source_event_id=source_event_id,
            source_event_start=event.start,
            source_event_location=event.location,
            source_event_summary=event.summary,
            lead_time_minutes=self.lead_time_minutes,
            created_at=now,
        )
        self.repository.save(trigger)
        return trigger

    def register_calendar_event(
        self,
        event: CalendarEvent,
        *,
        event_date: date,
        timezone: str,
        now: datetime,
    ) -> TriggerDefinition | None:
        start_clock = time.fromisoformat(event.start_time)
        local_start = datetime.combine(event_date, start_clock, ZoneInfo(timezone))
        return self.register_event(
            CalendarTriggerSourceEvent(
                id=event.id,
                summary=event.title,
                start=local_start,
                location=event.location,
                all_day=False,
            ),
            now=now,
        )

    def _trigger_id(self, source_event_id: str) -> str:
        digest = sha256(source_event_id.encode("utf-8")).hexdigest()[:12]
        return f"trigger-calendar-{digest}"

    def _fingerprint_event(self, event: CalendarTriggerSourceEvent) -> str:
        payload = f"{event.start.isoformat()}|{event.location}|{event.summary}"
        digest = sha256(payload.encode("utf-8")).hexdigest()[:16]
        return f"event-fingerprint-{digest}"


def resolve_calendar_trigger_lead_minutes() -> int:
    value = os.getenv(LEAD_TIME_ENV)
    if value is None or value.strip() == "":
        return DEFAULT_CALENDAR_TRIGGER_LEAD_MINUTES
    try:
        return int(value)
    except ValueError as exc:
        raise TriggerConfigurationError(
            f"{LEAD_TIME_ENV} must be an integer."
        ) from exc
