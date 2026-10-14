from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from flowmate.integrations.weather.provider import WeatherMappingError


class WeatherTemporalResolver:
    def __init__(self, *, clock: datetime | None = None) -> None:
        if clock is not None and clock.tzinfo is None:
            raise ValueError("clock must be timezone-aware.")
        self.clock = clock

    def resolve_date(self, value: str, *, timezone: str) -> date:
        normalized = value.strip().lower()
        if not normalized:
            raise WeatherMappingError("Weather date must not be blank.")

        zone = ZoneInfo(timezone)
        now = self.clock.astimezone(zone) if self.clock is not None else datetime.now(zone)

        if normalized == "today":
            return now.date()
        if normalized == "tomorrow":
            return now.date() + timedelta(days=1)

        try:
            return date.fromisoformat(normalized)
        except ValueError as exc:
            raise WeatherMappingError(
                "Unsupported weather date. Use today, tomorrow, or YYYY-MM-DD."
            ) from exc
