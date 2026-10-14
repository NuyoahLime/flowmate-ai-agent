from calendar import monthrange
from collections.abc import Callable
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flowmate.integrations.calendar.provider import (
    CalendarProviderError,
    CalendarProviderQuery,
    ResolvedCalendarWindow,
)


class CalendarTemporalResolutionError(CalendarProviderError, ValueError):
    pass


class CalendarTemporalResolver:
    def __init__(
        self,
        *,
        timezone: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not timezone.strip():
            raise CalendarTemporalResolutionError("Calendar timezone is required.")
        try:
            self.zone = ZoneInfo(timezone)
        except ZoneInfoNotFoundError as exc:
            raise CalendarTemporalResolutionError(
                f"Unknown calendar timezone: {timezone}"
            ) from exc
        self.timezone = timezone
        self.clock = clock or (lambda: datetime.now(self.zone))

    def resolve(self, query: CalendarProviderQuery) -> ResolvedCalendarWindow:
        now = self.clock()
        if now.tzinfo is None:
            raise CalendarTemporalResolutionError(
                "Calendar clock must return a timezone-aware datetime."
            )
        local_now = now.astimezone(self.zone)

        if query.date == "today":
            return self._resolve_day(local_now.date(), query)
        if query.date == "tomorrow":
            return self._resolve_day(local_now.date() + timedelta(days=1), query)
        if query.date == "next month":
            if query.start_time is not None or query.end_time is not None:
                raise CalendarTemporalResolutionError(
                    "Time-of-day windows are not supported for next month."
                )
            return self._resolve_next_month(local_now.date())

        raise CalendarTemporalResolutionError(
            f"Unsupported calendar date semantic: {query.date}"
        )

    def _resolve_day(
        self,
        concrete_date: date,
        query: CalendarProviderQuery,
    ) -> ResolvedCalendarWindow:
        start_clock = self._parse_time(query.start_time) if query.start_time else time.min
        start = datetime.combine(concrete_date, start_clock, self.zone)

        if query.end_time is None:
            end = datetime.combine(concrete_date + timedelta(days=1), time.min, self.zone)
        else:
            end = datetime.combine(
                concrete_date,
                self._parse_time(query.end_time),
                self.zone,
            )

        return ResolvedCalendarWindow(
            start=start,
            end=end,
            timezone=self.timezone,
        )

    def _resolve_next_month(self, current_date: date) -> ResolvedCalendarWindow:
        if current_date.month == 12:
            start_date = date(current_date.year + 1, 1, 1)
        else:
            start_date = date(current_date.year, current_date.month + 1, 1)
        days = monthrange(start_date.year, start_date.month)[1]
        end_date = start_date + timedelta(days=days)
        return ResolvedCalendarWindow(
            start=datetime.combine(start_date, time.min, self.zone),
            end=datetime.combine(end_date, time.min, self.zone),
            timezone=self.timezone,
        )

    def _parse_time(self, value: str) -> time:
        try:
            return time.fromisoformat(value)
        except ValueError as exc:
            raise CalendarTemporalResolutionError(
                f"Invalid calendar time: {value}"
            ) from exc
