from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from flowmate.integrations.calendar import (
    CalendarProviderQuery,
    CalendarTemporalResolutionError,
    CalendarTemporalResolver,
)


FIXED_NOW = datetime(2026, 8, 9, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))


def create_resolver(timezone: str = "Asia/Shanghai") -> CalendarTemporalResolver:
    return CalendarTemporalResolver(timezone=timezone, clock=lambda: FIXED_NOW)


def test_today_resolves_to_fixed_clock_local_day():
    window = create_resolver().resolve(CalendarProviderQuery(date="today"))

    assert window.start.isoformat() == "2026-08-09T00:00:00+08:00"
    assert window.end.isoformat() == "2026-08-10T00:00:00+08:00"
    assert window.timezone == "Asia/Shanghai"


def test_tomorrow_resolves_deterministically():
    window = create_resolver().resolve(CalendarProviderQuery(date="tomorrow"))

    assert window.start.isoformat() == "2026-08-10T00:00:00+08:00"
    assert window.end.isoformat() == "2026-08-11T00:00:00+08:00"


@pytest.mark.parametrize(
    ("start_time", "end_time", "expected_start", "expected_end"),
    [
        ("06:00", "12:00", "2026-08-10T06:00:00+08:00", "2026-08-10T12:00:00+08:00"),
        ("12:00", "18:00", "2026-08-10T12:00:00+08:00", "2026-08-10T18:00:00+08:00"),
        ("18:00", "23:59", "2026-08-10T18:00:00+08:00", "2026-08-10T23:59:00+08:00"),
    ],
)
def test_canonical_daypart_windows_are_preserved(
    start_time,
    end_time,
    expected_start,
    expected_end,
):
    window = create_resolver().resolve(
        CalendarProviderQuery(
            date="tomorrow",
            start_time=start_time,
            end_time=end_time,
        )
    )

    assert window.start.isoformat() == expected_start
    assert window.end.isoformat() == expected_end


def test_next_month_resolves_to_concrete_calendar_month():
    window = create_resolver().resolve(CalendarProviderQuery(date="next month"))

    assert window.start.isoformat() == "2026-09-01T00:00:00+08:00"
    assert window.end.isoformat() == "2026-10-01T00:00:00+08:00"


def test_next_month_rolls_year_at_december():
    now = datetime(2026, 12, 20, 9, tzinfo=ZoneInfo("Asia/Shanghai"))
    resolver = CalendarTemporalResolver(
        timezone="Asia/Shanghai",
        clock=lambda: now,
    )

    window = resolver.resolve(CalendarProviderQuery(date="next month"))

    assert window.start.isoformat() == "2027-01-01T00:00:00+08:00"
    assert window.end.isoformat() == "2027-02-01T00:00:00+08:00"


def test_next_month_rejects_unsupported_time_of_day_window():
    with pytest.raises(CalendarTemporalResolutionError):
        create_resolver().resolve(
            CalendarProviderQuery(
                date="next month",
                start_time="06:00",
                end_time="12:00",
            )
        )


def test_unsupported_relative_date_is_rejected_without_expanding_contract():
    with pytest.raises(CalendarTemporalResolutionError):
        create_resolver().resolve(CalendarProviderQuery(date="next quarter"))


def test_clock_must_be_timezone_aware():
    resolver = CalendarTemporalResolver(
        timezone="Asia/Shanghai",
        clock=lambda: datetime(2026, 8, 9, 10, 30),
    )

    with pytest.raises(CalendarTemporalResolutionError):
        resolver.resolve(CalendarProviderQuery(date="today"))


def test_explicit_timezone_does_not_use_system_local_timezone():
    utc_now = datetime(2026, 8, 9, 23, 30, tzinfo=ZoneInfo("UTC"))
    resolver = CalendarTemporalResolver(
        timezone="Asia/Shanghai",
        clock=lambda: utc_now,
    )

    window = resolver.resolve(CalendarProviderQuery(date="today"))

    assert window.start.isoformat() == "2026-08-10T00:00:00+08:00"


def test_blank_or_unknown_timezone_is_rejected():
    with pytest.raises(CalendarTemporalResolutionError):
        CalendarTemporalResolver(timezone="")
    with pytest.raises(CalendarTemporalResolutionError):
        CalendarTemporalResolver(timezone="Not/AZone")
