from pydantic import BaseModel, ConfigDict, Field

from flowmate.tools.base import BaseTool


class WeatherToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: str = Field(min_length=1)
    date: str = Field(min_length=1)


class WeatherToolResult(BaseModel):
    location: str
    date: str
    condition: str
    temperature_c: float
    rain_probability: float = Field(ge=0, le=1)


class WeatherTool(BaseTool[WeatherToolInput, WeatherToolResult]):
    name = "weather_tool"
    description = (
        "Query weather information for a location and date. Cannot control devices, "
        "change the environment, send reminders, or modify calendars."
    )
    input_schema = WeatherToolInput

    def __init__(self, provider: "WeatherProvider | None" = None) -> None:
        if provider is None:
            from flowmate.integrations.weather.mock_provider import MockWeatherProvider

            provider = MockWeatherProvider()
        self.provider = provider

    def execute(self, input_data: WeatherToolInput) -> WeatherToolResult:
        from flowmate.integrations.weather.provider import WeatherProviderQuery

        provider = getattr(self, "provider", None)
        if provider is None:
            from flowmate.integrations.weather.mock_provider import MockWeatherProvider

            provider = MockWeatherProvider()
            self.provider = provider

        return provider.get_weather(
            WeatherProviderQuery(location=input_data.location, date=input_data.date)
        )


from flowmate.integrations.weather.provider import WeatherProvider
