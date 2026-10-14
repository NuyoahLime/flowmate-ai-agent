import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flowmate.integrations.calendar.google_auth import (
    GoogleCalendarAuthError,
    GoogleCalendarConfigurationError,
    GoogleCalendarSettings,
    build_google_calendar_service,
)
from flowmate.integrations.calendar.google_provider import (
    GoogleCalendarProvider,
)
from flowmate.integrations.calendar.provider import (
    CalendarProviderError,
    CalendarProviderQuery,
)
from flowmate.tools import CalendarTool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run an explicit read-only Google Calendar smoke test."
    )
    parser.add_argument("--date", choices=("today", "tomorrow"), default="today")
    parser.add_argument("--show-events", action="store_true")
    parser.add_argument("--max-events", type=int, default=10)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.max_events < 1:
        print("error=--max-events must be at least 1")
        return 2

    try:
        settings = GoogleCalendarSettings.from_env()
    except GoogleCalendarConfigurationError as exc:
        print_configuration_status()
        print(f"error_type={exc.__class__.__name__}")
        return 2

    try:
        service = build_google_calendar_service(
            settings,
            allow_interactive=True,
        )
        provider = GoogleCalendarProvider(
            service=service,
            calendar_id=settings.calendar_id,
            timezone=settings.timezone,
        )
        query = CalendarProviderQuery(date=args.date)
        window = provider.resolver.resolve(query)
        result = CalendarTool(provider=provider).run({"date": args.date})
    except (GoogleCalendarAuthError, CalendarProviderError) as exc:
        print(f"provider=google")
        print(f"error_type={exc.__class__.__name__}")
        print("success=false")
        return 1

    calendar_label = "primary" if settings.calendar_id == "primary" else "configured_custom"
    print("provider=google")
    print(f"calendar_id={calendar_label}")
    print(f"query_date={args.date}")
    print(f"query_time_min={window.start.isoformat()}")
    print(f"query_time_max={window.end.isoformat()}")
    print(f"event_count={result.event_count}")
    print("result_schema_valid=true")
    print("success=true")

    if args.show_events:
        for event in result.events[: args.max_events]:
            location = event.location or ""
            print(
                "event="
                f"title:{event.title}|start:{event.start_time}|location:{location}"
            )
    return 0


def print_configuration_status() -> None:
    for name in (
        "GOOGLE_CALENDAR_CLIENT_SECRET_FILE",
        "GOOGLE_CALENDAR_TOKEN_FILE",
        "GOOGLE_CALENDAR_TIMEZONE",
    ):
        status = "configured" if os.getenv(name) else "missing"
        print(f"{name}={status}")
    calendar_status = "configured" if os.getenv("GOOGLE_CALENDAR_ID") else "default_primary"
    print(f"GOOGLE_CALENDAR_ID={calendar_status}")


if __name__ == "__main__":
    raise SystemExit(main())
