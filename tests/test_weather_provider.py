from flowmate.integrations.weather import MockWeatherProvider, WeatherProviderQuery
from flowmate.tools.weather import WeatherTool, WeatherToolResult


class FakeRealWeatherProvider:
    def get_weather(self, query: WeatherProviderQuery) -> WeatherToolResult:
        return WeatherToolResult(
            location="Shanghai",
            date=query.date,
            condition="clear",
            temperature_c=26.5,
            rain_probability=0.1,
        )


def test_mock_weather_provider_preserves_existing_output():
    provider = MockWeatherProvider()

    result = provider.get_weather(
        WeatherProviderQuery(location="Shanghai", date="tomorrow")
    )

    assert result == WeatherToolResult(
        location="Shanghai",
        date="tomorrow",
        condition="rain",
        temperature_c=18,
        rain_probability=0.8,
    )


def test_weather_tool_defaults_to_mock_provider():
    tool = WeatherTool()

    result = tool.run({"location": "Shanghai", "date": "tomorrow"})

    assert result.condition == "rain"
    assert result.temperature_c == 18
    assert result.rain_probability == 0.8


def test_weather_tool_accepts_real_shaped_provider_without_schema_branching():
    tool = WeatherTool(provider=FakeRealWeatherProvider())

    result = tool.run({"location": "Shanghai", "date": "tomorrow"})

    assert isinstance(result, WeatherToolResult)
    assert result.location == "Shanghai"
    assert result.date == "tomorrow"
    assert result.condition == "clear"
