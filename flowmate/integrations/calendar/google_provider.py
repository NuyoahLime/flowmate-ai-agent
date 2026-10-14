from datetime import datetime
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from flowmate.integrations.calendar.provider import (
    CalendarProviderError,
    CalendarProviderQuery,
)
from flowmate.integrations.calendar.temporal_resolver import CalendarTemporalResolver
from flowmate.tools.calendar import CalendarEvent


class GoogleCalendarTransportError(CalendarProviderError):
    pass


class GoogleCalendarResponseError(CalendarProviderError):
    pass


class GoogleCalendarMappingError(CalendarProviderError):
    pass


class GoogleCalendarProvider:
    def __init__(
        self,
        *,
        service: Any,
        timezone: str,
        calendar_id: str = "primary",
        resolver: CalendarTemporalResolver | None = None,
    ) -> None:
        if not calendar_id.strip():
            raise ValueError("calendar_id must not be blank.")
        self.service = service
        self.timezone = timezone
        self.calendar_id = calendar_id
        self.resolver = resolver or CalendarTemporalResolver(timezone=timezone)
        self.zone = ZoneInfo(timezone)

    def list_events(self, query: CalendarProviderQuery) -> list[CalendarEvent]:
        window = self.resolver.resolve(query)
        page_token: str | None = None
        events: list[CalendarEvent] = []

        while True:
            parameters: dict[str, Any] = {
                "calendarId": self.calendar_id,
                "timeMin": window.start.isoformat(),
                "timeMax": window.end.isoformat(),
                "singleEvents": True,
                "orderBy": "startTime",
                "showDeleted": False,
                "timeZone": self.timezone,
            }
            if page_token is not None:
                parameters["pageToken"] = page_token

            try:
                response = self.service.events().list(**parameters).execute()
            except CalendarProviderError:
                raise
            except Exception as exc:
                raise GoogleCalendarTransportError(
                    "Google Calendar events.list request failed."
                ) from exc

            if not isinstance(response, Mapping):
                raise GoogleCalendarResponseError(
                    "Google Calendar response must be a mapping."
                )
            raw_events = response.get("items", [])
            if not isinstance(raw_events, list):
                raise GoogleCalendarResponseError(
                    "Google Calendar response items must be a list."
                )

            for raw_event in raw_events:
                mapped = self._map_event(raw_event)
                if mapped is not None:
                    events.append(mapped)

            page_token_value = response.get("nextPageToken")
            if page_token_value is None:
                break
            if not isinstance(page_token_value, str) or not page_token_value:
                raise GoogleCalendarResponseError(
                    "Google Calendar nextPageToken must be a non-empty string."
                )
            page_token = page_token_value

        return events

    def _map_event(self, raw_event: Any) -> CalendarEvent | None:
        if not isinstance(raw_event, Mapping):
            raise GoogleCalendarMappingError("Google Calendar event must be a mapping.")

        start = raw_event.get("start")
        end = raw_event.get("end")
        if not isinstance(start, Mapping) or not isinstance(end, Mapping):
            raise GoogleCalendarMappingError(
                "Google Calendar timed event requires start and end mappings."
            )
        if "date" in start or "date" in end:
            return None

        event_id = raw_event.get("id")
        start_value = start.get("dateTime")
        end_value = end.get("dateTime")
        if not isinstance(event_id, str) or not event_id:
            raise GoogleCalendarMappingError("Google Calendar event id is required.")
        if not isinstance(start_value, str) or not isinstance(end_value, str):
            raise GoogleCalendarMappingError(
                "Google Calendar timed event requires start.dateTime and end.dateTime."
            )

        start_datetime = self._parse_datetime(start_value)
        end_datetime = self._parse_datetime(end_value)
        summary = raw_event.get("summary")
        title = summary if isinstance(summary, str) and summary else "(untitled)"
        location = raw_event.get("location")
        description = raw_event.get("description")

        return CalendarEvent(
            id=event_id,
            title=title,
            start_time=start_datetime.astimezone(self.zone).strftime("%H:%M"),
            end_time=end_datetime.astimezone(self.zone).strftime("%H:%M"),
            location=location if isinstance(location, str) else None,
            description=description if isinstance(description, str) else None,
        )

    def _parse_datetime(self, value: str) -> datetime:
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise GoogleCalendarMappingError(
                "Google Calendar event contains an invalid RFC3339 dateTime."
            ) from exc
        if parsed.tzinfo is None:
            raise GoogleCalendarMappingError(
                "Google Calendar event dateTime must include a timezone offset."
            )
        return parsed
