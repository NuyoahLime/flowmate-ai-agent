from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from flowmate.integrations.weather import WeatherMappingError, WeatherTemporalResolver


def test_temporal_resolver_resolves_today_with_fixed_clock_and_timezone():
    resolver = WeatherTemporalResolver(
        clock=datetime(2026, 8, 10, 16, 30, tzinfo=ZoneInfo("UTC"))
    )

    assert (
        resolver.resolve_date("today", timezone="Asia/Shanghai").isoformat()
        == "2026-08-11"
    )


def test_temporal_resolver_resolves_tomorrow_with_fixed_clock_and_timezone():
    resolver = WeatherTemporalResolver(
        clock=datetime(2026, 8, 10, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    )

    assert (
        resolver.resolve_date("tomorrow", timezone="Asia/Shanghai").isoformat()
        == "2026-08-11"
    )


def test_temporal_resolver_accepts_iso_date():
    resolver = WeatherTemporalResolver(
        clock=datetime(2026, 8, 10, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    )

    assert (
        resolver.resolve_date("2026-08-12", timezone="Asia/Shanghai").isoformat()
        == "2026-08-12"
    )


def test_temporal_resolver_rejects_unknown_date_semantics():
    resolver = WeatherTemporalResolver(
        clock=datetime(2026, 8, 10, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    )

    with pytest.raises(WeatherMappingError):
        resolver.resolve_date("next week", timezone="Asia/Shanghai")


def test_temporal_resolver_requires_timezone_aware_fixed_clock():
    with pytest.raises(ValueError):
        WeatherTemporalResolver(clock=datetime(2026, 8, 10, 12, 0))
