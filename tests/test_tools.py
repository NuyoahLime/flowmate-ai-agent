import pytest
from pydantic import ValidationError

from flowmate.tools import (
    BaseTool,
    NavigationTool,
    NavigationToolResult,
    WeatherTool,
    WeatherToolResult,
)
from flowmate.tools.navigation import NavigationToolInput
from flowmate.tools.weather import WeatherToolInput, WeatherToolResult as WeatherResultModel


def test_weather_tool_can_execute():
    tool = WeatherTool()

    result = tool.run({"location": "Shanghai", "date": "tomorrow"})

    assert result.condition == "rain"
    assert result.temperature_c == 18
    assert result.rain_probability == 0.8


def test_weather_tool_returns_structured_result():
    tool = WeatherTool()

    result = tool.run({"location": "Shanghai", "date": "tomorrow"})

    assert isinstance(result, WeatherToolResult)
    assert result.location == "Shanghai"
    assert result.date == "tomorrow"


def test_weather_input_missing_location_fails_validation():
    tool = WeatherTool()

    with pytest.raises(ValidationError):
        tool.run({"date": "tomorrow"})


def test_weather_result_rejects_invalid_rain_probability():
    with pytest.raises(ValidationError):
        WeatherResultModel(
            location="Shanghai",
            date="tomorrow",
            condition="rain",
            temperature_c=18,
            rain_probability=1.5,
        )


def test_navigation_tool_can_execute():
    tool = NavigationTool()

    result = tool.run(
        {
            "origin": "home",
            "destination": "company",
            "departure_time": "tomorrow 07:30",
        }
    )

    assert result.distance_km == 18.6
    assert result.duration_minutes == 42
    assert result.traffic == "heavy"


def test_navigation_tool_returns_structured_result():
    tool = NavigationTool()

    result = tool.run(
        {
            "origin": "home",
            "destination": "company",
            "departure_time": "tomorrow 07:30",
        }
    )

    assert isinstance(result, NavigationToolResult)
    assert result.origin == "home"
    assert result.destination == "company"


def test_navigation_input_missing_destination_fails_validation():
    tool = NavigationTool()

    with pytest.raises(ValidationError):
        tool.run({"origin": "home", "departure_time": "tomorrow 07:30"})


def test_navigation_result_rejects_negative_distance_and_duration():
    with pytest.raises(ValidationError):
        NavigationToolResult(
            origin="home",
            destination="company",
            distance_km=-1,
            duration_minutes=-5,
            traffic="heavy",
        )


def test_tools_follow_unified_contract():
    tools = [WeatherTool(), NavigationTool()]

    for tool in tools:
        assert isinstance(tool, BaseTool)
        assert isinstance(tool.name, str)
        assert isinstance(tool.description, str)
        assert tool.input_schema in {WeatherToolInput, NavigationToolInput}
        assert callable(tool.execute)
        assert callable(tool.run)
